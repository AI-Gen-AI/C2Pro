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
from src.documents.domain.storage_keys import legacy_document_object_key, revision_object_key
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


def _enqueue_document_processing(document_id: UUID, revision_id: UUID | None = None) -> str | None:
    """Best-effort post-commit analysis dispatch pinned to the new immutable revision."""
    try:
        from src.core.tasks.ingestion_tasks import process_document_async

        task = process_document_async.delay(
            document_id=str(document_id),
            revision_id=str(revision_id) if revision_id is not None else None,
        )
        return getattr(task, "id", None)
    except Exception as exc:  # pragma: no cover - broker availability is runtime-only.
        logger.warning("reupload_processing_enqueue_failed", document_id=str(document_id), error=str(exc))
        return None


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
        # A document uploaded before revision lineage keeps its original bytes at the
        # legacy ``{id}{ext}`` object, which is never written again (P0b) — so the
        # synthesised genesis points at those real bytes.
        blob_key = legacy_document_object_key(document_id, filename)
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

        # Serialise the read-close-append sequence. The lock is held by the surrounding
        # transaction until the commit below, so a concurrent re-upload observes the
        # just-created revision rather than reusing its revision number or parent.
        await self.revision_repository.lock_lineage(document_id, scoped_tenant_id)
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
        # P0b: revision B gets its own immutable object; revision A's object is untouched.
        blob_key = revision_object_key(
            tenant_id=scoped_tenant_id,
            project_id=document.project_id,
            document_id=document_id,
            blob_hash=new_file_hash,
            filename=resolved_filename,
        )

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
        # The mutable pointer follows the current revision; history is read from revisions.
        await self.document_repository.update_storage_path(scoped_tenant_id, document_id, blob_key)

        # REVISION + PROJECT_EVENT commit atomically here, before the enqueue.
        await self.document_repository.commit()

        # A revision is not useful temporal evidence until the worker parses it. The durable
        # write has already committed, so a broker outage cannot roll back the lineage.
        _enqueue_document_processing(document_id, new_revision.revision_id)

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
