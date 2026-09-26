"""
Use Case for downloading a document file.

P0b: serves the immutable object of the document's current revision (hash-verified);
only a document without revision lineage falls back to its legacy object.
"""
from mimetypes import guess_type  # From original service
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status

from src.documents.application.document_source import fetch_source_file, resolve_source_revision
from src.documents.application.get_document_use_case import GetDocumentUseCase  # Reuse use case
from src.documents.ports.document_repository import IDocumentRepository
from src.documents.ports.storage_service import IStorageService
from src.temporal.ports.document_revision_repository import IDocumentRevisionRepository


class DownloadDocumentUseCase:
    def __init__(
        self,
        document_repository: IDocumentRepository,
        storage_service: IStorageService,
        get_document_use_case: GetDocumentUseCase,
        revision_repository: IDocumentRevisionRepository | None = None,
    ):
        self.document_repository = document_repository
        self.storage_service = storage_service
        self.get_document_use_case = get_document_use_case
        self.revision_repository = revision_repository

    async def execute(self, document_id: UUID, user_id: UUID, tenant_id: UUID) -> tuple[Path, str]:
        """
        Retrieves the actual file from storage for a given document.
        Enforces security by checking document ownership via tenant_id.
        Returns file path and media type.
        """
        document = await self.get_document_use_case.execute(document_id, user_id, tenant_id)

        try:
            revision = (
                await resolve_source_revision(
                    revision_repository=self.revision_repository,
                    document_id=document.id,
                    tenant_id=document.tenant_id,
                    revision_id=None,
                )
                if self.revision_repository is not None
                else None
            )
            file_path = await fetch_source_file(
                storage=self.storage_service, document=document, revision=revision
            )
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
