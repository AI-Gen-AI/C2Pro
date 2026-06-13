"""
Use Case for uploading a document.
ADR-015: creates genesis DocumentRevision (rev_no=1) at initial upload.
Refers to Suite ID: TS-UA-DOC-UC-001.
"""
import hashlib
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status

from src.config import settings
from src.documents.domain.models import Document, DocumentStatus, DocumentType
from src.documents.ports.document_repository import IDocumentRepository
from src.documents.ports.storage_service import IStorageService
from src.projects.ports.project_repository import ProjectRepository
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.ports.document_revision_repository import IDocumentRevisionRepository


def _now_naive():
    return datetime.now(UTC).replace(tzinfo=None)


class UploadDocumentUseCase:
    def __init__(
        self,
        document_repository: IDocumentRepository,
        storage_service: IStorageService,
        project_repository: ProjectRepository,
        revision_repository: IDocumentRevisionRepository | None = None,
    ):
        self.document_repository = document_repository
        self.storage_service = storage_service
        self.project_repository = project_repository
        self.revision_repository = revision_repository

    @staticmethod
    def _blob_key(blob_hash: str, filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        return f"revisions/{blob_hash}{ext}"

    async def execute(
        self,
        project_id: UUID,
        file: UploadFile,
        document_type: DocumentType,
        user_id: UUID,
        tenant_id: UUID,
        metadata: dict | None = None,
    ) -> Document:
        if not metadata:
            metadata = {}

        file_size = getattr(file, "size", None)
        if not isinstance(file_size, int):
            current_position = file.file.tell()
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(current_position)

        if file_size > settings.max_upload_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds limit of {settings.max_upload_size_mb}MB.",
            )

        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in settings.allowed_document_types:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File type {file_extension} is not allowed. "
                       f"Allowed types: {', '.join(settings.allowed_document_types)}",
            )

        project_exists = await self.project_repository.exists_by_id(project_id, tenant_id)
        if not project_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        new_document = Document(
            id=uuid4(),
            project_id=project_id,
            tenant_id=tenant_id,
            document_type=document_type,
            filename=file.filename,
            upload_status=DocumentStatus.QUEUED,
            parsed_at=None,
            parsing_error=None,
            created_by=user_id,
            file_format=file_extension,
            file_size_bytes=file_size,
        )

        await self.document_repository.add(tenant_id, new_document)
        await self.document_repository.commit()

        file.file.seek(0)
        content_bytes = await file.read()
        file.file.seek(0)
        storage_path = await self.storage_service.upload_file(
            file_content=file.file, file_id=new_document.id, file_extension=file_extension
        )
        file_hash = hashlib.sha256(content_bytes).hexdigest()

        await self.document_repository.update_storage_path(tenant_id, new_document.id, storage_path)
        await self.document_repository.update_status(tenant_id, new_document.id, DocumentStatus.UPLOADED)
        await self.document_repository.update_metadata(tenant_id, new_document.id, {"file_hash": file_hash})
        await self.document_repository.commit()

        # H1: genesis revision at initial upload, content-addressed
        if self.revision_repository:
            blob_key = self._blob_key(file_hash, file.filename)
            if not await self.storage_service.file_exists(blob_key):
                await self.storage_service.upload_bytes(content_bytes, blob_key)
            now = _now_naive()
            genesis = DocumentRevision(
                revision_id=uuid4(),
                document_id=new_document.id,
                project_id=project_id,
                tenant_id=tenant_id,
                rev_no=1,
                parent_revision_id=None,
                blob_hash=file_hash,
                blob_key=blob_key,
                valid_from=now,
                created_at=now,
            )
            await self.revision_repository.append_revision(genesis)

        await self.document_repository.refresh(new_document)
        return new_document
