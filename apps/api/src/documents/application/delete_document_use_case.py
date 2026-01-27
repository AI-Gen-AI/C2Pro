"""
Use Case for deleting a document and its associated file.
"""
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status

from src.documents.ports.document_repository import IDocumentRepository
from src.documents.ports.storage_service import IStorageService
from src.documents.application.get_document_use_case import GetDocumentUseCase # Reuse use case

class DeleteDocumentUseCase:
    def __init__(
        self,
        document_repository: IDocumentRepository,
        storage_service: IStorageService,
        get_document_use_case: GetDocumentUseCase,
    ):
        self.document_repository = document_repository
        self.storage_service = storage_service
        self.get_document_use_case = get_document_use_case

    async def execute(self, document_id: UUID, user_id: UUID) -> None:
        """
        Deletes a document record and its associated file from storage.
        """
        document = await self.get_document_use_case.execute(document_id, user_id)

        # Assuming storage_url will be based on document.id and its extension
        file_name_in_storage = f"{document.id}{Path(document.filename).suffix}"

        try:
            await self.storage_service.delete_file(file_name_in_storage)
        except Exception as e:
            # Log error but proceed with DB deletion if file delete fails
            # or handle more gracefully based on business rules
            print(f"Warning: Failed to delete file {file_name_in_storage} from storage: {e}")
            # raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete file from storage: {e}")

        await self.document_repository.delete(document_id)
        await self.document_repository.commit()
