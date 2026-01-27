"""
Use Case for updating a document's storage path.
"""
from uuid import UUID

from src.documents.ports.document_repository import IDocumentRepository

class UpdateDocumentStoragePathUseCase:
    def __init__(self, document_repository: IDocumentRepository):
        self.document_repository = document_repository

    async def execute(self, document_id: UUID, storage_url: str) -> None:
        """
        Updates the storage_url for a document.
        """
        await self.document_repository.update_storage_path(document_id, storage_url)
        await self.document_repository.commit()
