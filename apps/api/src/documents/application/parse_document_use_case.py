"""
Use Case for parsing a document, extracting entities, and ingesting for RAG.
"""
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import structlog
from fastapi import HTTPException, status

from src.documents.domain.models import DocumentStatus
from src.documents.ports.document_repository import IDocumentRepository
from src.documents.ports.entity_extraction_service import IEntityExtractionService
from src.documents.ports.file_parser_service import IFileParserService
from src.documents.ports.rag_ingestion_service import IRagIngestionService
from src.documents.ports.storage_service import IStorageService

logger = structlog.get_logger()

class ParseDocumentUseCase:
    def __init__(
        self,
        document_repository: IDocumentRepository,
        storage_service: IStorageService,
        file_parser_service: IFileParserService,
        entity_extraction_service: IEntityExtractionService,
        rag_ingestion_service: IRagIngestionService,
    ):
        self.document_repository = document_repository
        self.storage_service = storage_service
        self.file_parser_service = file_parser_service
        self.entity_extraction_service = entity_extraction_service
        self.rag_ingestion_service = rag_ingestion_service

    async def execute(self, tenant_id: UUID, document_id: UUID, user_id: UUID) -> None:  # noqa: ARG002 — user_id reserved for future audit/permissions
        # 1. Get document and ensure it exists
        document = await self.document_repository.get_by_id(tenant_id, document_id)
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found or access denied.")

        # 2. Mark document as PARSING
        await self.document_repository.update_status(tenant_id, document_id, DocumentStatus.PARSING)
        await self.document_repository.commit()

        try:
            # 3. Download the file
            # Assuming storage_url will be based on document.id and its extension
            # For now, we mimic the original service's logic: extract filename from what would be storage_url
            file_name_in_storage = f"{document.id}{Path(document.filename).suffix}" # Construct based on stored ID and original extension
            file_path = await self.storage_service.download_file(file_name_in_storage)

            # 4. Parse the document file
            parsed_payload = await self.file_parser_service.parse_document_file(document, file_path)

            # 5. Extract entities (Stakeholders, WBS, BOM)
            await self.entity_extraction_service.extract_entities_from_document(
                document=document,
                parsed_payload=parsed_payload,
                tenant_id=tenant_id,
            )

            # 6. Ingest for RAG
            await self.rag_ingestion_service.ingest_document_chunks(
                document=document,
                parsed_payload=parsed_payload,
                tenant_id=tenant_id,
            )

            # 7. Update document status to PARSED
            # This would also involve updating document metadata (parsed_content, parsed_at, extraction_summary)
            # which might require an update_document_metadata method in the repository.
            # For simplicity now, only status and parsed_at.
            await self.document_repository.update_status(
                tenant_id,
                document_id,
                DocumentStatus.PARSED,
                parsing_error=None,
                parsed_at=datetime.now(UTC),
            )

            await self.document_repository.commit()

        except Exception as e:
            logger.error("document_parsing_failed", document_id=document_id, error=str(e))
            await self.document_repository.update_status(
                tenant_id, document_id, DocumentStatus.ERROR, parsing_error=str(e)
            )
            await self.document_repository.commit()
            raise # Re-raise to ensure error is propagated
