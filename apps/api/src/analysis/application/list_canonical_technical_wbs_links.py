"""S7: read-only, authority-aware projection of explicit Technical→WBS approvals.

An immutable approval event is a historical fact. It is a *current* canonical
association only while its original technical revision, extracted source clause,
trusted artifact and approved WBS baseline/node still match. This reader never
grants new approval, mutates Health or treats audit-only events as canonical.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.analysis.application.approve_canonical_technical_wbs_link import (
    CANONICAL_APPROVAL,
    CANONICAL_LINK_EVENT,
)
from src.analysis.application.record_technical_wbs_review import REVIEW_EVENT
from src.documents.adapters.persistence.models import ClauseORM, DocumentORM
from src.documents.domain.models import DocumentType
from src.temporal.adapters.persistence.current_revision_resolver import (
    SqlAlchemyCurrentRevisionResolver,
)
from src.temporal.adapters.persistence.models import DocumentRevisionORM, ProjectEventORM
from src.temporal.domain.current_revision import CurrentRevisionStatus
from src.wbs.adapters.persistence.governance_models import WBSBaselineNodeORM
from src.wbs.adapters.persistence.governance_repository import WBSGovernanceRepository
from src.wbs.adapters.persistence.models import WBSNodeORM

CurrentLinkState = Literal["CURRENT_VERIFIED", "HISTORICAL_NOT_CURRENT"]


class CanonicalLinkProjectNotFound(LookupError):
    """Do not reveal whether a project belongs to a different tenant."""


@dataclass(frozen=True)
class CanonicalTechnicalWBSLinkView:
    event_id: UUID
    occurred_at: datetime
    review_event_id: UUID
    technical_document_id: UUID
    technical_revision_id: UUID
    source_clause_id: UUID
    source_section: str
    wbs_baseline_id: UUID
    wbs_node_id: UUID
    current_state: CurrentLinkState
    state_reason: str
    approval: Literal["APPROVE_CANONICAL_LINK"] = CANONICAL_APPROVAL
    authority: Literal["EXPLICIT_HUMAN_CANONICAL_LINK"] = "EXPLICIT_HUMAN_CANONICAL_LINK"
    technical_assessment: Literal["NOT_ASSESSED"] = "NOT_ASSESSED"


@dataclass(frozen=True)
class _Candidate:
    event: ProjectEventORM
    review_event_id: UUID
    document_id: UUID
    revision_id: UUID
    clause_id: UUID
    baseline_id: UUID
    node_id: UUID
    section: str
    blob_hash: str


def _candidate(event: ProjectEventORM) -> _Candidate | None:
    """Ignore malformed or forged event payloads rather than granting authority."""
    data = event.payload
    if (
        not isinstance(data, dict)
        or data.get("authority") != "EXPLICIT_HUMAN_CANONICAL_LINK"
        or data.get("approval") != CANONICAL_APPROVAL
        or data.get("technical_assessment") != "NOT_ASSESSED"
        or not (event.actor or "").startswith("user:")
    ):
        return None
    try:
        candidate = _Candidate(
            event=event,
            review_event_id=UUID(str(data["review_event_id"])),
            document_id=UUID(str(data["technical_document_id"])),
            revision_id=UUID(str(data["technical_revision_id"])),
            clause_id=UUID(str(data["source_clause_id"])),
            baseline_id=UUID(str(data["wbs_baseline_id"])),
            node_id=UUID(str(data["wbs_node_id"])),
            section=str(data["source_section"]),
            blob_hash=str(data["source_blob_hash"]),
        )
    except (KeyError, TypeError, ValueError):
        return None
    if (
        event.source_revision_id != candidate.revision_id
        or len(candidate.blob_hash) != 64
        or any(c not in "0123456789abcdef" for c in candidate.blob_hash)
        or not candidate.section.strip()
    ):
        return None
    return candidate


@dataclass
class ListCanonicalTechnicalWBSLinksService:
    session: AsyncSession

    async def execute(
        self, *, tenant_id: UUID, project_id: UUID, limit: int = 50,
    ) -> list[CanonicalTechnicalWBSLinkView]:
        """List the tenant's approved events with present-day trust verdicts.

        The project KEY SHARE prevents a governed WBS apply (FOR UPDATE) from
        changing its baseline while this transaction reads the node projection.
        No UPDATE/INSERT/DELETE or lock on another tenant is ever issued.
        """
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        owned = await self.session.scalar(
            text(
                "SELECT id FROM projects WHERE id = :project "
                "AND tenant_id = :tenant FOR KEY SHARE"
            ),
            {"project": project_id, "tenant": tenant_id},
        )
        if owned is None:
            raise CanonicalLinkProjectNotFound()

        rows = (
            await self.session.scalars(
                select(ProjectEventORM).where(
                    ProjectEventORM.tenant_id == tenant_id,
                    ProjectEventORM.project_id == project_id,
                    ProjectEventORM.event_type == CANONICAL_LINK_EVENT,
                ).order_by(
                    ProjectEventORM.occurred_at.desc(), ProjectEventORM.event_id.desc(),
                ).limit(limit)
            )
        ).all()
        candidates = [candidate for event in rows if (candidate := _candidate(event)) is not None]
        if not candidates:
            return []

        authority = await WBSGovernanceRepository(self.session).authority(project_id, tenant_id)
        current_baseline_id = authority.baseline_id if authority.approved else None

        node_ids = {entry.node_id for entry in candidates}
        live_nodes: set[UUID] = set()
        if current_baseline_id is not None:
            live_nodes = set(
                (await self.session.scalars(
                    select(WBSBaselineNodeORM.node_id)
                    .join(
                        WBSNodeORM,
                        (WBSNodeORM.id == WBSBaselineNodeORM.node_id)
                        & (WBSNodeORM.tenant_id == WBSBaselineNodeORM.tenant_id)
                        & (WBSNodeORM.project_id == WBSBaselineNodeORM.project_id),
                    )
                    .where(
                        WBSBaselineNodeORM.tenant_id == tenant_id,
                        WBSBaselineNodeORM.project_id == project_id,
                        WBSBaselineNodeORM.baseline_id == current_baseline_id,
                        WBSBaselineNodeORM.node_id.in_(node_ids),
                    )
                )).all()
            )

        revision_ids = {entry.revision_id for entry in candidates}
        document_ids = {entry.document_id for entry in candidates}
        clause_ids = {entry.clause_id for entry in candidates}
        review_ids = {entry.review_event_id for entry in candidates}
        revisions = {
            row.revision_id: row
            for row in (await self.session.scalars(
                select(DocumentRevisionORM).where(
                    DocumentRevisionORM.tenant_id == tenant_id,
                    DocumentRevisionORM.project_id == project_id,
                    DocumentRevisionORM.revision_id.in_(revision_ids),
                )
            )).all()
        }
        documents = {
            row.id: row
            for row in (await self.session.scalars(
                select(DocumentORM).where(
                    DocumentORM.tenant_id == tenant_id,
                    DocumentORM.project_id == project_id,
                    DocumentORM.id.in_(document_ids),
                )
            )).all()
        }
        clauses = {
            row.id: row
            for row in (await self.session.scalars(
                select(ClauseORM).where(
                    ClauseORM.tenant_id == tenant_id,
                    ClauseORM.project_id == project_id,
                    ClauseORM.id.in_(clause_ids),
                )
            )).all()
        }
        trusted_artifacts = {
            (row.document_id, row.document_revision_id)
            for row in (await self.session.scalars(
                select(DocumentArtifactORM).where(
                    DocumentArtifactORM.tenant_id == tenant_id,
                    DocumentArtifactORM.project_id == project_id,
                    DocumentArtifactORM.document_id.in_(document_ids),
                    DocumentArtifactORM.document_revision_id.in_(revision_ids),
                    DocumentArtifactORM.trust_state == "trusted",
                    DocumentArtifactORM.lifecycle_status == "active",
                ).with_for_update(read=True)
            )).all()
        }
        reviews = {
            row.event_id: row
            for row in (await self.session.scalars(
                select(ProjectEventORM).where(
                    ProjectEventORM.tenant_id == tenant_id,
                    ProjectEventORM.project_id == project_id,
                    ProjectEventORM.event_type == REVIEW_EVENT,
                    ProjectEventORM.event_id.in_(review_ids),
                )
            )).all()
        }
        current = await SqlAlchemyCurrentRevisionResolver(self.session).resolve_many(
            tenant_id=tenant_id, document_ids=document_ids,
        )

        result: list[CanonicalTechnicalWBSLinkView] = []
        for candidate in candidates:
            doc = documents.get(candidate.document_id)
            revision = revisions.get(candidate.revision_id)
            clause = clauses.get(candidate.clause_id)
            audit = reviews.get(candidate.review_event_id)
            current_revision = current.get(candidate.document_id)
            # Do not infer current authority from a bare historical approval.
            reason = "CURRENT_VERIFIED"
            if (
                not authority.approved
                or current_baseline_id != candidate.baseline_id
                or candidate.node_id not in live_nodes
            ):
                reason = "WBS_AUTHORITY_CHANGED"
            elif (
                doc is None
                or doc.document_type not in {DocumentType.TECHNICAL_SPEC, DocumentType.SPECIFICATION}
                or revision is None
                or revision.document_id != candidate.document_id
                or revision.blob_hash != candidate.blob_hash
            ):
                reason = "TECHNICAL_SOURCE_CHANGED"
            elif (
                current_revision is None
                or current_revision.status is not CurrentRevisionStatus.TRUSTED
                or current_revision.revision_id != candidate.revision_id
                or (candidate.document_id, candidate.revision_id) not in trusted_artifacts
            ):
                reason = "TECHNICAL_REVISION_NOT_TRUSTED"
            elif (
                clause is None
                or clause.document_id != candidate.document_id
                or clause.revision_id != candidate.revision_id
                or clause.extraction_model != "deterministic-technical-section-v1"
                or (
                    (clause.extracted_entities or {}).get("technical_requirement") or {}
                ).get("source_section") != candidate.section
            ):
                reason = "SOURCE_CLAUSE_NOT_VERIFIED"
            elif (
                audit is None
                or audit.payload.get("authority") != "AUDIT_ONLY_NOT_CANONICAL_LINK"
                or audit.payload.get("decision") != "CONFIRMED_FOR_REVIEW"
                or audit.payload.get("technical_revision_id") != str(candidate.revision_id)
                or audit.payload.get("source_clause_id") != str(candidate.clause_id)
                or audit.payload.get("wbs_baseline_id") != str(candidate.baseline_id)
                or audit.payload.get("wbs_node_id") != str(candidate.node_id)
            ):
                reason = "ORIGINAL_HUMAN_AUDIT_UNAVAILABLE"

            result.append(CanonicalTechnicalWBSLinkView(
                event_id=candidate.event.event_id,
                occurred_at=candidate.event.occurred_at,
                review_event_id=candidate.review_event_id,
                technical_document_id=candidate.document_id,
                technical_revision_id=candidate.revision_id,
                source_clause_id=candidate.clause_id,
                source_section=candidate.section,
                wbs_baseline_id=candidate.baseline_id,
                wbs_node_id=candidate.node_id,
                current_state=(
                    "CURRENT_VERIFIED" if reason == "CURRENT_VERIFIED" else "HISTORICAL_NOT_CURRENT"
                ),
                state_reason=reason,
            ))
        return result
