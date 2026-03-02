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
from src.services.ingestion.pdf_parser import PdfParserService

logger = logging.getLogger(__name__)


async def _process(document_id: UUID) -> dict:
    """Fetch, parse, and update a document using real repositories."""
    from src.core.database import get_raw_session
    from src.documents.adapters.persistence.sqlalchemy_document_repository import (
        SqlAlchemyDocumentRepository,
    )
    from src.documents.adapters.storage.local_file_storage_service import (
        LocalFileStorageService,
    )
    from src.documents.domain.models import DocumentStatus

    storage = LocalFileStorageService()

    async with get_raw_session() as session:
        repo = SqlAlchemyDocumentRepository(session=session)

        # 1. Retrieve document metadata from the database
        document = await repo.get_by_id(document_id)
        if not document:
            logger.error("Document with ID '%s' not found. Cannot process.", document_id)
            return {"status": "error", "message": "Document not found"}

        # 2. Mark as PARSING
        await repo.update_status(document_id, DocumentStatus.PARSING)
        await session.commit()

        try:
            # 3. Download the file from storage
            file_name = f"{document.id}{Path(document.filename).suffix}"
            file_path = await storage.download_file(file_name)
            file_content = file_path.read_bytes()

            # 4. Parse based on file type
            suffix = Path(document.filename).suffix.lower()
            if suffix == ".pdf":
                parser = PdfParserService()
                parsed_data = parser.extract_text(file_content, filename=document.filename)
                processing_details = {
                    "pages_processed": parsed_data["page_count"],
                    "tables_found": len(parsed_data.get("tables_data", [])),
                    "chars_extracted": len(parsed_data["full_text"]),
                }
                logger.info("PDF parsing successful for document %s.", document_id)
            else:
                logger.warning("No parser available for file type '%s'.", suffix)
                processing_details = {"error": "Unsupported file type"}

            # 5. Update status to PARSED
            await repo.update_status(document_id, DocumentStatus.PARSED)
            await session.commit()

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
