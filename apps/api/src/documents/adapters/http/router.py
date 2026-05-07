"""
HTTP adapter (FastAPI router) for the Documents module.

Refers to Test Suite ID: TASK-OPS-DOCFLOW-009.
"""
from __future__ import annotations

import pathlib
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.database import get_session
from src.core.repositories import get_project_repository
from src.core.security import CurrentTenantId, CurrentUserId, security_scheme
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
from src.documents.adapters.rag.rag_service_adapter import SqlAlchemyRagService
from src.documents.adapters.rag.sqlalchemy_rag_ingestion_service import (
    SqlAlchemyRagIngestionService,
)
from src.documents.adapters.storage.local_file_storage_service import (
    LocalFileStorageService,
)
from src.documents.application.answer_rag_question_use_case import AnswerRagQuestionUseCase
from src.documents.application.delete_document_use_case import DeleteDocumentUseCase
from src.documents.application.download_document_use_case import DownloadDocumentUseCase
from src.documents.application.dtos import (
    DocumentDetailResponse,
    DocumentEntityResponse,
    DocumentHistoryResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentPollingStatus,
    DocumentQueuedResponse,
    DocumentRelationshipExplanationResponse,
    DocumentResponse,
    DocumentUploadResponse,
    RagAnswerResponse,
    RagQuestionRequest,
)
from src.documents.application.get_document_history_use_case import GetDocumentHistoryUseCase
from src.documents.application.get_document_relationship_explanation_use_case import (
    GetDocumentRelationshipExplanationUseCase,
)
from src.documents.application.get_document_use_case import GetDocumentUseCase
from src.documents.application.get_document_with_clauses_use_case import (
    GetDocumentWithClausesUseCase,
)
from src.documents.application.list_project_documents_use_case import (
    ListProjectDocumentsUseCase,
)
from src.documents.application.parse_document_use_case import ParseDocumentUseCase
from src.documents.application.reupload_document_use_case import (
    ReuploadDocumentUseCase,  # TASK-BCK-023
)
from src.documents.application.services.relationship_explanation_service import (
    EvidenceRelationshipExplanationService,
)
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import DocumentStatus, DocumentType
from src.procurement.adapters.persistence.bom_repository import SQLAlchemyBOMRepository
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.application.use_cases.bom_use_cases import CreateBOMItemUseCase
from src.procurement.application.use_cases.wbs_use_cases import CreateWBSItemUseCase
from src.projects.ports.project_repository import ProjectRepository

# Cross-module dependencies for entity extraction
from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)
from src.stakeholders.application.create_stakeholder_use_case import CreateStakeholderUseCase

logger = structlog.get_logger()

router = APIRouter(
    prefix="",
    tags=["Documents"],
    dependencies=[Depends(security_scheme)],  # Required for Swagger UI authentication
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
    },
)

ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".bc3"}


def _get_upload_file_size(file: UploadFile) -> int:
    size = getattr(file, "size", None)
    if isinstance(size, int):
        return size

    current_position = file.file.tell()
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(current_position)
    return size


def _enqueue_document_processing(document_id: UUID) -> str | None:
    try:
        from src.core.tasks.ingestion_tasks import process_document_async

        if process_document_async is None:
            logger.warning("document_processing_task_unavailable", document_id=str(document_id))
            return None

        task = process_document_async.delay(document_id=str(document_id))
        return getattr(task, "id", None)
    except Exception as exc:  # pragma: no cover - runtime infra failure path
        logger.warning(
            "document_processing_enqueue_failed",
            document_id=str(document_id),
            error=str(exc),
        )
        return None


def _normalize_document_status_for_polling(status: DocumentStatus) -> DocumentPollingStatus:
    if status == DocumentStatus.UPLOADED:
        return DocumentPollingStatus.QUEUED
    if status == DocumentStatus.PARSING:
        return DocumentPollingStatus.PROCESSING
    if status == DocumentStatus.PARSED:
        return DocumentPollingStatus.PARSED
    if status == DocumentStatus.ERROR:
        return DocumentPollingStatus.ERROR
    return DocumentPollingStatus.PROCESSING


