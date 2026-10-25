"""ACC-01 S7: tenant-scoped *human decision* on a source-backed WBS mapping proposal.

A durable review fact is NOT a canonical WBS association, approved technical
requirement, or assessed score. There is deliberately no HTTP route or link
writer here. The caller owns one DB transaction and must inject a server-side
source reader that verifies the immutable revision bytes against blob_hash.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from io import BytesIO
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from docx import Document as DocxDocument
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.analysis.domain.budget_row_evidence import ApprovedWBSScope
from src.analysis.domain.technical_wbs_link_candidate import (
    TechnicalWBSLinkCandidate,
    preview_technical_wbs_link,
)
from src.core.auth.models import User, UserRole
from src.documents.adapters.parsers.docx_file_parser import DocxFileParser
from src.documents.adapters.persistence.models import ClauseORM, DocumentORM
from src.documents.application.document_source import read_verified_revision_file
from src.documents.domain.models import Clause, DocumentType
from src.documents.ports.storage_service import IStorageService
from src.temporal.adapters.persistence.current_revision_resolver import (
    SqlAlchemyCurrentRevisionResolver,
)
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.models import ProjectEventORM
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.domain.current_revision import CurrentRevisionStatus
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.project_event import ProjectEvent
from src.wbs.adapters.persistence.link_authority import require_linkable_wbs_nodes

REVIEW_EVENT = "technical.wbs_link_reviewed"


class TechnicalMappingDecision(StrEnum):
    CONFIRMED_FOR_REVIEW = "CONFIRMED_FOR_REVIEW"
    REJECTED = "REJECTED"


class TechnicalMappingReviewError(ValueError):
    """A proposed review is stale, unauthorized, inconsistent or already settled."""


class VerifiedTechnicalTextReader(Protocol):
    """SERVER-owned port: read immutable source bytes, verify SHA-256, parse exact text.

    Do not implement by reading mutable documents.document_metadata, allowing
    client-provided text, or a newer revision's parsed text.
    """

    async def read_verified_text(self, revision: DocumentRevision) -> str: ...


@dataclass(frozen=True)
class ImmutableDocxTechnicalTextReader:
    """Production source adapter: parse only content-addressed immutable DOCX bytes.

    Shares the worker's DOCX paragraph/table-cell order and join convention.
    No mutable document_metadata, unstamped RAG chunks or user text is trusted.
    PDF technical sources need a separate byte-verified adapter; fail closed.
    """

    storage: IStorageService

    async def read_verified_text(self, revision: DocumentRevision) -> str:
        if Path(revision.blob_key).suffix.lower() != ".docx":
            raise TechnicalMappingReviewError("technical source format is not supported for review")
        path = await self.storage.download_object(revision.blob_key)
        verified_bytes = await asyncio.to_thread(
            read_verified_revision_file, path, revision.blob_hash
        )
        return await asyncio.to_thread(self._parse, verified_bytes)

    @staticmethod
    def _parse(verified_bytes: bytes) -> str:
        doc = DocxDocument(BytesIO(verified_bytes))
        blocks = (text.strip() for text in DocxFileParser._iter_text_in_document_order(doc))
        return "\n\n".join(text for text in blocks if text)


@dataclass(frozen=True)
class TechnicalMappingReviewResult:
    event_id: UUID
    candidate: TechnicalWBSLinkCandidate
    decision: TechnicalMappingDecision
    replayed: bool


async def require_locked_trusted_artifact(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    project_id: UUID,
    document_id: UUID,
    revision_id: UUID,
) -> UUID:
    """Lock the exact active trusted artifact until the transaction commits.

    The trust writer's supersede-active UPDATE requires an incompatible row
    lock, so it cannot silently change the source while human review settles.
    PostgreSQL real-transaction tests must cover this lock, not only mocks.
    """
    artifact_id = await session.scalar(
        select(DocumentArtifactORM.artifact_id)
        .where(
            DocumentArtifactORM.tenant_id == tenant_id,
            DocumentArtifactORM.project_id == project_id,
            DocumentArtifactORM.document_id == document_id,
            DocumentArtifactORM.document_revision_id == revision_id,
            DocumentArtifactORM.trust_state == "trusted",
            DocumentArtifactORM.lifecycle_status == "active",
        )
        .with_for_update(read=True)
    )
    if artifact_id is None:
        raise TechnicalMappingReviewError("active trusted artifact is unavailable")
    return artifact_id


@dataclass
class RecordTechnicalWBSReviewService:
    session: AsyncSession
    source_reader: VerifiedTechnicalTextReader

    async def execute(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        actor_user_id: UUID,
        clause_id: UUID,
        expected_revision_id: UUID,
        expected_blob_hash: str,
        expected_wbs_baseline_id: UUID,
        proposed_wbs_node_id: UUID,
        decision: TechnicalMappingDecision,
        idempotency_key: str,
        reason: str,
    ) -> TechnicalMappingReviewResult:
        """Record one human decision atomically; caller commits its transaction.

        The project FOR UPDATE lock serializes competing decisions AND WBS
        baseline apply. All trust and WBS facts are re-read inside this lock.
        Idempotency works only for the exact same actor/decision/key; conflicting
        terminal decisions on the same source+baseline+node are refused.
        """
        if not isinstance(decision, TechnicalMappingDecision):
            raise TechnicalMappingReviewError("unknown human mapping decision")
        if not idempotency_key or not (8 <= len(idempotency_key) <= 128):
            raise TechnicalMappingReviewError("invalid idempotency key")
        if not reason or not reason.strip() or len(reason.strip()) > 2000:
            raise TechnicalMappingReviewError("a bounded human review reason is required")

        locked_project = await self.session.scalar(
            text(
                "SELECT id FROM projects "
                "WHERE id = :project AND tenant_id = :tenant FOR UPDATE"
            ),
            {"project": project_id, "tenant": tenant_id},
        )
        if locked_project is None:
            raise TechnicalMappingReviewError("project unavailable to this tenant")
        # Fail closed without revealing cross-tenant existence.
        if await self.session.scalar(
            select(User.id).where(
                User.id == actor_user_id,
                User.tenant_id == tenant_id,
                User.is_active.is_(True),
                User.is_verified.is_(True),
                User.role.in_([UserRole.ADMIN, UserRole.USER]),
                User.clerk_user_id.is_not(None),
                User.clerk_user_id != "",
            )
        ) is None:
            raise TechnicalMappingReviewError("authenticated human reviewer required")

        authority = await require_linkable_wbs_nodes(
            self.session,
            tenant_id=tenant_id,
            project_id=project_id,
            node_ids={proposed_wbs_node_id},
        )
        if authority.baseline_id is None or authority.baseline_id != expected_wbs_baseline_id:
            raise TechnicalMappingReviewError("the approved WBS baseline changed")

        source_clause = await self.session.scalar(
            select(ClauseORM)
            .join(
                DocumentORM,
                (DocumentORM.id == ClauseORM.document_id)
                & (DocumentORM.tenant_id == ClauseORM.tenant_id),
            )
            .where(
                ClauseORM.id == clause_id,
                ClauseORM.project_id == project_id,
                ClauseORM.tenant_id == tenant_id,
                ClauseORM.revision_id == expected_revision_id,
                DocumentORM.project_id == project_id,
                DocumentORM.document_type.in_(
                    [DocumentType.TECHNICAL_SPEC, DocumentType.SPECIFICATION]
                ),
            )
        )
        if source_clause is None:
            raise TechnicalMappingReviewError("technical clause or immutable revision not found")
        revision = await SqlAlchemyDocumentRevisionRepository(self.session).get_by_id(
            expected_revision_id, tenant_id
        )
        if (
            revision is None
            or revision.document_id != source_clause.document_id
            or revision.project_id != project_id
            or revision.blob_hash != expected_blob_hash
        ):
            raise TechnicalMappingReviewError("source revision does not match reviewed document")

        # Hold a PostgreSQL FOR SHARE lock on THIS active trusted artifact
        # until the caller commits. Every canonical trust promotion (HITL
        # commit_candidate or direct trusted save) must first UPDATE/supersede
        # the existing active trusted row, which conflicts with FOR SHARE.
        # A new trust promotion therefore cannot invalidate our verified
        # source mid-review. No schema or writer-policy change is needed.
        await require_locked_trusted_artifact(
            self.session,
            tenant_id=tenant_id,
            project_id=project_id,
            document_id=revision.document_id,
            revision_id=revision.revision_id,
        )
        current = await SqlAlchemyCurrentRevisionResolver(self.session).resolve(
            tenant_id=tenant_id, document_id=revision.document_id
        )
        if current.status is not CurrentRevisionStatus.TRUSTED:
            raise TechnicalMappingReviewError("technical document has no approved trusted revision")
        if current.revision_id != revision.revision_id:
            raise TechnicalMappingReviewError("technical document revision became stale")
        # This reader must return the exact text parsed from verified source
        # bytes of THIS revision. Never use an upload cache or supplied request.
        parsed = await self.source_reader.read_verified_text(revision)
        clause = Clause(
            id=source_clause.id,
            tenant_id=source_clause.tenant_id,
            project_id=source_clause.project_id,
            document_id=source_clause.document_id,
            revision_id=source_clause.revision_id,
            clause_code=source_clause.clause_code,
            clause_type=source_clause.clause_type,
            title=source_clause.title,
            full_text=source_clause.full_text,
            text_start_offset=source_clause.text_start_offset,
            text_end_offset=source_clause.text_end_offset,
            extracted_entities=source_clause.extracted_entities or {},
            extraction_confidence=source_clause.extraction_confidence,
            extraction_model=source_clause.extraction_model,
            manually_verified=source_clause.manually_verified,
            verified_at=source_clause.verified_at,
        )
        candidate = preview_technical_wbs_link(
            document_revision=revision,
            clause=clause,
            trusted_current_revision_id=current.revision_id,
            parsed_revision_text=parsed,
            actor_tenant_id=tenant_id,
            approved_wbs_scope=ApprovedWBSScope(
                tenant_id=tenant_id,
                project_id=project_id,
                baseline_id=authority.baseline_id,
                node_ids=frozenset({proposed_wbs_node_id}),
            ),
            proposed_wbs_node_id=proposed_wbs_node_id,
        )
        identity = "|".join(
            str(x)
            for x in (
                tenant_id,
                project_id,
                candidate.technical_revision_id,
                candidate.source_clause_id,
                candidate.proposed_wbs_baseline_id,
                candidate.proposed_wbs_node_id,
            )
        )
        candidate_key = hashlib.sha256(identity.encode("utf-8")).hexdigest()

        # Project row FOR UPDATE serializes every decision for this proposal;
        # replay is explicitly scoped to the actor/decision/key, not merely ID.
        existing = (
            await self.session.execute(
                select(ProjectEventORM)
                .where(
                    ProjectEventORM.tenant_id == tenant_id,
                    ProjectEventORM.project_id == project_id,
                    ProjectEventORM.event_type == REVIEW_EVENT,
                    ProjectEventORM.payload["candidate_key"].astext == candidate_key,
                )
                .order_by(ProjectEventORM.occurred_at)
            )
        ).scalars().first()
        if existing is not None:
            same = (
                existing.actor == f"user:{actor_user_id}"
                and existing.payload.get("idempotency_key") == idempotency_key
                and existing.payload.get("decision") == decision.value
                and existing.payload.get("reason") == reason.strip()
            )
            if not same:
                raise TechnicalMappingReviewError("this mapping proposal was already reviewed")
            return TechnicalMappingReviewResult(
                event_id=existing.event_id,
                candidate=candidate,
                decision=decision,
                replayed=True,
            )

        # project_events columns are TIMESTAMP WITHOUT TIME ZONE.
        now = datetime.now(UTC).replace(tzinfo=None)
        event = ProjectEvent(
            event_id=uuid4(),
            tenant_id=tenant_id,
            project_id=project_id,
            event_type=REVIEW_EVENT,
            source_revision_id=revision.revision_id,
            occurred_at=now,
            created_at=now,
            actor=f"user:{actor_user_id}",
            payload={
                "candidate_key": candidate_key,
                "technical_document_id": str(candidate.technical_document_id),
                "technical_revision_id": str(candidate.technical_revision_id),
                "source_clause_id": str(candidate.source_clause_id),
                "source_section": candidate.source_section,
                "source_start_offset": candidate.source_start_offset,
                "source_end_offset": candidate.source_end_offset,
                "source_blob_hash": candidate.source_blob_hash,
                "wbs_baseline_id": str(candidate.proposed_wbs_baseline_id),
                "wbs_node_id": str(candidate.proposed_wbs_node_id),
                "decision": decision.value,
                "reason": reason.strip(),
                "idempotency_key": idempotency_key,
                "authority": "AUDIT_ONLY_NOT_CANONICAL_LINK",
                "technical_assessment": "NOT_ASSESSED",
            },
        )
        await SqlAlchemyProjectEventRepository(self.session).append(event)
        return TechnicalMappingReviewResult(
            event_id=event.event_id,
            candidate=candidate,
            decision=decision,
            replayed=False,
        )
