"""
Use Case for deleting a document and its stored revision objects (P0b).

The database delete goes first: append-only history (``project_events`` referencing the
document's revisions) may refuse it, and then no byte may be removed. Only after the delete
is committed are the document's own objects removed — its document-scoped revision prefix
and any legacy ``{id}{ext}`` object. Keys are document-scoped, so this never touches another
document's or tenant's bytes. A storage failure at that point leaves unreferenced objects
behind (logged for cleanup) instead of a live document without bytes.
"""
from uuid import UUID

import structlog

from src.core.tenants.types import require_tenant_id
from src.documents.application.get_document_use_case import GetDocumentUseCase  # Reuse use case
from src.documents.domain.storage_keys import document_object_prefix, legacy_document_object_key
from src.documents.ports.document_repository import IDocumentRepository
from src.documents.ports.storage_service import IStorageService

logger = structlog.get_logger()


class DeleteDocumentUseCase:
    def __init__(
        self,
        document_repository: IDocumentRepository,
        storage_service: IStorageService,
        get_document_use_case: GetDocumentUseCase,
    ):
        self.document_repository = document_repository
        self.storage_service = storage_service
        self.get_document_use_case = get_document_use_case

    async def execute(self, document_id: UUID, user_id: UUID, tenant_id: UUID) -> None:
        """
        Deletes a document record, then the objects that only that document owned.
        """
        scoped_tenant_id = require_tenant_id(tenant_id)
        document = await self.get_document_use_case.execute(document_id, user_id, scoped_tenant_id)

        await self.document_repository.delete(scoped_tenant_id, document_id)
        await self.document_repository.commit()

        prefix = document_object_prefix(scoped_tenant_id, document.project_id, document.id)
        try:
            await self.storage_service.delete_prefix(prefix)
        except Exception as exc:
            logger.warning(
                "document_revision_objects_not_deleted",
                document_id=str(document.id),
                prefix=prefix,
                error=str(exc),
            )

        legacy_key = legacy_document_object_key(document.id, document.filename)
        try:
            await self.storage_service.delete_file(legacy_key)
        except Exception as exc:
            logger.warning(
                "document_legacy_object_not_deleted",
                document_id=str(document.id),
                key=legacy_key,
                error=str(exc),
            )
