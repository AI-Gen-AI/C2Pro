"""
Use Case for uploading a document.
Refers to Suite ID: TS-UA-DOC-UC-001.
"""
import os
from typing import Optional
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status

from src.config import settings # Keep settings for now, refactor later
from src.documents.domain.models import Document, DocumentType, DocumentStatus
from src.documents.ports.document_repository import IDocumentRepository
from src.documents.ports.storage_service import IStorageService

class UploadDocumentUseCase:
    def __init__(self, document_repository: IDocumentRepository, storage_service: IStorageService):
        self.document_repository = document_repository
        self.storage_service = storage_service

    async def execute(
        self,
        project_id: UUID,
        file: UploadFile,
        document_type: DocumentType,
        user_id: UUID,
        metadata: Optional[dict] = None,
    ) -> Document:
        """
        Uploads a file to storage and creates a corresponding Document record in the database.
        """
        if not metadata:
            metadata = {}

        # 1. Validate file size and type
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
        
        # 2. Get tenant_id (from project or current user's context)
        # This dependency on Project.tenant_id needs to be handled via a port/repository in the Project module
        # For now, we'll keep the call to document_repository's helper.
        tenant_id = await self.document_repository.get_project_tenant_id(project_id)
        if not tenant_id:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        # 3. Create a new document domain entity
        new_document = Document(
            id=uuid4(),
            project_id=project_id,
            document_type=document_type,
            filename=file.filename,
            upload_status=DocumentStatus.QUEUED, # Start as QUEUED as per new plan
            parsed_at=None,
            parsing_error=None,
            # Other fields from the original Document model
            file_format=file_extension,
            file_size_bytes=file.size,
            # storage_url will be set after upload
        )

        # 4. Add document to repository (this will create the ORM record)
        await self.document_repository.add(new_document)
        await self.document_repository.commit() # Commit transaction for the new document record

        # 5. Upload the file to storage using the document's ID
        file.file.seek(0)
        storage_path = await self.storage_service.upload_file(
            file_content=file.file, file_id=new_document.id, file_extension=file_extension
        )

        # 6. Update document record with storage URL
        await self.document_repository.update_storage_path(new_document.id, storage_path)
        await self.document_repository.update_status(new_document.id, DocumentStatus.UPLOADED) # Mark as UPLOADED after successful storage
        await self.document_repository.commit()

        # 7. Refresh the domain entity from repository to get latest state
        await self.document_repository.refresh(new_document)

        return new_document
