"""
Use Case for re-uploading a document (document update with version increment).
ADR-015: now writes content-addressed DocumentRevision lineage instead of
silently forgetting history. Prior revisions are preserved, not reset.
Blobs are content-addressed by sha256 and stored via IStorageService.

Part of TASK-BCK-023 + TASK-V3-015-02.
"""
import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.documents.application.dtos import DocumentDTO
from src.documents.domain.models import DocumentStatus
from src.documents.ports.document_repository import IDocumentRepository
from src.documents.ports.storage_service import IStorageService
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.ports.document_revision_repository import IDocumentRevisionRepository


def _now_naive():
    return datetime.now(UTC).replace(tzinfo=None)


class ReuploadDocumentUseCase:

    def __init__(
        self,
        document_repository: IDocumentRepository,
        revision_repository: IDocumentRevisionRepository,
        storage_service: IStorageService,
    ):
        self.document_repository = document_repository
        self.revision_repository = revision_repository
        self.storage_service = storage_service

    @staticmethod
    def _blob_key(blob_hash: str, filename: str | None = None) -> str:
        ext = ""
        if filename and "." in filename:
            ext = filename[filename.rindex("."):]
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
        filename: str | None = None,
    ) -> DocumentDTO:
        document = await self.document_repository.get_by_id(tenant_id, document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found or access denied")

        new_file_hash = hashlib.sha256(file_content).hexdigest()

        if document.file_hash == new_file_hash:
            return DocumentDTO.from_domain(document)

        current_rev = await self.revision_repository.get_current(document_id, tenant_id)

        # H1: lazy genesis synthesis — if no revision row exists for this document
        # but it has a file_hash (legacy upload), synthesise genesis from that hash
        if not current_rev and document.file_hash:
            current_rev = await self._synthesize_genesis(
                document_id=document_id,
                project_id=document.project_id,
                tenant_id=tenant_id,
                file_hash=document.file_hash,
                filename=document.filename,
            )

        new_rev_no = (current_rev.rev_no + 1) if current_rev else 1
        parent_id = current_rev.revision_id if current_rev else None
        now = _now_naive()
        blob_key = self._blob_key(new_file_hash, filename or document.filename)

        await self._store_blob(blob_key, file_content)

        new_revision = DocumentRevision(
            revision_id=uuid4(),
            document_id=document_id,
            project_id=document.project_id,
            tenant_id=tenant_id,
            rev_no=new_rev_no,
            parent_revision_id=parent_id,
            blob_hash=new_file_hash,
            blob_key=blob_key,
            valid_from=now,
            created_at=now,
        )

        if current_rev:
            await self.revision_repository.close_current(document_id, tenant_id, now)

        await self.revision_repository.append_revision(new_revision)

        new_version = document.version + 1
        updated_document = await self.document_repository.update_version(
            tenant_id=tenant_id,
            document_id=document_id,
            version=new_version,
            file_hash=new_file_hash,
            filename=filename or document.filename,
            status=DocumentStatus.UPLOADED,
        )

        await self.document_repository.commit()

        return DocumentDTO.from_domain(updated_document)