def _document_status_detail_for_polling(status: DocumentStatus) -> str:
    if status == DocumentStatus.UPLOADED:
        return "Upload accepted. Ingestion is queued; analysis has not started."
    if status == DocumentStatus.PARSING:
        return "Document parsing is in progress. Analysis has not started."
    if status == DocumentStatus.PARSED:
        return (
            "Document parsing and RAG ingestion completed. Analysis must be triggered separately."
        )
    if status == DocumentStatus.ERROR:
        return "Document processing failed before analysis could start."
    return "Document ingestion is still in progress. Analysis has not started."


# --- Dependency wiring ---
def get_document_repository(
    db: AsyncSession = Depends(get_session),
) -> SqlAlchemyDocumentRepository:
    return SqlAlchemyDocumentRepository(session=db)


def get_storage_service() -> LocalFileStorageService:
    return LocalFileStorageService()


def get_file_parser_service() -> CompositeFileParser:
    return CompositeFileParser(
        bc3_parser=BC3FileParser(),
        excel_parser=ExcelFileParser(),
        pdf_parser=PDFFileParser(),
    )


def get_entity_extraction_service(
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_session),
    doc_repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
) -> DocumentsEntityExtractionService:
    # Use factories to provide fresh use cases with current session
    def stakeholder_factory():
        repo = SqlAlchemyStakeholderRepository(session=db)
        return CreateStakeholderUseCase(repository=repo, document_repository=doc_repo)

    def wbs_factory():
        repo = SQLAlchemyWBSRepository(session=db)
        return CreateWBSItemUseCase(wbs_repository=repo)

    def bom_factory():
        repo = SQLAlchemyBOMRepository(session=db)
        return CreateBOMItemUseCase(bom_repository=repo)

    return DocumentsEntityExtractionService(
        stakeholder_use_case_factory=stakeholder_factory,
        wbs_use_case_factory=wbs_factory,
        bom_use_case_factory=bom_factory,
        user_id=user_id,
    )


def get_rag_ingestion_service(
    db: AsyncSession = Depends(get_session),
) -> SqlAlchemyRagIngestionService:
    return SqlAlchemyRagIngestionService(db_session=db)


def get_upload_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    storage: LocalFileStorageService = Depends(get_storage_service),
    project_repo: ProjectRepository = Depends(get_project_repository),
) -> UploadDocumentUseCase:
    return UploadDocumentUseCase(
        document_repository=repo,
        storage_service=storage,
        project_repository=project_repo,
    )


def get_reupload_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
) -> ReuploadDocumentUseCase:
    """Dependency for ReuploadDocumentUseCase (TASK-BCK-023)."""
    return ReuploadDocumentUseCase(document_repository=repo)


def get_get_document_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
) -> GetDocumentUseCase:
    return GetDocumentUseCase(document_repository=repo)


def get_download_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    storage: LocalFileStorageService = Depends(get_storage_service),
    get_document: GetDocumentUseCase = Depends(get_get_document_use_case),
) -> DownloadDocumentUseCase:
    return DownloadDocumentUseCase(
        document_repository=repo,
        storage_service=storage,
        get_document_use_case=get_document,
    )


def get_delete_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    storage: LocalFileStorageService = Depends(get_storage_service),
    get_document: GetDocumentUseCase = Depends(get_get_document_use_case),
) -> DeleteDocumentUseCase:
    return DeleteDocumentUseCase(
        document_repository=repo,
        storage_service=storage,
        get_document_use_case=get_document,
    )


def get_list_documents_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    project_repo: ProjectRepository = Depends(get_project_repository),
) -> ListProjectDocumentsUseCase:
    return ListProjectDocumentsUseCase(document_repository=repo, project_repository=project_repo)


def get_get_document_with_clauses_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
) -> GetDocumentWithClausesUseCase:
    return GetDocumentWithClausesUseCase(document_repository=repo)


