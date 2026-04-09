"""
C2Pro - Asynchronous Ingestion Tasks

This module defines Celery tasks related to document ingestion and processing.
These tasks are designed to run in the background, decoupled from the main
API request/response cycle.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from uuid import UUID

from src.analysis.factories.orchestrator_factory import AnalysisOrchestratorFactory
from src.core.database import get_raw_session, init_db
from src.core.dlq.dlq_service import DLQService
from src.core.tasks.celery_app import celery_app
from src.documents.adapters.extraction.documents_entity_extraction_service import (
    DocumentsEntityExtractionService,
)
from src.documents.adapters.parsers.bc3_file_parser import BC3FileParser
from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.adapters.rag.sqlalchemy_rag_ingestion_service import (
    SqlAlchemyRagIngestionService,
)
from src.documents.adapters.storage.local_file_storage_service import (
    LocalFileStorageService,
)
from src.documents.application.trigger_document_analysis_use_case import (
    TriggerDocumentAnalysisUseCase,
)
from src.documents.domain.models import DocumentStatus
from src.procurement.adapters.persistence.bom_repository import SQLAlchemyBOMRepository
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.application.use_cases.bom_use_cases import CreateBOMItemUseCase
from src.procurement.application.use_cases.wbs_use_cases import CreateWBSItemUseCase
from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)
from src.stakeholders.application.create_stakeholder_use_case import CreateStakeholderUseCase

logger = logging.getLogger(__name__)

storage = LocalFileStorageService()
file_parser = CompositeFileParser(
    bc3_parser=BC3FileParser(),
    excel_parser=ExcelFileParser(),
    pdf_parser=PDFFileParser(),
)


@celery_app.task(name="handle_failed_task")
def handle_failed_task(**kwargs):
    """Compatibility task for deferred failure handling."""
    return kwargs


def _build_processing_details(extraction_summary: dict) -> dict:
    return {
        "processing_stage": "parsed_pending_analysis",
        "analysis_status": "queued",
        "status_detail": (
            "Document parsing and RAG ingestion completed. Analysis orchestration queued."
        ),
        "extraction_summary": extraction_summary,
    }


def _dispatch_failed_task(**kwargs) -> None:
    """Schedule deferred failure handling in Celery when available."""
    apply_async = getattr(handle_failed_task, "apply_async", None)
    if callable(apply_async):
        apply_async(kwargs=kwargs)
        return

    logger.warning(
        "handle_failed_task_apply_async_unavailable",
        extra={"task_type": kwargs.get("task_type")},
    )
    handle_failed_task(**kwargs)


async def _push_trigger_failure_to_dlq(
    *,
    tenant_id: UUID,
    document_id: UUID,
    error: Exception,
) -> None:
    await DLQService().push(
        tenant_id=tenant_id,
        task_type="document_analysis",
        document_id=document_id,
        payload={"document_id": str(document_id)},
        error_message=str(error),
    )


async def _process(document_id: UUID) -> dict:
    """Fetch, parse, update, and trigger analysis for a document."""
    await init_db()

    async with get_raw_session() as session:
        repo = SqlAlchemyDocumentRepository(session=session)

        document = await repo.get_by_id(document_id)
        if not document:
            logger.error("Document with ID '%s' not found. Cannot process.", document_id)
            return {"status": "error", "message": "Document not found"}

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

        tenant_id = await repo.get_project_tenant_id(document.project_id)
        if not tenant_id:
            logger.error("tenant_id_not_found_for_project: project_id=%s", document.project_id)
            return {"status": "error", "message": "Project not found"}

        await repo.update_status(document_id, DocumentStatus.PARSING)
        await session.commit()

        try:
            file_name = f"{document.id}{Path(document.filename).suffix}"
            file_path = await storage.download_file(file_name)

            parsed_payload = await file_parser.parse_document_file(document, file_path)
            logger.info("Document parsing successful for document %s.", document_id)

            extraction_summary = await entity_extraction.extract_entities_from_document(
                document=document,
                parsed_payload=parsed_payload,
                tenant_id=tenant_id,
            )

            await rag_ingestion.ingest_document_chunks(
                document=document,
                parsed_payload=parsed_payload,
                tenant_id=tenant_id,
            )

            document.document_metadata = document.document_metadata or {}
            document.document_metadata["parsed_text"] = parsed_payload.raw_text
            await repo.update_status(document_id, DocumentStatus.PARSED_PENDING_ANALYSIS)
            await session.commit()

            processing_details = _build_processing_details(extraction_summary)

            try:
                trigger_use_case = TriggerDocumentAnalysisUseCase(
                    document_repository=repo,
                    orchestrator=AnalysisOrchestratorFactory.create(),
                )
                await trigger_use_case.execute(document_id=document_id)
            except Exception as trigger_error:
                logger.error(
                    "document_analysis_trigger_failed",
                    exc_info=True,
                    extra={"document_id": str(document_id)},
                )
                _dispatch_failed_task(
                    tenant_id=str(tenant_id),
                    task_type="document_analysis",
                    document_id=str(document_id),
                    payload={"document_id": str(document_id)},
                    error_message=str(trigger_error),
                )
                await _push_trigger_failure_to_dlq(
                    tenant_id=tenant_id,
                    document_id=document_id,
                    error=trigger_error,
                )

            logger.info(
                "document_ingestion_stop_point_reached",
                document_id=str(document_id),
                processing_stage=processing_details["processing_stage"],
                analysis_status=processing_details["analysis_status"],
            )
            return {
                "status": "success",
                "document_id": str(document_id),
                "details": processing_details,
            }

        except Exception as error:
            logger.error("Error processing document %s: %s", document_id, error, exc_info=True)
            await repo.update_status(document_id, DocumentStatus.ERROR, parsing_error=str(error))
            await session.commit()
            raise


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
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
    logger.info(
        "Starting document processing for task_id: %s, document_id: %s",
        self.request.id,
        document_id,
    )
    return asyncio.run(_process(UUID(document_id)))
