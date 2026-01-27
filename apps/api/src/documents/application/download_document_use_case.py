"""
Use Case for downloading a document file.
"""
from pathlib import Path
from uuid import UUID
from mimetypes import guess_type # From original service

from fastapi import HTTPException, status

from src.documents.ports.document_repository import IDocumentRepository
from src.documents.ports.storage_service import IStorageService
from src.documents.application.get_document_use_case import GetDocumentUseCase # Reuse use case

class DownloadDocumentUseCase:
    def __init__(
        self,
        document_repository: IDocumentRepository,
        storage_service: IStorageService,
        get_document_use_case: GetDocumentUseCase,
    ):
        self.document_repository = document_repository
        self.storage_service = storage_service
        self.get_document_use_case = get_document_use_case

    async def execute(self, document_id: UUID, user_id: UUID) -> tuple[Path, str]:
        """
        Retrieves the actual file from storage for a given document.
        Enforces security by checking document ownership via tenant_id.
        Returns file path and media type.
        """
        document = await self.get_document_use_case.execute(document_id, user_id)

        # Assuming storage_url will be based on document.id and its extension
        file_name_in_storage = f"{document.id}{Path(document.filename).suffix}"

        try:
            file_path = await self.storage_service.download_file(file_name_in_storage)
            media_type, _ = guess_type(document.filename)
            if not media_type:
                media_type = "application/octet-stream"
            return file_path, media_type
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File content not found in storage."
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to download file: {e}",
            )
