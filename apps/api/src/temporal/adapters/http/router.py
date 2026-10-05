"""TS-UT-P0C-TEMPORAL-003 - tenant-scoped temporal change API."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol, cast
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_session_with_tenant
from src.core.tenants.types import TenantId, require_tenant_id
from src.projects.adapters.persistence.project_repository import SQLAlchemyProjectRepository
from src.projects.ports.project_repository import ProjectRepository
from src.temporal.adapters.persistence.clause_impact_resolver import SqlAlchemyClauseImpactResolver
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.application.change_qualification import (
    CHANGE_EVENT_TYPES,
    ChangeQualification,
    qualify_event,
)
from src.temporal.application.effective_change import (
    OUTCOME_EVENT_TYPES,
    EffectiveOutcome,
    derivation_of,
    derived_from,
    effective_by_revision,
    select_effective_outcome,
)
from src.temporal.application.impact_assessment import (
    ImpactResolver,
    ResolverResult,
    assess_change_impacts,
)
from src.temporal.application.revision_projection import (
    RevisionProjection,
    project_revision_coherence,
)
from src.temporal.application.revision_status import RevisionStatus
from src.temporal.application.timeline import (
    InvalidTimelineCursor,
    TimelineScope,
    decode_cursor,
    encode_cursor,
)
from src.temporal.domain.entity_ref import TemporalEntityRef
from src.temporal.domain.impact import ChangeImpact, EpistemicBasis
from src.temporal.domain.project_event import ProjectEvent
from src.temporal.ports.project_event_repository import IProjectEventRepository

logger = structlog.get_logger()

router = APIRouter(prefix="/projects", tags=["Temporal changes"])

ImpactAssessor = Callable[[ProjectEvent, ChangeQualification], Awaitable[list[ChangeImpact]]]


class RevisionProjector(Protocol):
    def __call__(
        self, *, project_id: UUID, document_id: UUID, revision_id: UUID, qualification: ChangeQualification
    ) -> Awaitable[RevisionProjection]: ...


class RevisionStatusRead(Protocol):
    def __call__(
        self, *, project_id: UUID, document_id: UUID, revision_id: UUID
    ) -> Awaitable[RevisionStatus | None]: ...


class TimelineItemResponse(BaseModel):
    """One immutable event rendered for the What Changed product surface."""

    event_id: UUID
    occurred_at: str
    event_type: str
    # A stored event is observed evidence; ``state``, ``confidence`` and
    # ``change_cause`` are its read-time qualified values (PR-C2), never mutated.
    basis: EpistemicBasis = EpistemicBasis.OBSERVED
    state: str
    change_cause: str | None = None
    confidence: float | None = None
    # "current" | "legacy" | "unsupported"; None for a non-comparison event.
    matcher_status: str | None = None
    legacy_matcher: bool = False
    qualification_reason: str | None = None
    document_id: UUID | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    l3_impact: None = None
    # C3b-2 lineage (revision outcomes only; None for bookkeeping events):
    # "original" | "recomputed" | "reinterpreted".
    derivation: str | None = None
    derived_from_event_id: UUID | None = None
    # Whether this is the revision's EFFECTIVE outcome (lineage + matcher, never
    # recency alone); a historical event names the event that supersedes it.
    effective: bool | None = None
    superseded_by_event_id: UUID | None = None


class TimelineResponse(BaseModel):
    """Stable cursor page; an empty page means no events, not an unavailable diff."""

    items: list[TimelineItemResponse]
    next_cursor: str | None = None


class ChangeDetailResponse(TimelineItemResponse):
    """Evidence-grounded revision detail with L1/L2 before and after snapshots."""

    changes: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    # DERIVED: persisted relationships of each changed entity (never similarity).
    impacts: list[ChangeImpact] = Field(default_factory=list)
    # PROJECTED: hypothetical #714 Coherence with this revision's pending candidate.
    projection: RevisionProjection | None = None
    # Every outcome recorded for this revision, with lineage (historical included).
    history: list[TimelineItemResponse] = Field(default_factory=list)
    # Trust / current-vs-historical / materialization status of the revision.
    revision_status: RevisionStatus | None = None


async def get_event_repository(
    current_user: User = Depends(get_current_user),
) -> AsyncIterator[IProjectEventRepository]:
    """Open the event reader with the caller's RLS tenant context."""
    async with get_session_with_tenant(current_user.tenant_id) as db:
        yield SqlAlchemyProjectEventRepository(db)