def get_parse_document_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    storage: LocalFileStorageService = Depends(get_storage_service),
    file_parser: CompositeFileParser = Depends(get_file_parser_service),
    entity_extraction: DocumentsEntityExtractionService = Depends(get_entity_extraction_service),
    rag_ingestion: SqlAlchemyRagIngestionService = Depends(get_rag_ingestion_service),
) -> ParseDocumentUseCase:
    return ParseDocumentUseCase(
        document_repository=repo,
        storage_service=storage,
        file_parser_service=file_parser,
        entity_extraction_service=entity_extraction,
        rag_ingestion_service=rag_ingestion,
    )


def get_rag_service(
    db: AsyncSession = Depends(get_session),
) -> SqlAlchemyRagService:
    return SqlAlchemyRagService(db_session=db)


def get_answer_rag_use_case(
    rag_service: SqlAlchemyRagService = Depends(get_rag_service),
) -> AnswerRagQuestionUseCase:
    return AnswerRagQuestionUseCase(rag_service=rag_service)


def get_document_history_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
) -> GetDocumentHistoryUseCase:
    return GetDocumentHistoryUseCase(document_repository=repo)


def get_document_relationship_explanation_service() -> EvidenceRelationshipExplanationService:
    return EvidenceRelationshipExplanationService()


def get_document_relationship_explanation_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    explanation_service: EvidenceRelationshipExplanationService = Depends(
        get_document_relationship_explanation_service
    ),
) -> GetDocumentRelationshipExplanationUseCase:
    return GetDocumentRelationshipExplanationUseCase(
        document_repository=repo,
        explanation_service=explanation_service,
    )


@router.post(
    "/projects/{project_id}/documents",
    response_model=DocumentQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document for asynchronous processing",
)
async def upload_document_for_processing(
    project_id: UUID,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    upload_use_case: UploadDocumentUseCase = Depends(get_upload_use_case),
) -> DocumentQueuedResponse:
    file_size = _get_upload_file_size(file)

    if file_size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds limit of {settings.max_upload_size_mb}MB.",
        )

    file_extension = pathlib.Path(file.filename).suffix.lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{file_extension}' is not allowed.",
        )

    document = await upload_use_case.execute(
        project_id=project_id,
        file=file,
        document_type=document_type,
        user_id=user_id,
        tenant_id=tenant_id,
    )
    response_data = DocumentResponse.model_validate(document).model_dump()
    response_data["task_id"] = _enqueue_document_processing(document.id)
    response_data["processing_status"] = DocumentPollingStatus.QUEUED
    response_data["status_detail"] = (
        "Upload accepted. File stored successfully. Background processing will start when the worker is available."
        if response_data["task_id"] is None
        else _document_status_detail_for_polling(DocumentStatus.UPLOADED)
    )
    return DocumentQueuedResponse(**response_data)


