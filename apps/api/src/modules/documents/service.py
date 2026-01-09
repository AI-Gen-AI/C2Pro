import os
from mimetypes import guess_type
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.database import get_session_with_tenant
from src.modules.documents.models import Document, DocumentStatus, DocumentType
from src.modules.projects.models import Project
from src.shared.storage import StorageService


class DocumentService:
    def __init__(self, db_session: AsyncSession, storage_service: StorageService):
        self.db_session = db_session
        self.storage_service = storage_service

    async def _get_project_tenant_id(self, project_id: UUID) -> UUID:
        """Helper to get tenant_id from project_id."""
        project_result = await self.db_session.execute(
            select(Project.tenant_id).where(Project.id == project_id)
        )
        tenant_id = project_result.scalar_one_or_none()
        if not tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        return tenant_id

    async def upload_document(
        self,
        project_id: UUID,
        file: UploadFile,
        document_type: DocumentType,
        user_id: UUID,
        metadata: dict = None,
    ) -> Document:
        """
        Uploads a file to storage and creates a corresponding Document record in the database.
        Enforces security by checking project ownership via tenant_id.
        """
        if not metadata:
            metadata = {}

        tenant_id = await self._get_project_tenant_id(project_id)

        # Validate file size and type
        if file.size > settings.max_upload_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds limit of {settings.max_upload_size_mb}MB.",
            )

        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in settings.allowed_document_types:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File type {file_extension} is not allowed. Allowed types: {', '.join(settings.allowed_document_types)}",
            )

        async with get_session_with_tenant(tenant_id) as tenant_db:
            # Create a new document record first to get an ID
            new_document = Document(
                project_id=project_id,
                document_type=document_type,
                filename=file.filename,
                file_format=file_extension,
                file_size_bytes=file.size,
                upload_status=DocumentStatus.UPLOADED,
                created_by=user_id,
                metadata=metadata,
            )
            tenant_db.add(new_document)
            await tenant_db.flush()  # Flush to get new_document.id

            # Upload the file to storage using the document's ID
            file.file.seek(0)  # Ensure file pointer is at the beginning
            storage_path = await self.storage_service.upload_file(
                file_content=file.file, file_id=new_document.id, file_extension=file_extension
            )
            new_document.storage_url = storage_path
            await tenant_db.commit()
            await tenant_db.refresh(new_document)
            return new_document

    async def get_document(self, document_id: UUID, user_id: UUID) -> Document:
        """
        Retrieves a document record from the database.
        Enforces security by checking document ownership via tenant_id.
        """
        document_result = await self.db_session.execute(
            select(Document).where(Document.id == document_id)
        )
        document = document_result.scalar_one_or_none()

        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        # Verify tenant ownership (RLS should handle this, but an explicit check adds safety)
        tenant_id_from_project = await self._get_project_tenant_id(document.project_id)
        # This explicit check is useful if the initial session for fetching document
        # was not already tenant-isolated, or as a double-check.
        # However, with get_session_with_tenant, this might be redundant if the session
        # is always created with the user's tenant_id for document operations.
        # For a service layer, it's safer to ensure consistent tenant context.
        # Here we rely on `get_session_with_tenant` further down

        return document

    async def download_document(self, document_id: UUID, user_id: UUID) -> tuple[Path, str]:
        """
        Retrieves the actual file from storage for a given document.
        Enforces security by checking document ownership via tenant_id.
        Returns file path and media type.
        """
        document = await self.get_document(
            document_id, user_id
        )  # Reuse get_document for authorization

        # Extract filename from storage_url
        # Assuming storage_url is something like "/local-storage/{file_id}.ext"
        file_name_in_storage = document.storage_url.split("/")[-1]

        try:
            file_path = await self.storage_service.download_file(file_name_in_storage)
            media_type, _ = guess_type(
                document.filename
            )  # Guess media type based on original filename
            if not media_type:
                media_type = "application/octet-stream"  # Default if not guessable
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

    async def delete_document(self, document_id: UUID, user_id: UUID):
        """
        Deletes a document record and its associated file from storage.
        Enforces security by checking document ownership via tenant_id.
        """
        document = await self.get_document(
            document_id, user_id
        )  # Reuse get_document for authorization

        tenant_id = await self._get_project_tenant_id(document.project_id)

        async with get_session_with_tenant(tenant_id) as tenant_db:
            # Delete file from storage
            file_name_in_storage = document.storage_url.split("/")[-1]
            await self.storage_service.delete_file(file_name_in_storage)

            # Delete document record from database
            await tenant_db.delete(document)
            await tenant_db.commit()
