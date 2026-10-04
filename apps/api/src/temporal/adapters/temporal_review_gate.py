"""Database-backed temporal-review seam for the canonical approval gate (PR-C2).

Revision/artifact scoped: the caller names only the tenant, the document and
the revision the analysis run is pinned to. Read-only; RLS applies through the
tenant session.
"""

from __future__ import annotations

from uuid import UUID

from src.core.database import get_session_with_tenant
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
        return await temporal_review.revision_requires_temporal_review(
            revisions=SqlAlchemyDocumentRevisionRepository(session),
            events=SqlAlchemyProjectEventRepository(session),
            tenant_id=tenant,
            document_id=document,
            revision_id=revision,
        )


__all__ = ["revision_requires_temporal_review"]
