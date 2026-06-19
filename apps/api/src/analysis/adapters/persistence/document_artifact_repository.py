"""SQLAlchemy DocumentArtifact repository (ADR-017 / TASK-V3-017-03).

TS-INT-ADR017-ART-001

LOCKED INVARIANT: repository methods never call commit().
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.ports.document_artifact_repository import IDocumentArtifactRepository


class SqlAlchemyDocumentArtifactRepository(IDocumentArtifactRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _artifact_document_id(artifact: DocumentArtifact) -> UUID:
        return UUID(artifact.document_id)

    @staticmethod
    def _artifact_revision_id(artifact: DocumentArtifact) -> UUID | None:
        if artifact.document_revision_id is None:
            return None
        return UUID(artifact.document_revision_id)

    async def save(
        self,
        artifact: DocumentArtifact,
        *,
        project_id: UUID,
        tenant_id: UUID,
    ) -> DocumentArtifact:
        document_id = self._artifact_document_id(artifact)
        await self._session.execute(
            update(DocumentArtifactORM)
            .where(
                DocumentArtifactORM.document_id == document_id,
                DocumentArtifactORM.lifecycle_status == "active",
            )
            .values(lifecycle_status="superseded")
        )
        self._session.add(
            DocumentArtifactORM(
                document_id=document_id,
                document_revision_id=self._artifact_revision_id(artifact),
                project_id=project_id,
                tenant_id=tenant_id,
                payload=artifact.model_dump(mode="json"),
                lifecycle_status="active",
            )
        )
        await self._session.flush()
        return artifact

    async def list_active_for_project(
        self,
        *,
        project_id: UUID,
        tenant_id: UUID,
    ) -> list[DocumentArtifact]:
        result = await self._session.execute(
            select(DocumentArtifactORM)
            .where(
                DocumentArtifactORM.project_id == project_id,
                DocumentArtifactORM.tenant_id == tenant_id,
                DocumentArtifactORM.lifecycle_status == "active",
            )
            .order_by(DocumentArtifactORM.created_at.asc())
        )
        return [
            DocumentArtifact.model_validate(orm.payload)
            for orm in result.scalars().all()
        ]


__all__ = ["SqlAlchemyDocumentArtifactRepository"]