async def get_project_repository(
    current_user: User = Depends(get_current_user),
) -> AsyncIterator[ProjectRepository]:
    """Open the ownership gate with the same RLS tenant context as events."""
    async with get_session_with_tenant(current_user.tenant_id) as db:
        yield SQLAlchemyProjectRepository(db)


class _FailClosedResolver:
    """A resolver failure is UNKNOWN impact, never a missing or partial claim."""

    def __init__(self, inner: ImpactResolver, session: AsyncSession) -> None:
        self.entity_type = inner.entity_type
        self._inner = inner
        self._session = session

    async def resolve(self, source: TemporalEntityRef) -> ResolverResult:
        try:
            async with self._session.begin_nested():
                return await self._inner.resolve(source)
        except Exception:  # noqa: BLE001 - degrade to UNKNOWN, keep the detail readable
            logger.warning("temporal_impact_resolution_failed", entity_type=self.entity_type, exc_info=True)
            return ResolverResult(links=[], source_verified=False, reason="impact lookup unavailable")


async def _document_type(session: AsyncSession, tenant_id: UUID, document_id: UUID) -> str | None:
    from src.documents.adapters.persistence.models import DocumentORM

    value = (
        await session.execute(
            select(DocumentORM.document_type).where(DocumentORM.id == document_id, DocumentORM.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    return str(getattr(value, "value", value)) if value is not None else None


async def get_impact_assessor(
    current_user: User = Depends(get_current_user),
) -> AsyncIterator[ImpactAssessor]:
    """Impact resolution over persisted relationships, in the caller's RLS context."""
    tenant_id = require_tenant_id(current_user.tenant_id)
    async with get_session_with_tenant(tenant_id) as db:
        # Resolvers are selected by source entity type; only clauses have one today.
        resolvers: dict[str, ImpactResolver] = {
            "clause": _FailClosedResolver(SqlAlchemyClauseImpactResolver(db, tenant_id=tenant_id), db),
        }

        async def assess(event: ProjectEvent, qualification: ChangeQualification) -> list[ChangeImpact]:
            document_id = _projection_payload(event).get("document_id")
            artifact_type = (
                await _document_type(db, tenant_id, UUID(document_id)) if isinstance(document_id, str) else None
            )
            return await assess_change_impacts(
                event=event, qualification=qualification, resolvers=resolvers, artifact_type=artifact_type
            )

        yield assess


async def get_revision_projector(
    current_user: User = Depends(get_current_user),
) -> AsyncIterator[RevisionProjector]:
    """#714 projection of this revision's pending candidate; read-only, never trusted."""
    from src.analysis.adapters.graph.project_graph import (
        evaluate_artifact_set,
        is_coherence_llm_enabled,
    )
    from src.analysis.adapters.persistence.document_artifact_repository import (
        SqlAlchemyDocumentArtifactRepository,
    )

    tenant_id = require_tenant_id(current_user.tenant_id)
    async with get_session_with_tenant(tenant_id) as db:
        repo = SqlAlchemyDocumentArtifactRepository(db)

        async def project(
            *, project_id: UUID, document_id: UUID, revision_id: UUID, qualification: ChangeQualification
        ) -> RevisionProjection:
            async def _evaluate(artifacts: list[Any]) -> Any:
                llm_on = await is_coherence_llm_enabled(tenant_id)
                return await evaluate_artifact_set(artifacts, project_id=project_id, tenant_id=tenant_id, llm_on=llm_on)

            try:
                async with db.begin_nested():
                    return await project_revision_coherence(
                        document_id=document_id,
                        revision_id=revision_id,
                        list_pending=lambda: repo.list_pending_candidates(project_id=project_id, tenant_id=tenant_id),
                        list_trusted=lambda: repo.list_trusted_for_project(project_id=project_id, tenant_id=tenant_id),
                        evaluate=_evaluate,
                        qualification=qualification,
                    )
            except Exception:  # noqa: BLE001 - a projection never hides the observed change
                logger.warning("temporal_revision_projection_unavailable", revision_id=str(revision_id), exc_info=True)
                return RevisionProjection(
                    status="unavailable", source_revision_id=revision_id, reason="projection_read_failed"
                )

        yield project


async def get_revision_status_reader(
    current_user: User = Depends(get_current_user),
) -> AsyncIterator[RevisionStatusRead]:
    """Trust / currency / materialization of one revision; read-only, fail closed."""
    from src.temporal.adapters.persistence.revision_status_reader import (
        SqlAlchemyRevisionStatusReader,
    )

    tenant_id = require_tenant_id(current_user.tenant_id)
    async with get_session_with_tenant(tenant_id) as db:
        reader = SqlAlchemyRevisionStatusReader(db)

        async def read(*, project_id: UUID, document_id: UUID, revision_id: UUID) -> RevisionStatus | None:
            try:
                async with db.begin_nested():
                    return await reader.read(
                        tenant_id=tenant_id, project_id=project_id, document_id=document_id, revision_id=revision_id
                    )
            except Exception:  # noqa: BLE001 - status unknown is never "current" or "trusted"
                logger.warning("temporal_revision_status_unavailable", revision_id=str(revision_id), exc_info=True)
                return RevisionStatus.unavailable(revision_id, "revision_status_read_failed")

        yield read


def _projection_payload(event: ProjectEvent) -> dict[str, Any]:
    return event.payload if isinstance(event.payload, dict) else {}


def _item(
    event: ProjectEvent,
    qualification: ChangeQualification | None = None,
    lineage: EffectiveOutcome | None = None,
) -> TimelineItemResponse:
    payload = _projection_payload(event)
    document_id = payload.get("document_id")
    qualified = qualification or qualify_event(event)
    outcome = event.event_type in OUTCOME_EVENT_TYPES
    effective = lineage.is_effective(event) if outcome and lineage is not None else None
    return TimelineItemResponse(
        event_id=event.event_id,
        occurred_at=event.occurred_at.isoformat(),
        event_type=event.event_type,
        state=qualified.effective_state,
        change_cause=qualified.effective_change_cause,
        confidence=qualified.effective_confidence,
        matcher_status=qualified.matcher_status.value if qualified.matcher_status else None,
        legacy_matcher=qualified.legacy_matcher,
        qualification_reason=qualified.reason,
        document_id=UUID(document_id) if isinstance(document_id, str) else None,
        provenance=cast(dict[str, Any], payload["provenance"]) if isinstance(payload.get("provenance"), dict) else {},
        l3_impact=None,
        derivation=derivation_of(event).value if outcome else None,
        derived_from_event_id=derived_from(event) if outcome else None,
        effective=effective,
        superseded_by_event_id=(
            lineage.superseded_by.get(event.event_id) if outcome and lineage is not None else None
        ),
    )


async def _require_project_access(
    project_id: UUID,
    tenant_id: TenantId,
    projects: ProjectRepository,
) -> None:
    if not await projects.exists_by_id(project_id, tenant_id):
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/{project_id}/timeline", response_model=TimelineResponse)
async def get_project_timeline(
    project_id: UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    events: IProjectEventRepository = Depends(get_event_repository),
    projects: ProjectRepository = Depends(get_project_repository),
) -> TimelineResponse:
    """Read the append-only project timeline in canonical temporal order."""

    tenant_id = require_tenant_id(current_user.tenant_id)
    await _require_project_access(project_id, tenant_id, projects)
    scope = TimelineScope(tenant_id=tenant_id, project_id=project_id)
    try:
        after = (
            decode_cursor(cursor, scope=scope, secret=settings.jwt_secret_key)
            if cursor
            else None
        )
    except InvalidTimelineCursor as exc:
        raise HTTPException(status_code=400, detail="Invalid or stale timeline cursor") from exc
    rows = await events.page_for_project(project_id, tenant_id, after=after, limit=limit)
    page_items = rows[:limit]
    next_cursor = (
        encode_cursor(
            page_items[-1].occurred_at,
            page_items[-1].event_id,
            scope=scope,
            secret=settings.jwt_secret_key,
        )
        if len(rows) > limit and page_items
        else None
    )
    # Lineage is decided over ALL outcomes of each revision on the page, not just
    # the ones this page happens to include.
    revision_ids = [
        event.source_revision_id
        for event in page_items
        if event.event_type in OUTCOME_EVENT_TYPES and event.source_revision_id is not None
    ]
    outcomes = (
        await events.list_outcomes_for_revisions(tenant_id=tenant_id, revision_ids=revision_ids)
        if revision_ids
        else []
    )
    lineage = effective_by_revision([event for event in outcomes if event.project_id == project_id])
    return TimelineResponse(
        items=[
            _item(
                event,
                lineage=lineage.get(event.source_revision_id) if event.source_revision_id else None,
            )
            for event in page_items
        ],
        next_cursor=next_cursor,
    )


@router.get(
    "/{project_id}/documents/{document_id}/changes/{revision_id}",
    response_model=ChangeDetailResponse,
)
async def get_revision_change_detail(
    project_id: UUID,
    document_id: UUID,
    revision_id: UUID,
    event_id: UUID | None = Query(
        default=None,
        description="Read one specific (possibly historical) comparison of this revision; "
        "omitted, the revision's EFFECTIVE comparison is returned.",
    ),
    current_user: User = Depends(get_current_user),
    events: IProjectEventRepository = Depends(get_event_repository),
    projects: ProjectRepository = Depends(get_project_repository),
    assess_impacts: ImpactAssessor = Depends(get_impact_assessor),
    project_revision: RevisionProjector = Depends(get_revision_projector),
    read_revision_status: RevisionStatusRead = Depends(get_revision_status_reader),
) -> ChangeDetailResponse:
    """Read a revision detail only from the tenant-scoped immutable projection."""

    tenant_id = require_tenant_id(current_user.tenant_id)
    await _require_project_access(project_id, tenant_id, projects)
    history = await events.list_revision_outcomes(
        tenant_id=tenant_id,
        project_id=project_id,
        document_id=document_id,
        revision_id=revision_id,
    )
    lineage = select_effective_outcome(history)
    if event_id is None:
        event = await events.get_change_for_revision(
            tenant_id=tenant_id,
            project_id=project_id,
            document_id=document_id,
            revision_id=revision_id,
        )
    else:
        event = next(
            (e for e in history if e.event_id == event_id and e.event_type in CHANGE_EVENT_TYPES),
            None,
        )
    if event is None:
        raise HTTPException(status_code=404, detail="Change not found")
    payload = _projection_payload(event)
    provenance = payload.get("provenance")
    if (
        not isinstance(provenance, dict)
        or provenance.get("target_revision_id") != str(revision_id)
        or payload.get("document_id") != str(document_id)
    ):
        raise HTTPException(status_code=404, detail="Change not found")
    qualification = qualify_event(event)
    item = _item(event, qualification, lineage)
    changeset = payload.get("changeset")
    changes = changeset.get("changes", []) if isinstance(changeset, dict) else []
    return ChangeDetailResponse(
        **item.model_dump(),
        changes=changes if isinstance(changes, list) else [],
        evidence_refs=[ref.model_dump(mode="json") for ref in event.evidence_refs],
        impacts=await assess_impacts(event, qualification),
        projection=await project_revision(
            project_id=project_id, document_id=document_id, revision_id=revision_id, qualification=qualification
        ),
        history=[_item(outcome, lineage=lineage) for outcome in history],
        revision_status=await read_revision_status(
            project_id=project_id, document_id=document_id, revision_id=revision_id
        ),
    )


__all__ = [
    "get_event_repository",
    "get_impact_assessor",
    "get_project_repository",
    "get_revision_projector",
    "get_revision_status_reader",
    "router",
]
