"""S7 read projection of durable human-approved Technical→WBS associations.

Unlike the audit-only review feed, this projects ONLY explicit
technical.wbs_link_approved events. Historical approvals remain visible but
cannot claim CURRENT when the technical revision or approved WBS changes.

No mutation, migration, implied technical compliance, or score calculation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast
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

CanonicalLinkState = Literal["CURRENT", "STALE_SOURCE", "STALE_WBS", "STALE_BOTH", "UNVERIFIED"]


@dataclass(frozen=True)
class CanonicalTechnicalWBSLinkView:
    event_id: UUID
    review_event_id: UUID | None
    approved_at: datetime
    technical_document_id: UUID | None
    technical_revision_id: UUID | None
    source_clause_id: UUID | None
    source_section: str
    source_blob_hash: str
    wbs_baseline_id: UUID | None
    wbs_node_id: UUID | None
    wbs_code: str | None
    wbs_name: str | None
    state: CanonicalLinkState
    approved_canonical_link: bool = True
    technical_assessment: Literal["NOT_ASSESSED"] = "NOT_ASSESSED"


class CanonicalLinkReadError(ValueError):
    """Do not reveal an inaccessible project across tenants."""


def _uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except (TypeError, ValueError, AttributeError):
        return None


@dataclass
class ReadCanonicalTechnicalWBSLinksService:
    session: AsyncSession

    async def list(
        self, *, tenant_id: UUID, project_id: UUID, limit: int = 50
    ) -> list[CanonicalTechnicalWBSLinkView]:
        if not 1 <= limit <= 50:
            raise CanonicalLinkReadError("invalid query limit")
        # The key-share lock holds WBS authority stable against a concurrent
        # baseline apply (which takes FOR UPDATE) through this GET transaction.
        if await self.session.scalar(
            text("SELECT id FROM projects WHERE id = :p AND tenant_id = :t FOR KEY SHARE"),
            {"p": project_id, "t": tenant_id},
        ) is None:
            raise CanonicalLinkReadError("project not found")

        events = list(
            (await self.session.scalars(
                select(ProjectEventORM).where(
                    ProjectEventORM.tenant_id == tenant_id,
                    ProjectEventORM.project_id == project_id,
                    ProjectEventORM.event_type == CANONICAL_LINK_EVENT,
                )
                .order_by(ProjectEventORM.occurred_at.desc(), ProjectEventORM.event_id.desc())
                .limit(limit)
            )).all()
        )
        if not events:
            return []

        authority = await WBSGovernanceRepository(self.session).authority(project_id, tenant_id)
        baseline_id = authority.baseline_id if authority.approved else None
        current_nodes = {}
        if baseline_id is not None:
            current_nodes = {
                row.node_id: row
                for row in (await self.session.scalars(
                    select(WBSBaselineNodeORM).where(
                        WBSBaselineNodeORM.tenant_id == tenant_id,
                        WBSBaselineNodeORM.project_id == project_id,
                        WBSBaselineNodeORM.baseline_id == baseline_id,
                    )
                )).all()
            }

        entries: list[tuple[ProjectEventORM, UUID | None, UUID | None, UUID | None, UUID | None, UUID | None]] = []
        for event in events:
            p = event.payload or {}
            entries.append((
                event,
                _uuid(p.get("technical_document_id")),
                _uuid(p.get("technical_revision_id")),
                _uuid(p.get("source_clause_id")),
                _uuid(p.get("wbs_baseline_id")),
                _uuid(p.get("wbs_node_id")),
            ))
        # All current identities are derived from tenant-scoped persisted state,
        # never from event metadata, current UI selection or an audit-only event.
        resolver = SqlAlchemyCurrentRevisionResolver(self.session)
        output: list[CanonicalTechnicalWBSLinkView] = []
        for event, document_id, revision_id, clause_id, event_baseline, node_id in entries:
            p = event.payload or {}
            audit_id = _uuid(p.get("review_event_id"))
            hash_value = str(p.get("source_blob_hash") or "")
            section = str(p.get("source_section") or "")
            node = current_nodes.get(cast(UUID, node_id))
            wbs_current = baseline_id is not None and event_baseline == baseline_id and node is not None
            structurally_valid = bool(
                document_id and revision_id and clause_id and audit_id
                and event_baseline and node_id
                and re.fullmatch(r"[0-9a-f]{64}", hash_value) is not None
                and p.get("authority") == "EXPLICIT_HUMAN_CANONICAL_LINK"
                and p.get("approval") == CANONICAL_APPROVAL
                and p.get("technical_assessment") == "NOT_ASSESSED"
                and event.source_revision_id == revision_id
                and event.actor and event.actor.startswith("user:")
            )
            source_current = False
            if structurally_valid:
                # Exact revision and source clause must still belong to this
                # tenant/project and be the approved technical document type.
                revision = await self.session.scalar(
                    select(DocumentRevisionORM).where(
                        DocumentRevisionORM.revision_id == revision_id,
                        DocumentRevisionORM.document_id == document_id,
                        DocumentRevisionORM.tenant_id == tenant_id,
                        DocumentRevisionORM.project_id == project_id,
                        DocumentRevisionORM.blob_hash == hash_value,
                    )
                )
                original_clause = await self.session.scalar(
                    select(ClauseORM).join(
                        DocumentORM,
                        (DocumentORM.id == ClauseORM.document_id)
                        & (DocumentORM.tenant_id == ClauseORM.tenant_id),
                    ).where(
                        ClauseORM.id == clause_id,
                        ClauseORM.tenant_id == tenant_id,
                        ClauseORM.project_id == project_id,
                        ClauseORM.document_id == document_id,
                        ClauseORM.revision_id == revision_id,
                        DocumentORM.project_id == project_id,
                        DocumentORM.document_type.in_(
                            [DocumentType.TECHNICAL_SPEC, DocumentType.SPECIFICATION]
                        ),
                    )
                )
                # The same clause ID is insufficient: persisted extracted source
                # identity (section, offsets and deterministic extractor) must
                # still equal the exact approved event. A re-index or tampered
                # clause cannot silently keep an obsolete link CURRENT.
                tech_metadata = (
                    (original_clause.extracted_entities or {}).get("technical_requirement")
                    if original_clause is not None
                    else None
                )
                clause_matches = bool(
                    original_clause is not None
                    and original_clause.extraction_model == "deterministic-technical-section-v1"
                    and isinstance(tech_metadata, dict)
                    and tech_metadata.get("source_section") == section
                    and original_clause.text_start_offset == p.get("source_start_offset")
                    and original_clause.text_end_offset == p.get("source_end_offset")
                    and original_clause.full_text
                )
                audit_event = await self.session.scalar(
                    select(ProjectEventORM).where(
                        ProjectEventORM.event_id == audit_id,
                        ProjectEventORM.tenant_id == tenant_id,
                        ProjectEventORM.project_id == project_id,
                        ProjectEventORM.event_type == REVIEW_EVENT,
                    )
                )
                # FOR SHARE conflicts with superseding the exact active trusted
                # artifact while the API decides whether the link is current.
                active_trust = await self.session.scalar(
                    select(DocumentArtifactORM.artifact_id).where(
                        DocumentArtifactORM.tenant_id == tenant_id,
                        DocumentArtifactORM.project_id == project_id,
                        DocumentArtifactORM.document_id == document_id,
                        DocumentArtifactORM.document_revision_id == revision_id,
                        DocumentArtifactORM.trust_state == "trusted",
                        DocumentArtifactORM.lifecycle_status == "active",
                    ).with_for_update(read=True)
                )
                # Resolve the canonical revision AFTER acquiring an artifact
                # SHARE lock: a concurrent trust promotion cannot invalidate
                # this projection between status checks.
                resolved = await resolver.resolve(
                    tenant_id=tenant_id, document_id=cast(UUID, document_id)
                ) if active_trust is not None else None
                audit_matches = bool(
                    audit_event is not None
                    and audit_event.payload.get("authority") == "AUDIT_ONLY_NOT_CANONICAL_LINK"
                    and audit_event.payload.get("decision") == "CONFIRMED_FOR_REVIEW"
                    and audit_event.payload.get("technical_document_id") == str(document_id)
                    and audit_event.payload.get("technical_revision_id") == str(revision_id)
                    and audit_event.payload.get("source_clause_id") == str(clause_id)
                    and audit_event.payload.get("source_blob_hash") == hash_value
                    and audit_event.payload.get("source_section") == section
                    and audit_event.payload.get("source_start_offset") == p.get("source_start_offset")
                    and audit_event.payload.get("source_end_offset") == p.get("source_end_offset")
                    and audit_event.payload.get("wbs_baseline_id") == str(event_baseline)
                    and audit_event.payload.get("wbs_node_id") == str(node_id)
                )
                source_current = bool(
                    revision is not None and clause_matches
                    and audit_matches and active_trust is not None
                    and resolved is not None
                    and resolved.status is CurrentRevisionStatus.TRUSTED
                    and resolved.revision_id == revision_id
                )
            if not structurally_valid:
                state: CanonicalLinkState = "UNVERIFIED"
            elif source_current and wbs_current:
                state = "CURRENT"
            elif not source_current and not wbs_current:
                state = "STALE_BOTH"
            elif not source_current:
                state = "STALE_SOURCE"
            else:
                state = "STALE_WBS"
            output.append(CanonicalTechnicalWBSLinkView(
                event_id=event.event_id,
                review_event_id=audit_id,
                approved_at=event.occurred_at,
                technical_document_id=document_id,
                technical_revision_id=revision_id,
                source_clause_id=clause_id,
                source_section=section,
                source_blob_hash=hash_value,
                wbs_baseline_id=event_baseline,
                wbs_node_id=node_id,
                wbs_code=node.code if node is not None and wbs_current else None,
                wbs_name=node.name if node is not None and wbs_current else None,
                state=state,
            ))
        return output


__all__ = [
    "CanonicalLinkReadError",
    "CanonicalTechnicalWBSLinkView",
    "ReadCanonicalTechnicalWBSLinksService",
]
