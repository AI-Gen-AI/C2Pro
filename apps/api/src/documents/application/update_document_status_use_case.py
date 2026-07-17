"""
Use Case for updating a document's processing status.
"""
from uuid import UUID

from src.core.tenants.types import require_tenant_id
from src.documents.domain.models import DocumentStatus
from src.documents.ports.document_repository import IDocumentRepository


class UpdateDocumentStatusUseCase:
    def __init__(self, document_repository: IDocumentRepository):
        self.document_repository = document_repository

    async def execute(self, tenant_id: UUID, document_id: UUID, status: DocumentStatus, parsing_error: str | None = None) -> None:
        """
        Updates the status for a document.
        """
        await self.document_repository.update_status(
            require_tenant_id(tenant_id), document_id, status, parsing_error
        )
        await self.document_repository.commit()
