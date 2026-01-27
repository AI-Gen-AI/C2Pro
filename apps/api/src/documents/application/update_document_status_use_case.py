"""
Use Case for updating a document's processing status.
"""
from typing import Optional
from uuid import UUID

from src.documents.domain.models import DocumentStatus
from src.documents.ports.document_repository import IDocumentRepository

class UpdateDocumentStatusUseCase:
    def __init__(self, document_repository: IDocumentRepository):
        self.document_repository = document_repository

    async def execute(self, document_id: UUID, status: DocumentStatus, parsing_error: Optional[str] = None) -> None:
        """
        Updates the status for a document.
        """
        await self.document_repository.update_status(document_id, status, parsing_error)
        await self.document_repository.commit()
