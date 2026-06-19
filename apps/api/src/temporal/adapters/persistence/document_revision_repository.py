"""SqlAlchemyDocumentRevisionRepository (ADR-015 / TASK-V3-015-01).

LOCKED INVARIANT: NEVER call session commit(). The use case owns the transaction.
Enforced by tests/unit/temporal/test_no_commit_in_revision_repository.py.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.temporal.adapters.persistence.models import DocumentRevisionORM
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.ports.document_revision_repository import IDocumentRevisionRepository

logger = structlog.get_logger()


class SqlAlchemyDocumentRevisionRepository(IDocumentRevisionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(orm: DocumentRevisionORM) -> DocumentRevision:
        return DocumentRevision(
            revision_id=orm.revision_id,
            document_id=orm.document_id,
            project_id=orm.project_id,
            tenant_id=orm.tenant_id,
            rev_no=orm.rev_no,
            parent_revision_id=orm.parent_revision_id,
            blob_hash=orm.blob_hash,
            blob_key=orm.blob_key,
            valid_from=orm.valid_from,
            valid_to=orm.valid_to,
            created_at=orm.created_at,
        )

    async def get_current(
        self, document_id: UUID, tenant_id: UUID
    ) -> DocumentRevision | None:
        result = await self._session.execute(
            select(DocumentRevisionORM).where(
                DocumentRevisionORM.document_id == document_id,
                DocumentRevisionORM.tenant_id == tenant_id,
                DocumentRevisionORM.valid_to.is_(None),
            )
        )
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def list_lineage(
        self, document_id: UUID, tenant_id: UUID
    ) -> list[DocumentRevision]:
        result = await self._session.execute(
            select(DocumentRevisionORM)
            .where(
                DocumentRevisionORM.document_id == document_id,
                DocumentRevisionORM.tenant_id == tenant_id,
            )
            .order_by(DocumentRevisionORM.rev_no.asc())
        )
        return [self._to_domain(orm) for orm in result.scalars().all()]

    async def append_revision(self, rev: DocumentRevision) -> DocumentRevision:
        orm = DocumentRevisionORM(
            revision_id=rev.revision_id,
            document_id=rev.document_id,
            project_id=rev.project_id,
            tenant_id=rev.tenant_id,
            rev_no=rev.rev_no,
            parent_revision_id=rev.parent_revision_id,
            blob_hash=rev.blob_hash,
            blob_key=rev.blob_key,
            valid_from=rev.valid_from,
            valid_to=rev.valid_to,
            created_at=rev.created_at,
        )
        self._session.add(orm)
        await self._session.flush()
        return rev

    async def close_current(
        self, document_id: UUID, tenant_id: UUID, valid_to: datetime
    ) -> None:
        await self._session.execute(
            update(DocumentRevisionORM)
            .where(
                DocumentRevisionORM.document_id == document_id,
                DocumentRevisionORM.tenant_id == tenant_id,
                DocumentRevisionORM.valid_to.is_(None),
            )
            .values(valid_to=valid_to)
        )
        await self._session.flush()