@router.patch(
    "/documents/{document_id}/file",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Re-upload a document file (creates new version)",
)
async def reupload_document_file(
    document_id: UUID,
    _user_id: CurrentUserId,
    _tenant_id: CurrentTenantId,
    file: UploadFile = File(...),
    reupload_use_case: ReuploadDocumentUseCase = Depends(get_reupload_use_case),
) -> DocumentResponse:
    """
    Re-upload a document with a new file.

    TASK-BCK-023: Document versioning
    - Calculates file hash and compares with existing
    - Increments version if content changed
    - Resets status to UPLOADED for re-processing
    - Returns existing document if content unchanged
    """
    file_size = _get_upload_file_size(file)

    if file_size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds limit of {settings.max_upload_size_mb}MB.",
        )

    file_extension = pathlib.Path(file.filename).suffix.lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{file_extension}' is not allowed.",
        )

    # Read file content
    file_content = await file.read()

    try:
        document_dto = await reupload_use_case.execute(
            document_id=document_id,
            file_content=file_content,
            filename=file.filename,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    # Trigger re-ingestion if version was incremented
    # (use case returns same version if content unchanged)
    # For now, just return the updated document
    # Future: trigger re-ingestion task similar to upload

    return DocumentResponse(
        id=document_dto.id,
        project_id=document_dto.project_id,
        document_type=document_dto.document_type,
        filename=document_dto.filename,
        upload_status=document_dto.upload_status,
        version=document_dto.version,
        file_hash=document_dto.file_hash,
        file_format=document_dto.file_format,
        storage_url=document_dto.storage_url,
        file_size_bytes=document_dto.file_size_bytes,
        created_at=document_dto.created_at,
        updated_at=document_dto.updated_at,
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get document details by ID",
)
async def get_document_endpoint(
    document_id: UUID,
    _user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    use_case: GetDocumentWithClausesUseCase = Depends(get_get_document_with_clauses_use_case),
) -> DocumentDetailResponse:
    document = await use_case.execute(document_id, tenant_id)
    response_data = DocumentResponse.model_validate(document).model_dump()
    response_data["clauses"] = [
        {
            "id": clause.id,
            "project_id": clause.project_id,
            "document_id": clause.document_id,
            "clause_code": clause.clause_code,
            "clause_type": clause.clause_type.value if clause.clause_type else None,
            "title": clause.title,
            "full_text": clause.full_text,
            "text_start_offset": clause.text_start_offset,
            "text_end_offset": clause.text_end_offset,
            "extracted_entities": clause.extracted_entities,
            "extraction_confidence": clause.extraction_confidence,
            "extraction_model": clause.extraction_model,
            "manually_verified": clause.manually_verified,
            "verified_at": clause.verified_at,
        }
        for clause in document.clauses
    ]
    return DocumentDetailResponse.model_validate(response_data)


@router.get(
    "/documents/{document_id}/history",
    response_model=DocumentHistoryResponse,
    summary="Get persisted evidence history for a document",
)
async def get_document_history_endpoint(
    document_id: UUID,
    use_case: GetDocumentHistoryUseCase = Depends(get_document_history_use_case),
) -> DocumentHistoryResponse:
    return await use_case.execute(document_id)


@router.get(
    "/documents/{document_id}/relationship-explanation",
    response_model=DocumentRelationshipExplanationResponse,
    summary="Get a grounded relationship explanation for a document",
)
async def get_document_relationship_explanation_endpoint(
    document_id: UUID,
    _user_id: CurrentUserId,
    use_case: GetDocumentRelationshipExplanationUseCase = Depends(
        get_document_relationship_explanation_use_case
    ),
) -> DocumentRelationshipExplanationResponse:
    return await use_case.execute(document_id)


@router.get(
    "/documents/{document_id}/entities",
    response_model=list[DocumentEntityResponse],
    summary="Get extracted entities for a document",
)
async def get_document_entities_endpoint(
    document_id: UUID,
    _user_id: CurrentUserId,
    use_case: GetDocumentWithClausesUseCase = Depends(get_get_document_with_clauses_use_case),
) -> list[DocumentEntityResponse]:
    document = await use_case.execute(document_id)

    entities: list[DocumentEntityResponse] = []
    for clause in document.clauses:
        evidence_location = (
            clause.extracted_entities.get("evidence_location", {})
            if clause.extracted_entities
            else {}
        )
        entities.append(
            DocumentEntityResponse(
                id=clause.id,
                type="clause",
                text=clause.title or clause.full_text or clause.clause_code,
                page=int(evidence_location.get("page_number") or 1),
                confidence=float(clause.extraction_confidence or 1.0),
                metadata={
                    "clause_code": clause.clause_code,
                    "clause_type": clause.clause_type.value if clause.clause_type else None,
                    "evidence_location": {
                        "page_number": int(evidence_location.get("page_number") or 1),
                        "bbox": evidence_location.get("bbox") or [0.08, 0.12, 0.84, 0.06],
                        "normalized": bool(evidence_location.get("normalized", True)),
                    },
                },
            )
        )

    return entities


@router.get(
    "/documents/{document_id}/download",
    summary="Download document file by ID",
)
async def download_document_endpoint(
    document_id: UUID,
    user_id: CurrentUserId,
    download_use_case: DownloadDocumentUseCase = Depends(get_download_use_case),
):
    file_path, media_type = await download_use_case.execute(document_id, user_id)
    return FileResponse(path=file_path, filename=file_path.name, media_type=media_type)


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document by ID",
)
async def delete_document_endpoint(
    document_id: UUID,
    user_id: CurrentUserId,
    delete_use_case: DeleteDocumentUseCase = Depends(get_delete_use_case),
):
    await delete_use_case.execute(document_id, user_id)
    return status.HTTP_204_NO_CONTENT


