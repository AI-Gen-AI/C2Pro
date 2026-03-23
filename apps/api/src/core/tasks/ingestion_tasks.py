"""
C2Pro - Asynchronous Ingestion Tasks

This module defines Celery tasks related to document ingestion and processing.
These tasks are designed to run in the background, decoupled from the main
API request/response cycle.
"""
import asyncio
import logging
from pathlib import Path
from uuid import UUID

from src.core.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _build_processing_details(extraction_summary: dict) -> dict:
    return {
        "processing_stage": "parsed",
        "analysis_status": "not_started",
        "status_detail": (
            "Document parsing and RAG ingestion completed. Analysis must be triggered separately."
        ),
        "extraction_summary": extraction_summary,
    }


async def _process(document_id: UUID) -> dict:
    """Fetch, parse, and update a document using real repositories and services."""
    from src.core.database import init_db, get_raw_session

    # Initialize database connection for Celery worker context
    await init_db()
    from src.documents.adapters.persistence.sqlalchemy_document_repository import (
        SqlAlchemyDocumentRepository,
    )
    from src.documents.adapters.storage.local_file_storage_service import (
        LocalFileStorageService,
    )
    from src.documents.adapters.parsers.bc3_file_parser import BC3FileParser
    from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
    from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser
    from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser
    from src.documents.adapters.rag.sqlalchemy_rag_ingestion_service import (
        SqlAlchemyRagIngestionService,
    )
    from src.documents.adapters.extraction.documents_entity_extraction_service import (
        DocumentsEntityExtractionService,
    )
    from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
        SqlAlchemyStakeholderRepository,
    )
    from src.stakeholders.application.create_stakeholder_use_case import CreateStakeholderUseCase
    from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
    from src.procurement.adapters.persistence.bom_repository import SQLAlchemyBOMRepository
    from src.procurement.application.use_cases.wbs_use_cases import CreateWBSItemUseCase
    from src.procurement.application.use_cases.bom_use_cases import CreateBOMItemUseCase
    from src.documents.domain.models import DocumentStatus

    storage = LocalFileStorageService()
    file_parser = CompositeFileParser(
        bc3_parser=BC3FileParser(),
        excel_parser=ExcelFileParser(),
        pdf_parser=PDFFileParser(),
    )

    async with get_raw_session() as session:
        repo = SqlAlchemyDocumentRepository(session=session)

        # 1. Retrieve document metadata from the database
        document = await repo.get_by_id(document_id)
        if not document:
            logger.error("Document with ID '%s' not found. Cannot process.", document_id)
            return {"status": "error", "message": "Document not found"}

        # Dependency factories for the extraction service
        def stakeholder_factory():
            stk_repo = SqlAlchemyStakeholderRepository(session=session)
            return CreateStakeholderUseCase(repository=stk_repo, document_repository=repo)

        def wbs_factory():
            wbs_repo = SQLAlchemyWBSRepository(session=session)
            return CreateWBSItemUseCase(wbs_repository=wbs_repo)

        def bom_factory():
            bom_repo = SQLAlchemyBOMRepository(session=session)
            return CreateBOMItemUseCase(bom_repository=bom_repo)

        entity_extraction = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=stakeholder_factory,
            wbs_use_case_factory=wbs_factory,
            bom_use_case_factory=bom_factory,
            user_id=document.created_by,
        )
        rag_ingestion = SqlAlchemyRagIngestionService(db_session=session)

        # 2. Get tenant_id for context
        tenant_id = await repo.get_project_tenant_id(document.project_id)
        if not tenant_id:
            logger.error("tenant_id_not_found_for_project: project_id=%s", document.project_id)
            return {"status": "error", "message": "Project not found"}

        # 3. Mark as PARSING
        await repo.update_status(document_id, DocumentStatus.PARSING)
        await session.commit()

        try:
            # 4. Download the file from storage
            file_name = f"{document.id}{Path(document.filename).suffix}"
            file_path = await storage.download_file(file_name)

            # 5. Parse the document file using the composite parser
            parsed_payload = await file_parser.parse_document_file(document, file_path)
            logger.info("Document parsing successful for document %s.", document_id)

            # 6. Extract entities (Stakeholders, WBS, BOM)
            extraction_summary = await entity_extraction.extract_entities_from_document(
                document=document,
                parsed_payload=parsed_payload,
                tenant_id=tenant_id,
            )

            # 7. Ingest for RAG
            await rag_ingestion.ingest_document_chunks(
                document=document,
                parsed_payload=parsed_payload,
                tenant_id=tenant_id,
            )

            # 8. Update status to PARSED
            await repo.update_status(document_id, DocumentStatus.PARSED)
            await session.commit()

            processing_details = _build_processing_details(extraction_summary)
            logger.info(
                "document_ingestion_stop_point_reached",
                document_id=str(document_id),
                processing_stage=processing_details["processing_stage"],
                analysis_status=processing_details["analysis_status"],
            )
            return {"status": "success", "document_id": str(document_id), "details": processing_details}

        except Exception as e:
            logger.error("Error processing document %s: %s", document_id, e, exc_info=True)
            await repo.update_status(document_id, DocumentStatus.ERROR, parsing_error=str(e))
            await session.commit()
            raise


# --- Task Definition ---

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,
    retry_backoff_max=60,
    task_track_started=True,
)
def process_document_async(self, document_id: str):
    """
    Asynchronously processes a document using the appropriate parser.

    Args:
        document_id: The unique ID of the document to process. The task
                     retrieves the file path and other info from the database.
    """
    logger.info("Starting document processing for task_id: %s, document_id: %s", self.request.id, document_id)
    return asyncio.run(_process(UUID(document_id)))
