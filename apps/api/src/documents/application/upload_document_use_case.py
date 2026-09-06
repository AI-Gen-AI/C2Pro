"""
Use Case for uploading a document.
ADR-015: creates genesis DocumentRevision (rev_no=1) at initial upload.
Refers to Suite ID: TS-UA-DOC-UC-001.
"""

import hashlib
import os
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import structlog
from fastapi import HTTPException, UploadFile, status

from src.config import settings
from src.core.json_types import JsonDict
from src.core.tasks.snapshot_tasks import enqueue_project_snapshot
from src.core.tenants.types import require_tenant_id
from src.documents.domain.models import Document, DocumentStatus, DocumentType
from src.documents.ports.document_repository import IDocumentRepository
from src.documents.ports.storage_service import IStorageService
from src.projects.ports.project_repository import ProjectRepository
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.project_snapshot import SnapshotTrigger
from src.temporal.domain.revision_event_factory import build_revision_ingested_event
from src.temporal.ports.document_revision_repository import IDocumentRevisionRepository
from src.temporal.ports.project_event_repository import IProjectEventRepository

logger = structlog.get_logger()

STRUCTURED_DOCUMENT_TYPES = {DocumentType.BUDGET, DocumentType.SCHEDULE}
STRUCTURED_DOCX_ERROR = "budget/schedule require .xlsx/.bc3"


def _now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class UploadDocumentUseCase:
    def __init__(
        self,
        document_repository: IDocumentRepository,
        storage_service: IStorageService,
        project_repository: ProjectRepository,
        revision_repository: IDocumentRevisionRepository | None = None,
        event_repository: IProjectEventRepository | None = None,
    ):
        self.document_repository = document_repository
        self.storage_service = storage_service
        self.project_repository = project_repository
        self.revision_repository = revision_repository
        self.event_repository = event_repository

        # Dependency invariant: a revision without its material ProjectEvent must
        # never be silently persisted. Legacy/test construction may omit BOTH, but
        # a revision_repository can never be wired without an event_repository.
        if revision_repository is not None and event_repository is None:
            raise ValueError(
                "event_repository is required when revision_repository is provided"
            )

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
        metadata: JsonDict | None = None,
    ) -> Document:
        if not metadata:
            metadata = {}

        scoped_tenant_id = require_tenant_id(tenant_id)
        filename = cast(str, file.filename)
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

        file_extension = os.path.splitext(filename)[1].lower()
        if file_extension not in settings.allowed_document_types:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File type {file_extension} is not allowed. "
                f"Allowed types: {', '.join(settings.allowed_document_types)}",
            )
        if file_extension == ".docx" and document_type in STRUCTURED_DOCUMENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=STRUCTURED_DOCX_ERROR,
            )

        project_exists = await self.project_repository.exists_by_id(project_id, scoped_tenant_id)
        if not project_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        new_document = Document(
            id=uuid4(),
            project_id=project_id,
            tenant_id=scoped_tenant_id,
            document_type=document_type,
            filename=filename,
            upload_status=DocumentStatus.QUEUED,
            parsed_at=None,
            parsing_error=None,
            created_by=user_id,
            file_format=file_extension,
            file_size_bytes=file_size,
        )

        await self.document_repository.add(scoped_tenant_id, new_document)
        await self.document_repository.commit()

        file.file.seek(0)
        content_bytes = await file.read()
        file.file.seek(0)
        storage_path = await self.storage_service.upload_file(
            file_content=file.file, file_id=new_document.id, file_extension=file_extension
        )
        file_hash = hashlib.sha256(content_bytes).hexdigest()

        await self.document_repository.update_storage_path(
            scoped_tenant_id, new_document.id, storage_path
        )
        await self.document_repository.update_status(
            scoped_tenant_id, new_document.id, DocumentStatus.UPLOADED
        )
        await self.document_repository.update_metadata(
            scoped_tenant_id, new_document.id, {"file_hash": file_hash}
        )
        await self.document_repository.commit()

        # H1: genesis revision at initial upload, content-addressed
        if self.revision_repository:
            assert self.event_repository is not None  # guaranteed by __init__ invariant
            blob_key = self._blob_key(file_hash, filename)
            if not await self.storage_service.file_exists(blob_key):
                await self.storage_service.upload_bytes(content_bytes, blob_key)
            now = _now_naive()
            genesis = DocumentRevision(
                revision_id=uuid4(),
                document_id=new_document.id,
                project_id=project_id,
                tenant_id=scoped_tenant_id,
                rev_no=1,
                parent_revision_id=None,
                blob_hash=file_hash,
                blob_key=blob_key,
                valid_from=now,
                created_at=now,
            )
            await self.revision_repository.append_revision(genesis)

            event = build_revision_ingested_event(
                document_id=new_document.id,
                project_id=project_id,
                tenant_id=scoped_tenant_id,
                revision=genesis,
                filename=filename,
                actor=str(user_id),
            )
            await self.event_repository.append(event)

            # REVISION + PROJECT_EVENT commit atomically here, before the enqueue.
            await self.document_repository.commit()

            # Best-effort: enqueuing the snapshot task hits the Celery broker
            # synchronously. A broker/Redis outage must NOT fail the upload — the
            # document, its genesis revision, and its material event are already
            # persisted. (Mirrors the resilient _enqueue_document_processing in
            # the HTTP router.)
            try:
                enqueue_project_snapshot(
                    project_id=project_id,
                    tenant_id=scoped_tenant_id,
                    trigger=SnapshotTrigger.REVISION_INGESTED,
                    source_event_id=event.event_id,
                )
            except Exception as exc:  # pragma: no cover - infra failure path
                logger.warning(
                    "project_snapshot_enqueue_failed",
                    document_id=str(new_document.id),
                    project_id=str(project_id),
                    error=str(exc),
                )

        await self.document_repository.refresh(new_document)
        return new_document
