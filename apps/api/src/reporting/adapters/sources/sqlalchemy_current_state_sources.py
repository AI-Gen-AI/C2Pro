"""TS-P0D-REPORT-004 - SQLAlchemy sources for the Current State Report.

Each loader reads one domain through that domain's existing repository or use
case, inside its own tenant-scoped session. Separate sessions keep one failed
query from aborting the transaction another domain would use.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.alerts.adapters.persistence.alert_repository import SqlAlchemyAlertRepository
from src.alerts.domain.models import Alert
from src.analysis.adapters.persistence.models import Analysis, DocumentArtifactORM
from src.analysis.domain.enums import AnalysisStatus
from src.config import get_settings
from src.core.auth.models import User
from src.core.database import get_session_with_tenant
from src.core.tenants.types import require_tenant_id
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.modules.hitl.adapters.persistence.repository import SqlAlchemyReviewQueueRepository
from src.modules.hitl.domain.entities import ReviewStatus
from src.procurement.adapters.persistence.budget_repository import SQLAlchemyBudgetRepository
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.application.budget_use_cases import BudgetResponse, GetBudgetUseCase
from src.projects.adapters.persistence.project_repository import SQLAlchemyProjectRepository
from src.reporting.application.ports import (
    DocumentRevisionState,
    DocumentsInput,
    HitlInput,
    SourceUnavailableError,
    StakeholdersInput,
    WbsInput,
)
from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)
from src.stakeholders.application.dtos import RaciMatrixViewResponse
from src.stakeholders.application.get_raci_matrix_use_case import GetRaciMatrixUseCase
from src.stakeholders.application.list_project_stakeholders_use_case import (
    ListProjectStakeholdersUseCase,
)
from src.temporal.adapters.persistence.models import DocumentRevisionORM, ProjectEventORM
from src.temporal.adapters.persistence.project_snapshot_repository import (
    SqlAlchemyProjectSnapshotRepository,
)
from src.temporal.domain.project_snapshot import ProjectSnapshot
from src.wbs.adapters.persistence.governance_repository import WBSGovernanceRepository

# The document and stakeholder repositories page with OFFSET/LIMIT and no ORDER BY,
# so a multi-page read could repeat or skip rows. Each is read once, bounded, and
# the projection marks counts partial when the true total is larger.
MAX_DOCUMENTS = 1000
MAX_STAKEHOLDERS = 500
MAX_REVIEW_ITEMS_PER_STATUS = 200

# Items still waiting on a human decision. Escalated items are included: they have
# been routed to another reviewer but are not yet decided.
AWAITING_DECISION_STATUSES: tuple[ReviewStatus, ...] = (
    ReviewStatus.PENDING_REVIEW_REQUIRED,
    ReviewStatus.PENDING_REVIEW_CONDITIONAL,
    ReviewStatus.ESCALATED,
)

COHERENCE_DISABLED_REASON = "Coherence analysis is not enabled in this environment."

SessionScope = Callable[[UUID], AbstractAsyncContextManager[AsyncSession]]


async def _read_coherence_dashboard(project_id: UUID, current_user: User, session: AsyncSession) -> Any:
    """Reuse the Coherence dashboard read so the report shows exactly what the Coherence tab shows.

    Imported lazily: the coherence router pulls in the evaluation graph, and it is
    only mounted when coherence analysis is enabled.
    """
    from src.coherence.router import get_coherence_dashboard, get_flags_service

    return await get_coherence_dashboard(
        project_id=project_id,
        current_user=current_user,
        db=session,
        flags_service=get_flags_service(db=session),
    )


async def _load_revision_states(
    session: AsyncSession, tenant_id: UUID, project_id: UUID
) -> dict[UUID, DocumentRevisionState]:
    """Per document: the revision behind the trusted-current artifact and the pending proposal.

    The trusted revision is the one the canonical state was built from; a pending revision is an
    uploaded revision still waiting for human approval (persisted != trusted).
    """
    rows = await session.execute(
        select(
            DocumentArtifactORM.document_id,
            DocumentArtifactORM.trust_state,
            DocumentArtifactORM.lifecycle_status,
            DocumentRevisionORM.revision_id,
            DocumentRevisionORM.rev_no,
            DocumentRevisionORM.blob_hash,
        )
        .join(
            DocumentRevisionORM,
            DocumentRevisionORM.revision_id == DocumentArtifactORM.document_revision_id,
        )
        .where(
            DocumentArtifactORM.tenant_id == tenant_id,
            DocumentArtifactORM.project_id == project_id,
        )
    )
    trusted: dict[UUID, tuple[UUID, int, str]] = {}
    pending: dict[UUID, tuple[UUID, int, str]] = {}
    for document_id, trust_state, lifecycle_status, revision_id, rev_no, blob_hash in rows:
        ref = (revision_id, rev_no, blob_hash)
        if trust_state == "trusted" and lifecycle_status == "active":
            trusted[document_id] = ref
        elif trust_state == "proposed":
            pending[document_id] = ref
    return {
        document_id: DocumentRevisionState(trusted=trusted.get(document_id), pending=pending.get(document_id))
        for document_id in trusted.keys() | pending.keys()
    }


class SqlAlchemyCurrentStateSources:
    def __init__(
        self,
        *,
        current_user: User,
        session_scope: SessionScope = get_session_with_tenant,
        settings_provider: Callable[[], Any] = get_settings,
    ) -> None:
        self._current_user = current_user
        self._session_scope = session_scope
        self._settings_provider = settings_provider

    async def load_documents(self, project_id: UUID, tenant_id: UUID) -> DocumentsInput:
        scoped = require_tenant_id(tenant_id)
        async with self._session_scope(tenant_id) as session:
            documents, total = await SqlAlchemyDocumentRepository(session).list_for_project(
                scoped, project_id, 0, MAX_DOCUMENTS
            )
            return DocumentsInput(
                documents=list(documents),
                total=total,
                revisions=await _load_revision_states(session, scoped, project_id),
            )

    async def load_health(self, project_id: UUID, tenant_id: UUID) -> ProjectSnapshot | None:
        scoped = require_tenant_id(tenant_id)
        async with self._session_scope(tenant_id) as session:
            return await SqlAlchemyProjectSnapshotRepository(session).latest(project_id, scoped)

    async def load_coherence(self, project_id: UUID, tenant_id: UUID) -> Any:
        if not getattr(self._settings_provider(), "feature_coherence_analysis", False):
            raise SourceUnavailableError(COHERENCE_DISABLED_REASON)
        async with self._session_scope(tenant_id) as session:
            return await _read_coherence_dashboard(project_id, self._current_user, session)

    async def load_decision_proposals(self, project_id: UUID, tenant_id: UUID) -> list[dict[str, Any]]:
        """Only N11 proposals tied to the current trusted document revision.

        Historic or revision-unbound results are NOT silently promoted to current.
        A source quote remains unverified; no document URL is invented.
        """
        scoped = require_tenant_id(tenant_id)
        async with self._session_scope(scoped) as session:
            revisions = await _load_revision_states(session, scoped, project_id)
            if not revisions:
                raise SourceUnavailableError("No trusted document revisions to anchor N11 decisions.")
            analyses = (
                await session.execute(
                    select(Analysis)
                    .where(
                        Analysis.project_id == project_id,
                        Analysis.tenant_id == scoped,
                        Analysis.status == AnalysisStatus.COMPLETED,
                    )
                    .order_by(Analysis.completed_at.desc(), Analysis.id.desc())
                    .limit(100)
                )
            ).scalars().all()
            actions: list[dict[str, Any]] = []
            seen_documents: set[UUID] = set()
            for analysis in analyses:
                data = analysis.result_json or {}
                snapshot = data.get("decision_snapshot") if isinstance(data, dict) else None
                if not isinstance(snapshot, dict):
                    continue
                try:
                    document_id = UUID(str(snapshot["document_id"]))
                    revision_id = UUID(str(snapshot["revision_id"]))
                except (KeyError, TypeError, ValueError, AttributeError):
                    continue
                trusted = revisions.get(document_id)
                if trusted is None or trusted.trusted is None or trusted.trusted[0] != revision_id:
                    continue
                # Never re-surface an older assessment of the same current revision.
                if document_id in seen_documents:
                    continue
                seen_documents.add(document_id)
                for action in snapshot.get("proposed_actions") or []:
                    if not isinstance(action, dict) or action.get("status") != "PROPOSED_REQUIRES_HUMAN_REVIEW":
                        continue
                    origin = action.get("source_evidence") or {}
                    if not isinstance(origin, dict):
                        continue
                    try:
                        source_id = UUID(str(origin["document_id"]))
                        source_rev_id = UUID(str(origin["revision_id"]))
                    except (KeyError, TypeError, ValueError, AttributeError):
                        continue
                    source_trusted = revisions.get(source_id)
                    if (
                        source_trusted is None
                        or source_trusted.trusted is None
                        or source_trusted.trusted[0] != source_rev_id
                    ):
                        continue
                    actions.append({
                        "analysis_id": str(analysis.id),
                        "document_id": str(document_id),
                        "revision_id": str(revision_id),
                        "source_document_id": str(source_id),
                        "source_revision_id": str(source_rev_id),
                        "title": str(action.get("title") or "Untitled proposal"),
                        "proposed_action": str(action.get("proposed_action") or ""),
                        "priority_proposal": str(action.get("priority_proposal") or "UNASSESSED"),
                        "risk_impact": action.get("risk_impact"),
                        "clause_ref": origin.get("clause_ref"),
                        "source_quote": origin.get("source_quote"),
                        "source_verification": "REQUIRES_SOURCE_VALIDATION",
                        "status": "PROPOSED_REQUIRES_HUMAN_REVIEW",
                    })
                    if len(actions) >= 5:
                        return actions
            if not actions:
                raise SourceUnavailableError(
                    "No N11 proposals tied to current trusted revisions; older or unbound results remain historical."
                )
            return actions

    async def load_source_discrepancies(self, project_id: UUID, tenant_id: UUID) -> dict[str, Any]:
        """Expose only the newest provisional event and current dual-source revisions.

        A contract/spec quote must still belong to the trusted current artifact.
        An XLSX row must still have the original canonical revision and hashes.
        Nothing here converts a source observation into an approved baseline.
        """
        from src.documents.application.structured_source_units import load_canonical_source_units
        from src.analysis.adapters.graph.source_clause_evidence import (
            load_revision_bound_source_quotes,
        )

        scoped = require_tenant_id(tenant_id)
        async with self._session_scope(scoped) as session:
            event = (await session.execute(
                select(ProjectEventORM).where(
                    ProjectEventORM.project_id == project_id,
                    ProjectEventORM.tenant_id == scoped,
                    ProjectEventORM.event_type == "project_graph.source_discrepancies_observed",
                ).order_by(ProjectEventORM.occurred_at.desc(), ProjectEventORM.event_id.desc()).limit(1)
            )).scalar_one_or_none()
            if event is None:
                raise SourceUnavailableError("No ProjectGraph provisional comparison recorded for this project.")
            payload = event.payload
            if not isinstance(payload, dict) or payload.get("state") != "PROVISIONAL" or payload.get("scoring_policy") != "not_scored":
                raise SourceUnavailableError("ProjectGraph comparison has no valid provisional trust boundary.")
            trusted = await _load_revision_states(session, scoped, project_id)
            rows = []
            for family in ("budget", "schedule"):
                rows.extend(await load_canonical_source_units(
                    session=session, tenant_id=scoped, project_id=project_id, family=family
                ))
            canonical = {
                (str(row.get("document_id")), str(row.get("revision_id")),
                 str(row.get("source_locator")), str(row.get("blob_hash")),
                 str(row.get("unit_sha256")))
                for row in rows
            }
            exact_quotes = await load_revision_bound_source_quotes(
                session=session, tenant_id=scoped, project_id=project_id,
            )
            literal_authority = {
                (str(q["document_id"]), str(q["revision_id"]),
                 q["source_locator"], q["source_quote"], q["source_quote_sha256"])
                for q in exact_quotes
            }
            current = []
            for item in payload.get("findings") or []:
                if not isinstance(item, dict) or (
                    item.get("state") != "PROVISIONAL" or item.get("scored") is not False
                    or item.get("requires_human_review") is not True
                ):
                    continue
                sources = item.get("sources")
                if not isinstance(sources, list) or len(sources) != 2:
                    continue
                quote = next((s for s in sources if isinstance(s, dict)
                              and s.get("role") == "verified_document_quote"), None)
                row = next((s for s in sources if isinstance(s, dict)
                            and s.get("role") == "original_source_row"), None)
                if quote is None or row is None:
                    continue
                try:
                    qid, qrev = UUID(str(quote["document_id"])), UUID(str(quote["revision_id"]))
                except (KeyError, TypeError, ValueError, AttributeError):
                    continue
                trust = trusted.get(qid)
                if trust is None or trust.trusted is None or trust.trusted[0] != qrev:
                    continue
                original_quote, quote_sha = quote.get("source_quote"), quote.get("source_quote_sha256")
                if (not isinstance(original_quote, str) or not original_quote
                        or not isinstance(quote_sha, str)
                        or hashlib.sha256(original_quote.encode("utf-8")).hexdigest() != quote_sha):
                    continue
                # Source-chunk quotes must still exist verbatim in their
                # revision-stamped parsed text; a self-hash is not authority.
                if str(quote.get("source_locator") or "").startswith("chunk:"):
                    quote_key = (
                        str(quote["document_id"]), str(quote["revision_id"]),
                        str(quote["source_locator"]), original_quote, quote_sha,
                    )
                    if quote_key not in literal_authority:
                        continue
                key = (
                    str(row.get("document_id")), str(row.get("revision_id")),
                    str(row.get("source_locator")), str(row.get("blob_sha256")),
                    str(row.get("unit_sha256")),
                )
                if key not in canonical:
                    continue
                current.append({
                    "rule_id": item.get("rule_id"), "summary": item.get("summary"),
                    "state": "PROVISIONAL", "scored": False,
                    "requires_human_review": True,
                    "compared_values": item.get("compared_values") or {},
                    "sources": [quote, row],
                })
                if len(current) >= 25:
                    break
            if not current:
                raise SourceUnavailableError(
                    "No current trusted quote and canonical XLSX row pair remains; older findings are historical."
                )
            return {
                "event_id": str(event.event_id),
                "observed_at": event.occurred_at,
                "items": current,
            }

    async def load_alerts(self, project_id: UUID, tenant_id: UUID) -> list[Alert]:
        scoped = require_tenant_id(tenant_id)
        async with self._session_scope(tenant_id) as session:
            return await SqlAlchemyAlertRepository(session, scoped).list_for_project(project_id, scoped)

    async def load_hitl(self, project_id: UUID, tenant_id: UUID) -> HitlInput:
        scoped = require_tenant_id(tenant_id)
        async with self._session_scope(tenant_id) as session:
            repository = SqlAlchemyReviewQueueRepository(session=session, tenant_id=scoped)
            pending = 0
            items: list[Any] = []
            for status in AWAITING_DECISION_STATUSES:
                pending += await repository.count_by_status(status, project_id=project_id)
                items.extend(
                    await repository.list_by_status(
                        status,
                        skip=0,
                        limit=MAX_REVIEW_ITEMS_PER_STATUS,
                        project_id=project_id,
                    )
                )
            return HitlInput(items=items, pending_count=pending)

    async def load_budget(self, project_id: UUID, tenant_id: UUID) -> BudgetResponse:
        scoped = require_tenant_id(tenant_id)
        async with self._session_scope(tenant_id) as session:
            return await GetBudgetUseCase(SQLAlchemyBudgetRepository(session)).execute(project_id, scoped)

    async def load_wbs(self, project_id: UUID, tenant_id: UUID) -> WbsInput:
        # The live WBS rows (as GET /projects/{id}/wbs serves them), qualified by the project's WBS
        # authority (PC-2a.3): legacy rows are never reported as approved scope.
        scoped = require_tenant_id(tenant_id)
        async with self._session_scope(tenant_id) as session:
            repository = SQLAlchemyWBSRepository(session)
            authority, items = await WBSGovernanceRepository(session).read_with_authority(
                project_id, scoped, lambda: repository.get_by_project(project_id, scoped)
            )
            return WbsInput(items=items, authority=authority)

    async def load_stakeholders(self, project_id: UUID, tenant_id: UUID) -> StakeholdersInput:
        scoped = require_tenant_id(tenant_id)
        async with self._session_scope(tenant_id) as session:
            stakeholders, total = await ListProjectStakeholdersUseCase(
                SqlAlchemyStakeholderRepository(session)
            ).execute(project_id, scoped, limit=MAX_STAKEHOLDERS)
            return StakeholdersInput(stakeholders=list(stakeholders), total=total)

    async def load_raci(self, project_id: UUID, tenant_id: UUID) -> RaciMatrixViewResponse:
        scoped = require_tenant_id(tenant_id)
        async with self._session_scope(tenant_id) as session:
            use_case = GetRaciMatrixUseCase(
                stakeholder_repository=SqlAlchemyStakeholderRepository(session),
                wbs_repository=SQLAlchemyWBSRepository(session),
                project_repository=SQLAlchemyProjectRepository(session),
                wbs_authority_reader=WBSGovernanceRepository(session),
            )
            return await use_case.execute(project_id, scoped)


__all__ = [
    "AWAITING_DECISION_STATUSES",
    "COHERENCE_DISABLED_REASON",
    "MAX_DOCUMENTS",
    "MAX_STAKEHOLDERS",
    "SqlAlchemyCurrentStateSources",
]
