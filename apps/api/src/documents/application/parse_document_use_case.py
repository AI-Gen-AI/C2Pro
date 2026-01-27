"""
Use Case for parsing a document, extracting entities, and ingesting for RAG.
"""
import structlog
from pathlib import Path
from uuid import UUID
from datetime import datetime # Import datetime for document.parsed_at update

from fastapi import HTTPException, status

from src.documents.domain.models import Document, DocumentStatus
from src.documents.ports.document_repository import IDocumentRepository
from src.documents.ports.storage_service import IStorageService
from src.documents.ports.file_parser_service import IFileParserService
from src.documents.ports.entity_extraction_service import IEntityExtractionService
from src.documents.ports.rag_ingestion_service import IRagIngestionService

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

    async def execute(self, document_id: UUID, user_id: UUID) -> None: # user_id might be needed for audit logs or permissions
        # 1. Get document and ensure it exists
        document = await self.document_repository.get_by_id(document_id)
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        # 2. Get tenant_id for context
        tenant_id = await self.document_repository.get_project_tenant_id(document.project_id)
        if not tenant_id:
            logger.error("tenant_id_not_found_for_project", project_id=document.project_id, document_id=document_id)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project for document not found.")

        # 3. Mark document as PARSING
        await self.document_repository.update_status(document_id, DocumentStatus.PARSING)
        await self.document_repository.commit()

        try:
            # 4. Download the file
            # Assuming storage_url will be based on document.id and its extension
            # For now, we mimic the original service's logic: extract filename from what would be storage_url
            file_name_in_storage = f"{document.id}{Path(document.filename).suffix}" # Construct based on stored ID and original extension
            file_path = await self.storage_service.download_file(file_name_in_storage)

            # 5. Parse the document file
            parsed_payload = await self.file_parser_service.parse_document_file(document, file_path)

            # 6. Extract entities (Stakeholders, WBS, BOM)
            extraction_summary = await self.entity_extraction_service.extract_entities_from_document(
                document=document,
                parsed_payload=parsed_payload,
                tenant_id=tenant_id,
            )

            # 7. Ingest for RAG
            await self.rag_ingestion_service.ingest_document_chunks(
                document=document,
                parsed_payload=parsed_payload,
                tenant_id=tenant_id,
            )

            # 8. Update document status to PARSED
            # This would also involve updating document metadata (parsed_content, parsed_at, extraction_summary)
            # which might require an update_document_metadata method in the repository.
            # For simplicity now, only status.
            await self.document_repository.update_status(
                document_id, DocumentStatus.PARSED, parsing_error=None
            )
            # Update parsed_at in domain model if needed, then sync with repository
            # document.parsed_at = datetime.utcnow() # This would be part of a richer update operation
            
            await self.document_repository.commit()

        except Exception as e:
            logger.error("document_parsing_failed", document_id=document_id, error=str(e))
            await self.document_repository.update_status(
                document_id, DocumentStatus.ERROR, parsing_error=str(e)
            )
            await self.document_repository.commit()
            raise # Re-raise to ensure error is propagated