@router.get(
    "/projects/{project_id}/documents",
    response_model=DocumentListResponse,
    summary="List documents for a project",
)
async def list_documents_for_project(
    project_id: UUID,
    tenant_id: CurrentTenantId,
    _user_id: CurrentUserId,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    list_use_case: ListProjectDocumentsUseCase = Depends(get_list_documents_use_case),
) -> DocumentListResponse:
    documents, total_count = await list_use_case.execute(
        project_id=project_id,
        tenant_id=tenant_id,
        skip=skip,
        limit=limit,
    )

    items = [
        DocumentListItem(
            id=doc.id,
            filename=doc.filename,
            document_type=doc.document_type.value if doc.document_type else None,
            status=_normalize_document_status_for_polling(doc.upload_status),
            status_detail=_document_status_detail_for_polling(doc.upload_status),
            error_message=doc.parsing_error if doc.upload_status == DocumentStatus.ERROR else None,
            uploaded_at=doc.created_at,
            file_size_bytes=doc.file_size_bytes or 0,
        )
        for doc in documents
    ]
    return DocumentListResponse(items=items, total_count=total_count, skip=skip, limit=limit)


@router.post(
    "/documents/{document_id}/parse",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Parse a document by ID",
)
@router.post(
    "/{document_id}/parse",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Parse a document by ID",
    include_in_schema=False,
)
async def parse_document_endpoint(
    document_id: UUID,
    _user_id: CurrentUserId,
    parse_use_case: ParseDocumentUseCase = Depends(get_parse_document_use_case),
):
    await parse_use_case.execute(document_id, _user_id)
    return DocumentUploadResponse(
        document_id=document_id,
        status=DocumentStatus.PARSED,
        message="Document parsed successfully",
    )


@router.post(
    "/projects/{project_id}/documents/{document_id}/reprocess",
    response_model=DocumentQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-trigger async processing for a stuck or errored document",
)
async def reprocess_document_endpoint(
    project_id: UUID,
    document_id: UUID,
    _user_id: CurrentUserId,
    _tenant_id: CurrentTenantId,
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
) -> DocumentQueuedResponse:
    """
    Re-dispatch a Celery processing task for a document stuck in queued, uploaded,
    or error state. Resets the document status to UPLOADED and enqueues a fresh
    parse + analysis run.
    """
    document = await repo.get_by_id(document_id)
    if not document or document.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    await repo.update_status(document_id, DocumentStatus.UPLOADED, parsing_error=None)
    await repo.commit()
    await repo.refresh(document)

    response_data = DocumentResponse.model_validate(document).model_dump()
    response_data["task_id"] = _enqueue_document_processing(document_id)
    response_data["processing_status"] = DocumentPollingStatus.QUEUED
    response_data["status_detail"] = (
        "Document status reset successfully. Background reprocessing will start when the worker is available."
        if response_data["task_id"] is None
        else "Document reprocessing has been queued."
    )
    return DocumentQueuedResponse(**response_data)


@router.post(
    "/projects/{project_id}/rag/answer",
    response_model=RagAnswerResponse,
    summary="Ask a question about project documents (RAG)",
)
async def answer_project_question(
    project_id: UUID,
    payload: RagQuestionRequest,
    _user_id: CurrentUserId,
    _tenant_id: CurrentTenantId,
    use_case: AnswerRagQuestionUseCase = Depends(get_answer_rag_use_case),
):
    result = await use_case.execute(
        question=payload.question,
        project_id=project_id,
        top_k=payload.top_k or 5,
    )
    return RagAnswerResponse(
        answer=result.answer,
        sources=[
            {
                "content": chunk.content,
                "metadata": chunk.metadata,
                "similarity": chunk.similarity,
            }
            for chunk in result.sources
        ],
    )
