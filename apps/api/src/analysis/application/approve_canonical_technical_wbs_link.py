"""ACC-01 S7 explicit human approval of a canonical Technical -> WBS link.

The audit event technical.wbs_link_reviewed is deliberately insufficient.
This writer records a separate, explicit final human decision and re-validates
the source revision and approved WBS baseline inside the same transaction.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.application.record_technical_wbs_review import (
    REVIEW_EVENT,
    require_locked_trusted_artifact,
)
from src.core.auth.models import User, UserRole
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
from src.temporal.domain.project_event import ProjectEvent
from src.wbs.adapters.persistence.link_authority import require_linkable_wbs_nodes

CANONICAL_LINK_EVENT = "technical.wbs_link_approved"
CANONICAL_APPROVAL = "APPROVE_CANONICAL_LINK"


class CanonicalTechnicalWBSLinkError(ValueError):
    """Final association cannot be safely made current."""


@dataclass(frozen=True)
class CanonicalTechnicalWBSLinkResult:
    event_id: UUID
    replayed: bool
    technical_document_id: UUID
    technical_revision_id: UUID
    source_clause_id: UUID
    source_section: str
    source_start_offset: int
    source_end_offset: int
    wbs_baseline_id: UUID
    wbs_node_id: UUID


@dataclass
class ApproveCanonicalTechnicalWBSLinkService:
    """Persist one explicit, authenticated human approval."""

    session: AsyncSession

    async def execute(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        actor_user_id: UUID,
        review_event_id: UUID,
        expected_wbs_baseline_id: UUID,
        expected_wbs_node_id: UUID,
        approval: str,
        idempotency_key: str,
        reason: str,
    ) -> CanonicalTechnicalWBSLinkResult:
        if approval != CANONICAL_APPROVAL:
            raise CanonicalTechnicalWBSLinkError("explicit canonical approval is required")
        if not 8 <= len(idempotency_key) <= 128:
            raise CanonicalTechnicalWBSLinkError("invalid idempotency key")
        if not reason.strip() or len(reason.strip()) > 2000:
            raise CanonicalTechnicalWBSLinkError("a bounded human approval reason is required")

        locked_project = await self.session.scalar(
            text(
                "SELECT id FROM projects "
                "WHERE id = :project AND tenant_id = :tenant FOR UPDATE"
            ),
            {"project": project_id, "tenant": tenant_id},
        )
        if locked_project is None:
            raise CanonicalTechnicalWBSLinkError("project unavailable to this tenant")

        reviewer = await self.session.scalar(
            select(User.id).where(
                User.id == actor_user_id,
                User.tenant_id == tenant_id,
                User.is_active.is_(True),
                User.role.in_([UserRole.ADMIN, UserRole.USER]),
                User.clerk_user_id.is_not(None),
                User.clerk_user_id != "",
            )
        )
        if reviewer is None:
            raise CanonicalTechnicalWBSLinkError("authenticated human approver required")

        authority = await require_linkable_wbs_nodes(
            self.session,
            tenant_id=tenant_id,
            project_id=project_id,
            node_ids={expected_wbs_node_id},
        )
        if authority.baseline_id != expected_wbs_baseline_id:
            raise CanonicalTechnicalWBSLinkError("the approved WBS baseline changed")

        review = await self.session.scalar(
            select(ProjectEventORM)
            .where(
                ProjectEventORM.event_id == review_event_id,
                ProjectEventORM.tenant_id == tenant_id,
                ProjectEventORM.project_id == project_id,
                ProjectEventORM.event_type == REVIEW_EVENT,
            )
            .with_for_update(read=True)
        )
        if review is None:
            raise CanonicalTechnicalWBSLinkError("confirmed human review is required")

        payload = review.payload
        required = {
            "authority": "AUDIT_ONLY_NOT_CANONICAL_LINK",
            "technical_assessment": "NOT_ASSESSED",
            "decision": "CONFIRMED_FOR_REVIEW",
            "wbs_baseline_id": str(expected_wbs_baseline_id),
            "wbs_node_id": str(expected_wbs_node_id),
        }
        if any(payload.get(key) != value for key, value in required.items()):
            raise CanonicalTechnicalWBSLinkError("review does not authorize this canonical target")

        try:
            revision_id = UUID(str(payload["technical_revision_id"]))
            document_id = UUID(str(payload["technical_document_id"]))
            clause_id = UUID(str(payload["source_clause_id"]))
            source_hash = str(payload["source_blob_hash"])
            source_section = str(payload["source_section"])
            start_offset = int(payload["source_start_offset"])
            end_offset = int(payload["source_end_offset"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CanonicalTechnicalWBSLinkError("review provenance is incomplete") from exc

        revision = await SqlAlchemyDocumentRevisionRepository(self.session).get_by_id(
            revision_id, tenant_id
        )
        if (
            revision is None
            or revision.project_id != project_id
            or revision.document_id != document_id
            or revision.blob_hash != source_hash
        ):
            raise CanonicalTechnicalWBSLinkError("review source revision is stale")

        await require_locked_trusted_artifact(
            self.session,
            tenant_id=tenant_id,
            project_id=project_id,
            document_id=document_id,
            revision_id=revision_id,
        )
        current = await SqlAlchemyCurrentRevisionResolver(self.session).resolve(
            tenant_id=tenant_id, document_id=document_id
        )
        if current.status is not CurrentRevisionStatus.TRUSTED or current.revision_id != revision_id:
            raise CanonicalTechnicalWBSLinkError("review source revision is stale")

        identity = "|".join(
            str(value)
            for value in (
                tenant_id,
                project_id,
                revision_id,
                clause_id,
                expected_wbs_baseline_id,
                expected_wbs_node_id,
            )
        )
        candidate_key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        existing = (
            await self.session.execute(
                select(ProjectEventORM)
                .where(
                    ProjectEventORM.tenant_id == tenant_id,
                    ProjectEventORM.project_id == project_id,
                    ProjectEventORM.event_type == CANONICAL_LINK_EVENT,
                    ProjectEventORM.payload["candidate_key"].astext == candidate_key,
                )
                .order_by(ProjectEventORM.occurred_at)
            )
        ).scalars().first()
        if existing is not None:
            same = (
                existing.actor == f"user:{actor_user_id}"
                and existing.payload.get("idempotency_key") == idempotency_key
                and existing.payload.get("approval") == CANONICAL_APPROVAL
                and existing.payload.get("reason") == reason.strip()
                and existing.payload.get("review_event_id") == str(review_event_id)
            )
            if not same:
                raise CanonicalTechnicalWBSLinkError(
                    "this canonical technical WBS link was already settled"
                )
            return CanonicalTechnicalWBSLinkResult(
                event_id=existing.event_id,
                replayed=True,
                technical_document_id=document_id,
                technical_revision_id=revision_id,
                source_clause_id=clause_id,
                source_section=source_section,
                source_start_offset=start_offset,
                source_end_offset=end_offset,
                wbs_baseline_id=expected_wbs_baseline_id,
                wbs_node_id=expected_wbs_node_id,
            )

        now = datetime.now(UTC).replace(tzinfo=None)
        event = ProjectEvent(
            event_id=uuid4(),
            tenant_id=tenant_id,
            project_id=project_id,
            event_type=CANONICAL_LINK_EVENT,
            source_revision_id=revision_id,
            occurred_at=now,
            created_at=now,
            actor=f"user:{actor_user_id}",
            payload={
                "candidate_key": candidate_key,
                "review_event_id": str(review_event_id),
                "technical_document_id": str(document_id),
                "technical_revision_id": str(revision_id),
                "source_clause_id": str(clause_id),
                "source_section": source_section,
                "source_start_offset": start_offset,
                "source_end_offset": end_offset,
                "source_blob_hash": source_hash,
                "wbs_baseline_id": str(expected_wbs_baseline_id),
                "wbs_node_id": str(expected_wbs_node_id),
                "approval": CANONICAL_APPROVAL,
                "reason": reason.strip(),
                "idempotency_key": idempotency_key,
                "authority": "EXPLICIT_HUMAN_CANONICAL_LINK",
                "technical_assessment": "NOT_ASSESSED",
            },
        )
        await SqlAlchemyProjectEventRepository(self.session).append(event)
        return CanonicalTechnicalWBSLinkResult(
            event_id=event.event_id,
            replayed=False,
            technical_document_id=document_id,
            technical_revision_id=revision_id,
            source_clause_id=clause_id,
            source_section=source_section,
            source_start_offset=start_offset,
            source_end_offset=end_offset,
            wbs_baseline_id=expected_wbs_baseline_id,
            wbs_node_id=expected_wbs_node_id,
        )


__all__ = [
    "CANONICAL_APPROVAL",
    "CANONICAL_LINK_EVENT",
    "ApproveCanonicalTechnicalWBSLinkService",
    "CanonicalTechnicalWBSLinkError",
    "CanonicalTechnicalWBSLinkResult",
]
