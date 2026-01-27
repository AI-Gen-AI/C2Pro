"""
Use Case for creating a document record and queuing it for processing.
"""
import os
from typing import Optional
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status

from src.config import settings # Keep settings for validation for now
from src.documents.domain.models import Document, DocumentType, DocumentStatus
from src.documents.ports.document_repository import IDocumentRepository

class CreateAndQueueDocumentUseCase:
    def __init__(self, document_repository: IDocumentRepository):
        self.document_repository = document_repository

    async def execute(
        self,
        project_id: UUID,
        file: UploadFile,
        document_type: DocumentType,
        user_id: UUID,
    ) -> Document:
        """
        Creates a document record with QUEUED status.
        This is the first, synchronous step in the async processing workflow,
        before the file is actually uploaded to permanent storage.
        """
        # 1. Validate file size and type (basic validation before even queueing)
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
        
        # 2. Get tenant_id
        tenant_id = await self.document_repository.get_project_tenant_id(project_id)
        if not tenant_id:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        # 3. Create a new document domain entity with QUEUED status
        new_document = Document(
            id=uuid4(),
            project_id=project_id,
            document_type=document_type,
            filename=file.filename,
            upload_status=DocumentStatus.QUEUED, # Always start as QUEUED
            parsed_at=None,
            parsing_error=None,
            file_format=file_extension,
            file_size_bytes=file.size,
            # storage_url will be updated later by a background worker after file upload
        )

        # 4. Add document to repository
        await self.document_repository.add(new_document)
        await self.document_repository.commit()
        await self.document_repository.refresh(new_document) # Refresh to get any DB-assigned values

        return new_document
