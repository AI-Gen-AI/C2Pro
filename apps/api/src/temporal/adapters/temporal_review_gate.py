"""Database-backed temporal-review seam for the canonical approval gate (PR-C2).

Revision/artifact scoped: the caller names only the tenant, the document and
the revision the analysis run is pinned to. Read-only; RLS applies through the
tenant session.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from src.core.database import get_session_with_tenant
from src.documents.adapters.persistence.models import DocumentORM
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.application import temporal_review
from src.temporal.application.temporal_review import TemporalReviewDecision


async def revision_requires_temporal_review(
    *,
    tenant_id: UUID | str,
    document_id: UUID | str,
    revision_id: UUID | str,
) -> TemporalReviewDecision:
    tenant, document, revision = (
        UUID(str(tenant_id)),
        UUID(str(document_id)),
        UUID(str(revision_id)),
    )
    async with get_session_with_tenant(tenant) as session:
        document_type = (
            await session.execute(
                select(DocumentORM.document_type).where(
                    DocumentORM.id == document, DocumentORM.tenant_id == tenant
                )
            )
        ).scalar_one_or_none()
        return await temporal_review.revision_requires_temporal_review(
            revisions=SqlAlchemyDocumentRevisionRepository(session),
            events=SqlAlchemyProjectEventRepository(session),
            tenant_id=tenant,
            document_id=document,
            revision_id=revision,
            # Unknown document -> None -> a missing assessment fails closed.
            artifact_type=(
                str(getattr(document_type, "value", document_type))
                if document_type is not None
                else None
            ),
        )


__all__ = ["revision_requires_temporal_review"]
