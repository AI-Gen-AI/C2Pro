"""
Use Case for retrieving a document with its clauses.
"""
from uuid import UUID

from fastapi import HTTPException, status

from src.documents.domain.models import Document
from src.documents.ports.document_repository import IDocumentRepository


class GetDocumentWithClausesUseCase:
    def __init__(self, document_repository: IDocumentRepository):
        self.document_repository = document_repository

    async def execute(self, document_id: UUID) -> Document:
        document = await self.document_repository.get_document_with_clauses(document_id)
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        return document
