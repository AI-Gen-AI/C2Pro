"""
Use Case for re-uploading a document (document update with version increment).
ADR-015: now writes content-addressed DocumentRevision lineage instead of
silently forgetting history. Prior revisions are preserved, not reset.
Blobs are content-addressed by sha256 and stored via IStorageService.

Lineage fix: the ingested revision now materialises a ``revision.ingested``
ProjectEvent in the SAME transaction as the revision, and the snapshot enqueue
references ``event.event_id`` (not the revision id), satisfying the
``project_snapshots.source_event_id -> project_events.event_id`` foreign key.

Part of TASK-BCK-023 + TASK-V3-015-02.
"""
import hashlib
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog

from src.core.tasks.snapshot_tasks import enqueue_project_snapshot
from src.core.tenants.types import require_tenant_id
from src.documents.application.dtos import DocumentDTO
from src.documents.domain.models import DocumentStatus, DocumentType
from src.documents.ports.document_repository import IDocumentRepository
from src.documents.ports.storage_service import IStorageService
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.project_snapshot import SnapshotTrigger
from src.temporal.domain.revision_event_factory import build_revision_ingested_event
from src.temporal.ports.document_revision_repository import IDocumentRevisionRepository
from src.temporal.ports.project_event_repository import IProjectEventRepository

logger = structlog.get_logger()


def _now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


STRUCTURED_DOCUMENT_TYPES = {DocumentType.BUDGET, DocumentType.SCHEDULE}
STRUCTURED_DOCX_ERROR = "budget/schedule require .xlsx/.bc3"


class ReuploadDocumentUseCase:
    def __init__(
        self,
        document_repository: IDocumentRepository,
        revision_repository: IDocumentRevisionRepository,
        storage_service: IStorageService,
        event_repository: IProjectEventRepository,
    ):
        self.document_repository = document_repository
        self.revision_repository = revision_repository
        self.storage_service = storage_service
        self.event_repository = event_repository

    @staticmethod
    def _blob_key(blob_hash: str, filename: str | None = None) -> str:
        ext = ""
        if filename and "." in filename:
            ext = filename[filename.rindex(".") :]
        return f"revisions/{blob_hash}{ext}"

    async def _store_blob(self, blob_key: str, file_content: bytes) -> None:
        if not await self.storage_service.file_exists(blob_key):
            await self.storage_service.upload_bytes(file_content, blob_key)

    async def _synthesize_genesis(
        self,
        document_id: UUID,
        project_id: UUID,
        tenant_id: UUID,
        file_hash: str,
        filename: str | None,
    ) -> DocumentRevision:
        # Legacy backfilled genesis is metadata-only — the original bytes are
        # unavailable at reupload time, so the blob_key is not retrievable.
        blob_key = self._blob_key(file_hash, filename)
        now = _now_naive()
        genesis = DocumentRevision(
            revision_id=uuid4(),
            document_id=document_id,
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
        return genesis

    async def execute(
        self,
        tenant_id: UUID,
        document_id: UUID,
        file_content: bytes,
        user_id: UUID,
        filename: str | None = None,
    ) -> DocumentDTO:
        scoped_tenant_id = require_tenant_id(tenant_id)
        document = await self.document_repository.get_by_id(scoped_tenant_id, document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found or access denied")
        file_extension = os.path.splitext(filename or document.filename)[1].lower()
        if file_extension == ".docx" and document.document_type in STRUCTURED_DOCUMENT_TYPES:
            raise ValueError(STRUCTURED_DOCX_ERROR)

        new_file_hash = hashlib.sha256(file_content).hexdigest()

        if document.file_hash == new_file_hash:
            return DocumentDTO.from_domain(document)

        current_rev = await self.revision_repository.get_current(document_id, scoped_tenant_id)

        # H1: lazy genesis synthesis — if no revision row exists for this document
        # but it has a file_hash (legacy upload), synthesise genesis from that hash
        if not current_rev and document.file_hash:
            current_rev = await self._synthesize_genesis(
                document_id=document_id,
                project_id=document.project_id,
                tenant_id=scoped_tenant_id,
                file_hash=document.file_hash,
                filename=document.filename,
            )

        new_rev_no = (current_rev.rev_no + 1) if current_rev else 1
        parent_id = current_rev.revision_id if current_rev else None
        now = _now_naive()
        resolved_filename = filename or document.filename
        blob_key = self._blob_key(new_file_hash, resolved_filename)

        await self._store_blob(blob_key, file_content)

        new_revision = DocumentRevision(
            revision_id=uuid4(),
            document_id=document_id,
            project_id=document.project_id,
            tenant_id=scoped_tenant_id,
            rev_no=new_rev_no,
            parent_revision_id=parent_id,
            blob_hash=new_file_hash,
            blob_key=blob_key,
            valid_from=now,
            created_at=now,
        )

        if current_rev:
            await self.revision_repository.close_current(document_id, scoped_tenant_id, now)

        await self.revision_repository.append_revision(new_revision)

        event = build_revision_ingested_event(
            document_id=document_id,
            project_id=document.project_id,
            tenant_id=scoped_tenant_id,
            revision=new_revision,
            filename=resolved_filename,
            actor=str(user_id),
        )
        await self.event_repository.append(event)

        new_version = document.version + 1
        updated_document = await self.document_repository.update_version(
            tenant_id=scoped_tenant_id,
            document_id=document_id,
            version=new_version,
            file_hash=new_file_hash,
            filename=resolved_filename,
            status=DocumentStatus.UPLOADED,
        )

        # REVISION + PROJECT_EVENT commit atomically here, before the enqueue.
        await self.document_repository.commit()

        # Best-effort: the snapshot enqueue hits the Celery broker synchronously.
        # A broker outage must NOT fail the reupload — revision, event, and the
        # updated document are already durably committed.
        try:
            enqueue_project_snapshot(
                project_id=document.project_id,
                tenant_id=scoped_tenant_id,
                trigger=SnapshotTrigger.REVISION_INGESTED,
                source_event_id=event.event_id,
            )
        except Exception as exc:  # pragma: no cover - infra failure path
            logger.warning(
                "project_snapshot_enqueue_failed",
                document_id=str(document_id),
                project_id=str(document.project_id),
                error=str(exc),
            )

        return DocumentDTO.from_domain(updated_document)
