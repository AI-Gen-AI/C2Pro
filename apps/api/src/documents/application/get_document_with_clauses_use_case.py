"""
Use Case for retrieving a document with its clauses.

Lane C / C3a: the clauses are ONE revision's set -- the document's trusted-current
revision by default, or an explicitly requested historical revision. A historical
read never changes what is current.

Refers to Test Suite ID: TASK-OPS-DOCFLOW-009.
"""
from uuid import UUID

from fastapi import HTTPException, status

from src.core.tenants.types import require_tenant_id
from src.documents.domain.models import Document
from src.documents.ports.document_repository import IDocumentRepository
from src.temporal.ports.document_revision_repository import IDocumentRevisionRepository


class GetDocumentWithClausesUseCase:
    """Test Suite ID: TASK-OPS-DOCFLOW-009."""

    def __init__(
        self,
        document_repository: IDocumentRepository,
        revision_repository: IDocumentRevisionRepository | None = None,
    ):
        self.document_repository = document_repository
        self.revision_repository = revision_repository

    async def execute(
        self, tenant_id: UUID, document_id: UUID, revision_id: UUID | None = None
    ) -> Document:
        scoped_tenant_id = require_tenant_id(tenant_id)
        if revision_id is not None:
            await self._require_revision_of_document(scoped_tenant_id, document_id, revision_id)
        document = await self.document_repository.get_document_with_clauses(
            scoped_tenant_id,
            document_id,
            revision_id=revision_id,
        )
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        return document

    async def _require_revision_of_document(
        self, tenant_id: UUID, document_id: UUID, revision_id: UUID
    ) -> None:
        if self.revision_repository is None:
            from src.temporal.adapters.persistence.document_revision_repository import (
                SqlAlchemyDocumentRevisionRepository,
            )

            session = getattr(self.document_repository, "session", None)
            if session is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found."
                )
            self.revision_repository = SqlAlchemyDocumentRevisionRepository(session)
        revision = await self.revision_repository.get_by_id(revision_id, tenant_id)
        if revision is None or revision.document_id != document_id or revision.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found.")
