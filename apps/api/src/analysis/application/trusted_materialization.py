"""Lane C / C3b-1: the ONE canonical materializer of an approved (#714) artifact.

#714 ``commit_candidate`` is the only trust authority. When a human approves an
exact candidate it promotes it to TRUSTED and -- in the same transaction --
records a durable, artifact-keyed obligation
(``system_recovery.trusted_projection_index.materialization_state = 'pending'``).
This module turns that obligation into canonical project state.

Execution model: AT-LEAST-ONCE delivery + IDEMPOTENT durable effects.

* Identity: the approved ``artifact_id``. ``uq_analyses_source_artifact`` makes
  "one trusted artifact -> at most one canonical materialization" a database
  fact; the composite FK pins that analysis to the artifact's tenant/project.
* Single path: the fenced HITL resume (N17) calls
  :func:`materialize_in_transaction` inside ITS transaction, right after
  ``commit_candidate``, so approval and materialization commit together and the
  obligation is already ``materialized`` when anyone else looks. The async
  worker (``core.tasks.materialization_tasks``) calls the same function for an
  obligation that was left ``pending`` -- it then finds the materialization and
  writes nothing.
* Stale guard (under the document + project locks the caller holds, plus the
  artifact row lock taken here): the artifact must still be exactly the bound
  version/digest, TRUSTED + ACTIVE, in this tenant/project/document, and the
  C3a trusted-current resolver must still point at its revision. Otherwise the
  outcome is OBSOLETE with ZERO canonical writes.
* The graph is never re-run: the content comes from the approved run's own
  state (resume) or from the immutable artifact payload (async).

Derived-state policy (C3b-1):

* ``materialized`` means "every effect CURRENTLY AUTHORISED BY GOVERNANCE was
  applied" -- NOT "every proposed effect became canonical". Effects that need a
  governance step this approval does not provide are DEFERRED and recorded as
  qualifications on the artifact-keyed obligation and the completion event.
* WBS is a governed canonical project backbone. A generic artifact approval
  does not prove that a human reviewed, could edit and approved the exact WBS
  tree as scope authority, and WBS identity is generated-code-only today
  (ProjectGraph marks every pairing ``generated_anchor``). So NO canonical WBS
  is written here -- not even a project's first one: nothing is created,
  replaced, upserted or re-linked, and RACI / BOM are never touched. The
  proposal stays in the exact approved artifact
  (``document_artifacts.payload.extracted_wbs``, bound by id/version/digest and
  revision) for the future governed baseline workflow (review + edit + approve
  -> Baseline #1, then governed change proposals -> Baseline #N+1), and the
  materialization is qualified ``WBS_GOVERNANCE_REQUIRED``.
* Alerts: the per-analysis RISK alerts are created exactly as before (once,
  because the analysis is created once); existing alerts, their human
  disposition and reviewer evidence are never read or modified here. The
  canonical AlertGeneratorService (#828) reconciles COHERENCE alerts only and
  has no stable identity for RISK findings (no rule, anchor or detector
  evidence), so cross-revision RISK reconciliation is NOT attempted and is
  qualified ``RISK_ALERT_RECONCILIATION_REQUIRED``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select, text

from src.analysis.domain.enums import AnalysisStatus, AnalysisType

logger = structlog.get_logger()

#: Bumped whenever the set or semantics of canonical effects changes.
MATERIALIZER_VERSION = "c3b1-trusted-materializer-v2"
MATERIALIZATION_COMPLETED_EVENT = "materialization.completed"

Fault = Callable[[str], Awaitable[None]]


class MaterializationState(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    MATERIALIZED = "materialized"
    OBSOLETE = "obsolete"
    OPERATOR_REQUIRED = "operator_required"


class MaterializationQualification(StrEnum):
    WBS_GOVERNANCE_REQUIRED = "WBS_GOVERNANCE_REQUIRED"
    RISK_ALERT_RECONCILIATION_REQUIRED = "RISK_ALERT_RECONCILIATION_REQUIRED"


class MaterializationStatus(StrEnum):
    CREATED = "created"
    ALREADY_MATERIALIZED = "already_materialized"
    OBSOLETE = "obsolete"


@dataclass(frozen=True)
class ArtifactRef:
    """The exact approved candidate (CandidateBinding + its scope)."""

    artifact_id: UUID
    document_id: UUID
    artifact_version: int
    artifact_hash: str
    project_id: UUID
    tenant_id: UUID


@dataclass(frozen=True)
class MaterializationContent:
    """What becomes canonical. Never re-derived by re-running the graph."""

    document_id: str | None
    risks: list[Any]
    wbs: list[Any]
    coherence_score: int | float | None = None
    coherence_breakdown: Mapping[str, Any] = field(default_factory=dict)
    assessment: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> MaterializationContent:
        return cls(
            document_id=_str_or_none(state.get("document_id")),
            risks=list(state.get("extracted_risks") or []),
            wbs=list(state.get("extracted_wbs") or []),
            coherence_score=state.get("coherence_score"),
            coherence_breakdown=state.get("coherence_breakdown") or {},
            assessment=state.get("single_document_assessment") or {},
        )

    @classmethod
    def from_artifact(
        cls, payload: Mapping[str, Any], scoring: Mapping[str, Any] | None
    ) -> MaterializationContent:
        score = (scoring or {}).get("coherence_score")
        return cls(
            document_id=_str_or_none(payload.get("document_id")),
            risks=list(payload.get("extracted_risks") or []),
            wbs=list(payload.get("extracted_wbs") or []),
            coherence_score=round(score) if isinstance(score, int | float) else None,
            coherence_breakdown={},
            assessment={},
        )


@dataclass(frozen=True)
class ResumeLink:
    """Fenced HITL resume provenance, recorded on the analysis it creates."""

    operation_id: UUID
    attempt_id: UUID
    fencing_token: int
    decision_revision: int


@dataclass(frozen=True)
class MaterializationOutcome:
    status: MaterializationStatus
    analysis_id: UUID | None
    qualifications: tuple[str, ...] = ()
    reason: str | None = None


# -- locks ---------------------------------------------------------------------

# Canonical cross-aggregate lock order (see resume_ownership.finalize_v3):
# DOCUMENT -> (RESUME_OPERATION) -> PROJECT -> ARTIFACT -> OBLIGATION.
_LOCK_DOCUMENT_SQL = text(
    "SELECT id FROM documents "
    "WHERE id = cast(:document_id as uuid) AND tenant_id = cast(:tenant_id as uuid) "
    "FOR UPDATE"
)
_LOCK_PROJECT_SQL = text(
    "SELECT id FROM projects "
    "WHERE id = cast(:project_id as uuid) AND tenant_id = cast(:tenant_id as uuid) "
    "FOR UPDATE"
)


async def lock_document(session: Any, *, tenant_id: UUID, document_id: UUID) -> bool:
    row = (
        await session.execute(
            _LOCK_DOCUMENT_SQL, {"document_id": str(document_id), "tenant_id": str(tenant_id)}
        )
    ).first()
    return row is not None


async def lock_project(session: Any, *, tenant_id: UUID, project_id: UUID) -> bool:
    row = (
        await session.execute(
            _LOCK_PROJECT_SQL, {"project_id": str(project_id), "tenant_id": str(tenant_id)}
        )
    ).first()
    return row is not None


# -- obligation ----------------------------------------------------------------

_MARK_MATERIALIZED_SQL = text(
    """
    UPDATE system_recovery.trusted_projection_index
       SET materialization_state = 'materialized',
           materialized_analysis_id = cast(:analysis_id as uuid),
           materialization_detail = coalesce(cast(:detail as jsonb), materialization_detail),
           materialization_checked_at = (clock_timestamp() AT TIME ZONE 'UTC'),
           updated_at = (clock_timestamp() AT TIME ZONE 'UTC')
     WHERE artifact_id = cast(:artifact_id as uuid)
       AND tenant_id = cast(:tenant_id as uuid)
       AND materialization_state <> 'materialized'
    """
)

_MARK_OBSOLETE_SQL = text(
    """
    UPDATE system_recovery.trusted_projection_index
       SET materialization_state = 'obsolete',
           materialization_detail = cast(:detail as jsonb),
           materialization_checked_at = (clock_timestamp() AT TIME ZONE 'UTC'),
           updated_at = (clock_timestamp() AT TIME ZONE 'UTC')
     WHERE artifact_id = cast(:artifact_id as uuid)
       AND tenant_id = cast(:tenant_id as uuid)
       AND materialization_state IN ('pending', 'operator_required')
    """
)


async def mark_obsolete(session: Any, ref: ArtifactRef, reason: str) -> None:
    await session.execute(
        _MARK_OBSOLETE_SQL,
        {
            "artifact_id": str(ref.artifact_id),
            "tenant_id": str(ref.tenant_id),
            "detail": _json({"reason": reason, "materializer_version": MATERIALIZER_VERSION}),
        },
    )


def materialization_detail(
    ref: ArtifactRef, content: MaterializationContent, qualifications: Sequence[str]
) -> dict[str, Any]:
    """The durable meaning of ``materialized`` for this artifact.

    ``scope`` makes explicit that only governance-authorised effects were
    applied; ``deferred_effects`` names what still needs governance and where
    the exact proposal is recoverable from.
    """
    deferred: dict[str, Any] = {}
    if MaterializationQualification.WBS_GOVERNANCE_REQUIRED in qualifications:
        deferred["wbs"] = {
            "qualification": MaterializationQualification.WBS_GOVERNANCE_REQUIRED.value,
            "proposed_nodes": len(content.wbs),
            "proposal_source": {
                "table": "document_artifacts",
                "artifact_id": str(ref.artifact_id),
                "artifact_version": ref.artifact_version,
                "artifact_hash": ref.artifact_hash,
                "path": "payload.extracted_wbs",
            },
        }
    return {
        "scope": "governance_authorized_effects_applied",
        "qualifications": list(qualifications),
        "deferred_effects": deferred,
        "materializer_version": MATERIALIZER_VERSION,
    }


async def _mark_materialized(
    session: Any, ref: ArtifactRef, analysis_id: UUID, detail: Mapping[str, Any] | None
) -> None:
    await session.execute(
        _MARK_MATERIALIZED_SQL,
        {
            "artifact_id": str(ref.artifact_id),
            "tenant_id": str(ref.tenant_id),
            "analysis_id": str(analysis_id),
            # A replay re-links the existing result and keeps its recorded detail.
            "detail": _json(dict(detail)) if detail is not None else None,
        },
    )


# -- stale guard ---------------------------------------------------------------


async def verify_current_authority(session: Any, ref: ArtifactRef) -> str | None:
    """Re-check, under lock, that ``ref`` is still the trusted-current artifact.

    Returns ``None`` when it is, else the reason it is not. Locks the artifact
    row (the trust authority's own row), so no concurrent approval or
    supersession of this document can change the answer before commit.
    """
    from src.analysis.adapters.persistence.models import DocumentArtifactORM
    from src.analysis.domain.trust import TrustState
    from src.temporal.adapters.persistence.current_revision_resolver import (
        SqlAlchemyCurrentRevisionResolver,
    )
    from src.temporal.domain.current_revision import CurrentRevisionStatus

    row = (
        await session.execute(
            select(DocumentArtifactORM)
            .where(
                DocumentArtifactORM.artifact_id == ref.artifact_id,
                DocumentArtifactORM.tenant_id == ref.tenant_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        return "artifact_not_found"
    if row.project_id != ref.project_id or row.document_id != ref.document_id:
        return "artifact_scope_mismatch"
    if int(row.artifact_version) != ref.artifact_version or row.artifact_hash != ref.artifact_hash:
        return "binding_mismatch"
    if row.trust_state != TrustState.TRUSTED.value or row.lifecycle_status != "active":
        return f"artifact_not_trusted_active:{row.trust_state}/{row.lifecycle_status}"

    current = await SqlAlchemyCurrentRevisionResolver(session).resolve(
        tenant_id=ref.tenant_id, document_id=ref.document_id
    )
    if row.document_revision_id is not None:
        if (
            current.status is not CurrentRevisionStatus.TRUSTED
            or current.revision_id != row.document_revision_id
        ):
            return "not_trusted_current_revision"
    elif current.status is not CurrentRevisionStatus.SINGLE_REVISION:
        # A pre-lineage (unbound) artifact is current only while the document
        # has at most one revision and no revision-bound trusted artifact.
        return "unbound_artifact_not_current"
    return None


# -- the materializer ----------------------------------------------------------


async def materialize_in_transaction(
    session: Any,
    *,
    ref: ArtifactRef,
    content: MaterializationContent,
    resume: ResumeLink | None = None,
    actor: str = "trusted_materializer",
    fault: Fault | None = None,
) -> MaterializationOutcome:
    """Make ``ref``'s canonical project state durable at most once.

    The caller owns the transaction and must already hold the DOCUMENT and
    PROJECT locks (:func:`lock_document`, :func:`lock_project`). Nothing here
    commits; an exception rolls every effect back with the caller.
    """
    from src.analysis.adapters.persistence.models import Analysis

    reason = await verify_current_authority(session, ref)
    if reason is not None:
        logger.warning(
            "trusted_materialization_obsolete",
            artifact_id=str(ref.artifact_id),
            reason=reason,
        )
        return MaterializationOutcome(MaterializationStatus.OBSOLETE, None, reason=reason)

    existing = (
        (
            await session.execute(
                select(Analysis.id).where(
                    Analysis.source_artifact_id == ref.artifact_id,
                    Analysis.tenant_id == ref.tenant_id,
                )
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        # Replay (duplicate delivery, beat sweep, resume-then-worker): the
        # canonical effect already happened. Write nothing new.
        await _mark_materialized(session, ref, existing, None)
        return MaterializationOutcome(MaterializationStatus.ALREADY_MATERIALIZED, existing)

    analysis_id, qualifications = await write_canonical_effects(
        session,
        tenant_id=ref.tenant_id,
        project_id=ref.project_id,
        content=content,
        source_artifact_id=ref.artifact_id,
        resume=resume,
        fault=fault,
    )

    now = _utcnow()
    from src.temporal.adapters.persistence.models import ProjectEventORM

    row = (
        await session.execute(
            text(
                "SELECT document_revision_id FROM document_artifacts "
                "WHERE artifact_id = cast(:a as uuid)"
            ),
            {"a": str(ref.artifact_id)},
        )
    ).first()
    revision_id = row.document_revision_id if row is not None else None
    # Append-only completion evidence. Never the idempotency authority: that is
    # uq_analyses_source_artifact above.
    session.add(
        ProjectEventORM(
            event_id=uuid4(),
            project_id=ref.project_id,
            tenant_id=ref.tenant_id,
            event_type=MATERIALIZATION_COMPLETED_EVENT,
            payload={
                "artifact_id": str(ref.artifact_id),
                "document_id": str(ref.document_id),
                "document_revision_id": str(revision_id) if revision_id else None,
                "artifact_version": ref.artifact_version,
                "artifact_hash": ref.artifact_hash,
                "analysis_id": str(analysis_id),
                **materialization_detail(ref, content, qualifications),
                "resume_operation_id": str(resume.operation_id) if resume else None,
            },
            actor=actor,
            evidence_refs=[],
            occurred_at=now,
            created_at=now,
            source_revision_id=revision_id,
        )
    )
    await session.flush()
    await _mark_materialized(
        session, ref, analysis_id, materialization_detail(ref, content, qualifications)
    )
    logger.info(
        "trusted_materialization_created",
        artifact_id=str(ref.artifact_id),
        analysis_id=str(analysis_id),
        qualifications=list(qualifications),
    )
    return MaterializationOutcome(MaterializationStatus.CREATED, analysis_id, qualifications)


async def write_canonical_effects(
    session: Any,
    *,
    tenant_id: UUID,
    project_id: UUID,
    content: MaterializationContent,
    source_artifact_id: UUID | None,
    resume: ResumeLink | None,
    fault: Fault | None = None,
) -> tuple[UUID, tuple[str, ...]]:
    """The extracted N17 persistence core: analysis + alerts; WBS is deferred.

    Shared by the artifact-keyed materializer and the pre-#714 (unbound)
    resume path, so there is exactly one implementation of "what approval
    makes canonical".
    """
    from src.analysis.adapters.persistence.analysis_repository import (
        SqlAlchemyAnalysisRepository,
    )
    from src.analysis.ports.types import AlertWrite, AnalysisWrite
    from src.coherence.alert_generator import AlertGenerator

    qualifications: list[str] = []
    analysis_id = uuid4()
    repo = SqlAlchemyAnalysisRepository(session)
    await repo.add_analysis(
        AnalysisWrite(
            id=analysis_id,
            tenant_id=tenant_id,
            project_id=project_id,
            analysis_type=AnalysisType.RISK if content.risks else AnalysisType.SCHEDULE,
            status=AnalysisStatus.COMPLETED,
            coherence_score=content.coherence_score,
            coherence_breakdown=dict(content.coherence_breakdown),
            alerts_count=len(content.risks),
            completed_at=_utcnow(),
            result_json={"risks": content.risks, "wbs": content.wbs, **dict(content.assessment)},
            resume_operation_id=resume.operation_id if resume else None,
            resume_attempt_id=resume.attempt_id if resume else None,
            fencing_token=resume.fencing_token if resume else None,
            decision_revision=resume.decision_revision if resume else None,
            source_artifact_id=source_artifact_id,
        ),
        tenant_id=tenant_id,
    )
    await repo.flush()
    if fault is not None:
        await fault("after_analysis")

    if content.risks:
        generator = AlertGenerator(project_id=project_id, analysis_id=analysis_id)
        await repo.add_alerts(
            [
                AlertWrite(
                    tenant_id=tenant_id,
                    project_id=dto.project_id,
                    analysis_id=dto.analysis_id,
                    alert_type=dto.alert_type,
                    severity=dto.severity,
                    title=dto.title,
                    message=dto.description,
                    description=dto.description,
                    category=dto.category,
                    impact_level=dto.impact_level,
                    alert_metadata=dto.alert_metadata,
                    rule_id=dto.rule_id,
                    source_clause_id=dto.source_clause_id,
                    related_clause_ids=dto.related_clause_ids,
                    affected_entities=dto.affected_entities,
                    recommendation=dto.recommendation,
                )
                for dto in generator.generate_risk_alerts(content.risks)
            ],
            tenant_id=tenant_id,
        )
        await repo.flush()
        # No canonical identity exists for RISK findings (see module docstring).
        qualifications.append(MaterializationQualification.RISK_ALERT_RECONCILIATION_REQUIRED)
    if fault is not None:
        await fault("after_alerts")

    if content.wbs:
        # Governed backbone: no canonical WBS write without a governed baseline
        # approval -- whether or not the project already has a WBS.
        qualifications.append(MaterializationQualification.WBS_GOVERNANCE_REQUIRED)
        logger.info(
            "trusted_materialization_wbs_governance_required",
            project_id=str(project_id),
            proposed_nodes=len(content.wbs),
        )
    if fault is not None:
        await fault("after_wbs")

    return analysis_id, tuple(qualifications)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _str_or_none(value: Any) -> str | None:
    return str(value) if value else None


def _json(value: Any) -> str:
    import json

    return json.dumps(value)


__all__ = [
    "MATERIALIZATION_COMPLETED_EVENT",
    "MATERIALIZER_VERSION",
    "ArtifactRef",
    "MaterializationContent",
    "MaterializationOutcome",
    "MaterializationQualification",
    "MaterializationState",
    "MaterializationStatus",
    "ResumeLink",
    "lock_document",
    "lock_project",
    "materialization_detail",
    "mark_obsolete",
    "materialize_in_transaction",
    "verify_current_authority",
    "write_canonical_effects",
]
