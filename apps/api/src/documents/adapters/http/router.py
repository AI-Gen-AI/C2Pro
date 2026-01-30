"""
HTTP adapter (FastAPI router) for the Documents module.
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
from src.core.security import CurrentTenantId, CurrentUserId
from src.documents.adapters.parsers.bc3_file_parser import BC3FileParser
from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.adapters.rag.legacy_rag_ingestion_service import (
    LegacyRagIngestionService,
)
from src.documents.adapters.rag.rag_service_adapter import SqlAlchemyRagService
from src.documents.adapters.extraction.legacy_entity_extraction_service import (
    LegacyEntityExtractionService,
)
from src.documents.adapters.storage.local_file_storage_service import (
    LocalFileStorageService,
)
from src.documents.application.delete_document_use_case import DeleteDocumentUseCase
from src.documents.application.download_document_use_case import DownloadDocumentUseCase
from src.documents.application.get_document_use_case import GetDocumentUseCase
from src.documents.application.get_document_with_clauses_use_case import (
    GetDocumentWithClausesUseCase,
)
from src.documents.application.list_project_documents_use_case import (
    ListProjectDocumentsUseCase,
)
from src.documents.application.parse_document_use_case import ParseDocumentUseCase
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.application.answer_rag_question_use_case import AnswerRagQuestionUseCase
from src.documents.domain.models import DocumentStatus, DocumentType
from src.documents.application.dtos import (
    DocumentDetailResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentPollingStatus,
    DocumentQueuedResponse,
    DocumentResponse,
    DocumentUploadResponse,
    RagAnswerResponse,
    RagQuestionRequest,
)

logger = structlog.get_logger()

router = APIRouter(
    prefix="",
    tags=["Documents"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
    },
)

ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".bc3"}


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


# --- Dependency wiring ---
def get_document_repository(db: AsyncSession = Depends(get_session)) -> SqlAlchemyDocumentRepository:
    return SqlAlchemyDocumentRepository(session=db)


def get_storage_service() -> LocalFileStorageService:
    return LocalFileStorageService()


def get_file_parser_service() -> CompositeFileParser:
    return CompositeFileParser(
        bc3_parser=BC3FileParser(),
        excel_parser=ExcelFileParser(),
        pdf_parser=PDFFileParser(),
    )


def get_entity_extraction_service() -> LegacyEntityExtractionService:
    return LegacyEntityExtractionService()


def get_rag_ingestion_service() -> LegacyRagIngestionService:
    return LegacyRagIngestionService()


def get_upload_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    storage: LocalFileStorageService = Depends(get_storage_service),
) -> UploadDocumentUseCase:
    return UploadDocumentUseCase(document_repository=repo, storage_service=storage)


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
) -> ListProjectDocumentsUseCase:
    return ListProjectDocumentsUseCase(document_repository=repo)

def get_get_document_with_clauses_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
) -> GetDocumentWithClausesUseCase:
    return GetDocumentWithClausesUseCase(document_repository=repo)


def get_parse_document_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    storage: LocalFileStorageService = Depends(get_storage_service),
    file_parser: CompositeFileParser = Depends(get_file_parser_service),
    entity_extraction: LegacyEntityExtractionService = Depends(get_entity_extraction_service),
    rag_ingestion: LegacyRagIngestionService = Depends(get_rag_ingestion_service),
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


@router.post(
    "/projects/{project_id}/documents",
    response_model=DocumentQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document for asynchronous processing",
)
async def upload_document_for_processing(
    project_id: UUID,
    user_id: CurrentUserId,
    _tenant_id: CurrentTenantId,
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    upload_use_case: UploadDocumentUseCase = Depends(get_upload_use_case),
) -> DocumentQueuedResponse:
    if file.size > settings.max_upload_size_bytes:
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
    )

    from src.core.tasks.ingestion_tasks import process_document_async

    task = process_document_async.delay(document_id=document.id)
    response_data = DocumentResponse.model_validate(document).model_dump()
    response_data["task_id"] = task.id
    return DocumentQueuedResponse(**response_data)


@router.get(
    "/documents/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get document details by ID",
)
async def get_document_endpoint(
    document_id: UUID,
    user_id: CurrentUserId,
    use_case: GetDocumentWithClausesUseCase = Depends(get_get_document_with_clauses_use_case),
) -> DocumentDetailResponse:
    document = await use_case.execute(document_id)
    return DocumentDetailResponse.model_validate(document)


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
    user_id: CurrentUserId,
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
            status=_normalize_document_status_for_polling(doc.upload_status),
            error_message=doc.parsing_error if doc.upload_status == DocumentStatus.ERROR else None,
            uploaded_at=doc.created_at,
            file_size_bytes=doc.file_size_bytes or 0,
        )
        for doc in documents
    ]
    return DocumentListResponse(items=items, total_count=total_count, skip=skip, limit=limit)


@router.post(
    "/{document_id}/parse",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Parse a document by ID",
)
async def parse_document_endpoint(
    document_id: UUID,
    user_id: CurrentUserId,
    parse_use_case: ParseDocumentUseCase = Depends(get_parse_document_use_case),
):
    await parse_use_case.execute(document_id, user_id)
    return DocumentUploadResponse(
        document_id=document_id,
        status=DocumentStatus.PARSED,
        message="Document parsed successfully",
    )


@router.post(
    "/projects/{project_id}/rag/answer",
    response_model=RagAnswerResponse,
    summary="Ask a question about project documents (RAG)",
)
async def answer_project_question(
    project_id: UUID,
    payload: RagQuestionRequest,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
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
