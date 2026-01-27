"""
Use Case for retrieving a single document.
"""
from uuid import UUID

from fastapi import HTTPException, status

from src.documents.domain.models import Document
from src.documents.ports.document_repository import IDocumentRepository

class GetDocumentUseCase:
    def __init__(self, document_repository: IDocumentRepository):
        self.document_repository = document_repository

    async def execute(self, document_id: UUID, user_id: UUID) -> Document: # user_id for potential audit/permissions
        """
        Retrieves a document record from the database.
        """
        document = await self.document_repository.get_by_id(document_id)

        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        # In a real scenario, implement authorization logic here:
        # Check if user_id has permission to access this document/project.
        # For now, relying on tenant_id isolation in the repository and project link.
        
        return document
