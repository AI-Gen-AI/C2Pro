"""
HTTP adapter (FastAPI router) for the Documents module.

Refers to Test Suite ID: TASK-OPS-DOCFLOW-009.
"""
from __future__ import annotations

import inspect
import os
import pathlib
import tempfile
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import cast
from uuid import UUID

import structlog
from anyio import open_file
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.database import get_session
from src.core.json_types import JsonDict
from src.core.processing_authority import ProcessingAuthorityLost
from src.core.repositories import get_project_repository
from src.core.security import CurrentTenantId, CurrentUserId, security_scheme
from src.documents.adapters.extraction.documents_entity_extraction_service import (
    DocumentsEntityExtractionService,
)
from src.documents.adapters.parsers.bc3_file_parser import BC3FileParser
from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser
from src.documents.adapters.parsers.docx_file_parser import DocxFileParser
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.adapters.rag.rag_service import (
    RagProjectNotFoundError,
    RagProviderUnavailableError,
)
from src.documents.adapters.rag.rag_service_adapter import SqlAlchemyRagService
from src.documents.adapters.rag.sqlalchemy_rag_ingestion_service import (
    SqlAlchemyRagIngestionService,
)
from src.documents.adapters.storage.factory import build_storage_service
from src.documents.application.answer_rag_question_use_case import AnswerRagQuestionUseCase
from src.documents.application.delete_document_use_case import DeleteDocumentUseCase
from src.documents.application.download_document_use_case import DownloadDocumentUseCase
from src.documents.application.dtos import (
    DocumentDetailResponse,
    DocumentEntityResponse,
    DocumentHistoryResponse,
    DocumentLifecycleStatus,
    DocumentListItem,
    DocumentListResponse,
    DocumentPollingStatus,
    DocumentQueuedResponse,
    DocumentRelationshipExplanationResponse,
    DocumentResponse,
    DocumentUploadResponse,
    RagAnswerResponse,
    RagQuestionRequest,
    document_is_retryable,
    document_lifecycle_status,
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
from src.documents.ports.storage_service import IStorageService
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.domain.entities import ReviewStatus
from src.projects.ports.project_repository import ProjectRepository

# Cross-module dependencies for entity extraction
from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)
from src.stakeholders.application.create_stakeholder_use_case import CreateStakeholderUseCase
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)

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

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".bc3"}
STRUCTURED_DOCUMENT_TYPES = {DocumentType.BUDGET, DocumentType.SCHEDULE}
STRUCTURED_DOCX_ERROR = "budget/schedule require .xlsx/.bc3"

# EPIC-OPS-DOCFLOW Stream A: bound how much of an upload we ever hold in a
# single chunk. A naive `await file.read()` materializes the entire upload
# as one contiguous bytes object — for a >100MB construction spec that is a
# real OOM risk, especially under concurrent uploads.
_UPLOAD_STREAM_CHUNK_BYTES = 8 * 1024 * 1024  # 8MB


def _get_upload_file_size(file: UploadFile) -> int:
    size = getattr(file, "size", None)
    if isinstance(size, int):
        return size

    current_position = file.file.tell()
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(current_position)
    return size


async def _stream_upload_to_tempfile(file: UploadFile, max_bytes: int) -> pathlib.Path:
    """Stream an upload to a temp file on disk in bounded chunks.

    Never holds more than one ~8MB chunk in memory at a time, and aborts as
    soon as the running total exceeds `max_bytes` — without ever reading (or
    writing) more than the cap allows, even for a caller that lies about
    Content-Length or omits it. Caller owns deleting the returned path.
    """
    fd, tmp_name = tempfile.mkstemp(suffix=".upload")
    # mkstemp returns a raw fd; hand the write path to anyio's async file API
    # (offloaded to a worker thread) so the event loop is never blocked by
    # synchronous file I/O.
    os.close(fd)
    total = 0
    try:
        async with await open_file(tmp_name, "wb") as tmp_file:
            while True:
                chunk = await file.read(_UPLOAD_STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File size exceeds limit of {settings.max_upload_size_mb}MB.",
                    )
                await tmp_file.write(chunk)
    except Exception:
        with suppress(OSError):
            os.unlink(tmp_name)
        raise

    return pathlib.Path(tmp_name)


def _validate_upload_extension(
    file_extension: str,
    document_type: DocumentType | None = None,
) -> None:
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{file_extension}' is not allowed.",
        )
    if (
        file_extension == ".docx"
        and document_type is not None
        and document_type in STRUCTURED_DOCUMENT_TYPES
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=STRUCTURED_DOCX_ERROR,
        )


def _enqueue_document_processing(
    document_id: UUID, revision_id: UUID | None = None, generation: int | None = None
) -> str | None:
    try:
        from src.core.tasks.ingestion_tasks import process_document_async

        if process_document_async is None:
            logger.warning("document_processing_task_unavailable", document_id=str(document_id))
            return None

        # P0b: a pinned revision_id makes the worker read that immutable object even if a
        # newer revision is uploaded before the task runs.
        kwargs: dict[str, object] = {
            "document_id": str(document_id),
            "revision_id": str(revision_id) if revision_id is not None else None,
        }
        # #711: a reprocess pins the new processing generation it started.
        if generation is not None:
            kwargs["generation"] = generation
        task = process_document_async.delay(**kwargs)
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
    if status == DocumentStatus.ANALYZED:
        # Terminal success. The polling enum has no dedicated "analyzed" member;
        # clients render PARSED as "Analyzed" and treat it as a ready document.
        # Without this, an analyzed document fell through to PROCESSING and the UI
        # showed it stuck on "processing" forever even though analysis finished.
        return DocumentPollingStatus.PARSED
    if status == DocumentStatus.ERROR:
        return DocumentPollingStatus.ERROR
    if status == DocumentStatus.NEEDS_CHANGES:
        # #712: a human rejection is durable, terminal-for-now attention -- the
        # polling enum has no dedicated member for it, so it surfaces the same
        # as a system error rather than as still-processing.
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
    if status == DocumentStatus.ANALYZED:
        return "Document analysis completed."
    if status == DocumentStatus.ERROR:
        return "Document processing failed before analysis could start."
    return "Document ingestion is still in progress. Analysis has not started."


# #712: the two review statuses that mean "a human decision is still pending" --
# APPROVED/REJECTED/ESCALATED/CLOSED/DRAFT items are not what makes a document
# say REVIEW_REQUIRED.
_PENDING_REVIEW_STATUSES = (
    ReviewStatus.PENDING_REVIEW_REQUIRED,
    ReviewStatus.PENDING_REVIEW_CONDITIONAL,
    ReviewStatus.ESCALATED,
)

# (pending_review_count, exact_item_id_if_exactly_one_else_None) per document_id.
PendingReviewLookup = Callable[[UUID, list[UUID]], Awaitable[dict[UUID, tuple[int, UUID | None]]]]


async def _fetch_pending_review_counts(
    tenant_id: UUID, document_ids: list[UUID], db: AsyncSession
) -> dict[UUID, tuple[int, UUID | None]]:
    """Group pending HITL review items by document, so the Documents list can
    say "review required" truthfully without guessing which item to link to
    when more than one is pending (#712)."""
    if not document_ids:
        return {}

    result = await db.execute(
        select(ReviewItemORM.document_id, ReviewItemORM.item_id).where(
            ReviewItemORM.tenant_id == tenant_id,
            ReviewItemORM.document_id.in_(document_ids),
            ReviewItemORM.current_status.in_(_PENDING_REVIEW_STATUSES),
        )
    )
    item_ids_by_document: dict[UUID, list[UUID]] = {}
    for document_id, item_id in result.all():
        item_ids_by_document.setdefault(document_id, []).append(item_id)

    return {
        document_id: (len(item_ids), item_ids[0] if len(item_ids) == 1 else None)
        for document_id, item_ids in item_ids_by_document.items()
    }


def get_pending_review_document_ids(
    db: AsyncSession = Depends(get_session),
) -> PendingReviewLookup:
    async def _lookup(tenant_id: UUID, document_ids: list[UUID]) -> dict[UUID, tuple[int, UUID | None]]:
        return await _fetch_pending_review_counts(tenant_id, document_ids, db)

    return _lookup


def _document_status_detail(
    status: DocumentStatus,
    lifecycle: DocumentLifecycleStatus,
    review_count: int | None,
) -> str:
    """Context-aware status detail. Falls back to the polling-only text for
    every lifecycle state that isn't one of #712's new truthful states, so
    existing copy for UPLOADED/PROCESSING/PARSED/ANALYSIS_PENDING/ANALYZED/
    ERROR is unchanged."""
    if lifecycle == DocumentLifecycleStatus.REVIEW_REQUIRED:
        if review_count is not None and review_count > 1:
            return (
                f"{review_count} reviews are pending for this document. "
                "Open the project review queue to act on them."
            )
        return "Analysis completed and is waiting for a human review decision."
    if lifecycle == DocumentLifecycleStatus.FAILED_RETRYABLE:
        return "Automatic analysis did not complete after several attempts. Retry to try again."
    if lifecycle == DocumentLifecycleStatus.NEEDS_CHANGES:
        return "A reviewer requested changes. Upload a corrected version to continue."
    return _document_status_detail_for_polling(status)


# --- Dependency wiring ---
def get_document_repository(
    db: AsyncSession = Depends(get_session),
) -> SqlAlchemyDocumentRepository:
    return SqlAlchemyDocumentRepository(session=db)


def get_storage_service() -> IStorageService:
    return build_storage_service()


def get_file_parser_service() -> CompositeFileParser:
    return CompositeFileParser(
        bc3_parser=BC3FileParser(),
        excel_parser=ExcelFileParser(),
        pdf_parser=PDFFileParser(),
        docx_parser=DocxFileParser(),
    )


def get_entity_extraction_service(
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_session),
    doc_repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
) -> DocumentsEntityExtractionService:
    # Use factories to provide fresh use cases with current session
    def stakeholder_factory() -> CreateStakeholderUseCase:
        repo = SqlAlchemyStakeholderRepository(session=db)
        return CreateStakeholderUseCase(repository=repo, document_repository=doc_repo)

    return DocumentsEntityExtractionService(
        stakeholder_use_case_factory=stakeholder_factory,
        # #852 / #860: no WBS or BOM writer -- a schedule / budget is observed,
        # never written as canonical WBS / BOM.
        user_id=user_id,
    )


def get_rag_ingestion_service(
    db: AsyncSession = Depends(get_session),
) -> SqlAlchemyRagIngestionService:
    return SqlAlchemyRagIngestionService(db_session=db)


def get_document_revision_repository(
    db: AsyncSession = Depends(get_session),
) -> SqlAlchemyDocumentRevisionRepository:
    return SqlAlchemyDocumentRevisionRepository(session=db)


def get_project_event_repository(
    db: AsyncSession = Depends(get_session),
) -> SqlAlchemyProjectEventRepository:
    return SqlAlchemyProjectEventRepository(session=db)


def get_upload_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    storage: IStorageService = Depends(get_storage_service),
    project_repo: ProjectRepository = Depends(get_project_repository),
    rev_repo: SqlAlchemyDocumentRevisionRepository = Depends(get_document_revision_repository),
    event_repo: SqlAlchemyProjectEventRepository = Depends(get_project_event_repository),
) -> UploadDocumentUseCase:
    return UploadDocumentUseCase(
        document_repository=repo,
        storage_service=storage,
        project_repository=project_repo,
        revision_repository=rev_repo,
        event_repository=event_repo,
    )


def get_reupload_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    rev_repo: SqlAlchemyDocumentRevisionRepository = Depends(get_document_revision_repository),
    storage: IStorageService = Depends(get_storage_service),
    event_repo: SqlAlchemyProjectEventRepository = Depends(get_project_event_repository),
) -> ReuploadDocumentUseCase:
    return ReuploadDocumentUseCase(
        document_repository=repo,
        revision_repository=rev_repo,
        storage_service=storage,
        event_repository=event_repo,
    )


def get_get_document_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
) -> GetDocumentUseCase:
    return GetDocumentUseCase(document_repository=repo)


def get_download_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    storage: IStorageService = Depends(get_storage_service),
    get_document: GetDocumentUseCase = Depends(get_get_document_use_case),
    rev_repo: SqlAlchemyDocumentRevisionRepository = Depends(get_document_revision_repository),
) -> DownloadDocumentUseCase:
    return DownloadDocumentUseCase(
        document_repository=repo,
        storage_service=storage,
        get_document_use_case=get_document,
        revision_repository=rev_repo,
    )


def get_delete_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    storage: IStorageService = Depends(get_storage_service),
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
    revision_repository: SqlAlchemyDocumentRevisionRepository = Depends(
        get_document_revision_repository
    ),
) -> GetDocumentWithClausesUseCase:
    return GetDocumentWithClausesUseCase(
        document_repository=repo, revision_repository=revision_repository
    )


def get_parse_document_use_case(
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    storage: IStorageService = Depends(get_storage_service),
    file_parser: CompositeFileParser = Depends(get_file_parser_service),
    entity_extraction: DocumentsEntityExtractionService = Depends(get_entity_extraction_service),
    rag_ingestion: SqlAlchemyRagIngestionService = Depends(get_rag_ingestion_service),
    rev_repo: SqlAlchemyDocumentRevisionRepository = Depends(get_document_revision_repository),
) -> ParseDocumentUseCase:
    return ParseDocumentUseCase(
        document_repository=repo,
        storage_service=storage,
        file_parser_service=file_parser,
        entity_extraction_service=entity_extraction,
        rag_ingestion_service=rag_ingestion,
        revision_repository=rev_repo,
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
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required.",
        )

    file_size = _get_upload_file_size(file)

    if file_size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds limit of {settings.max_upload_size_mb}MB.",
        )

    file_extension = pathlib.Path(file.filename).suffix.lower()
    _validate_upload_extension(file_extension, document_type)

    document = await upload_use_case.execute(
        project_id=project_id,
        file=file,
        document_type=document_type,
        user_id=user_id,
        tenant_id=tenant_id,
    )
    response_data = DocumentResponse.model_validate(document).model_dump()
    created_revision_id = getattr(upload_use_case, "created_revision_id", None)
    response_data["task_id"] = _enqueue_document_processing(
        document.id, created_revision_id if isinstance(created_revision_id, UUID) else None
    )
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
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
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
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required.",
        )

    # Fast-path reject on a declared size that's already over the cap, before
    # streaming a single byte to disk.
    declared_size = _get_upload_file_size(file)
    if declared_size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds limit of {settings.max_upload_size_mb}MB.",
        )

    file_extension = pathlib.Path(file.filename).suffix.lower()
    _validate_upload_extension(file_extension)

    # EPIC-OPS-DOCFLOW Stream A: stream to disk in bounded chunks rather than
    # `await file.read()`, which would materialize the whole upload as one
    # contiguous in-memory bytes object (OOM risk for large construction
    # specs). The declared-size check above is a fast rejection only — this
    # streaming loop is the real, enforced cap: it aborts mid-stream the
    # moment actual bytes received exceed the limit, regardless of what the
    # client claimed.
    tmp_path = await _stream_upload_to_tempfile(file, settings.max_upload_size_bytes)
    try:
        file_content = tmp_path.read_bytes()
    finally:
        with suppress(OSError):
            tmp_path.unlink()

    try:
        document_dto = await reupload_use_case.execute(
            tenant_id=tenant_id,
            document_id=document_id,
            file_content=file_content,
            filename=file.filename,
            user_id=user_id,
        )
    except ValueError as e:
        if str(e) == STRUCTURED_DOCX_ERROR:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
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
        tenant_id=document_dto.tenant_id,
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
    revision_id: UUID | None = Query(
        default=None,
        description=(
            "Read the clauses of this historical revision instead of the document's "
            "trusted-current revision. Never changes what is current."
        ),
    ),
) -> DocumentDetailResponse:
    document = await use_case.execute(
        tenant_id=tenant_id, document_id=document_id, revision_id=revision_id
    )
    response_data = DocumentResponse.model_validate(document).model_dump()
    response_data["clauses"] = [
        {
            "id": clause.id,
            "project_id": clause.project_id,
            "document_id": clause.document_id,
            "clause_code": clause.clause_code,
            "clause_type": clause.clause_type.value if clause.clause_type is not None else None,
            "title": clause.title,
            "full_text": clause.full_text,
            "text_start_offset": clause.text_start_offset,
            "text_end_offset": clause.text_end_offset,
            "extracted_entities": clause.extracted_entities,
            "extraction_confidence": clause.extraction_confidence,
            "extraction_model": clause.extraction_model,
            "manually_verified": clause.manually_verified,
            "verified_at": clause.verified_at,
            "revision_id": clause.revision_id,
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
    tenant_id: CurrentTenantId,
    use_case: GetDocumentHistoryUseCase = Depends(get_document_history_use_case),
) -> DocumentHistoryResponse:
    return await use_case.execute(tenant_id=tenant_id, document_id=document_id)


@router.get(
    "/documents/{document_id}/relationship-explanation",
    response_model=DocumentRelationshipExplanationResponse,
    summary="Get a grounded relationship explanation for a document",
)
async def get_document_relationship_explanation_endpoint(
    document_id: UUID,
    _user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    use_case: GetDocumentRelationshipExplanationUseCase = Depends(
        get_document_relationship_explanation_use_case
    ),
) -> DocumentRelationshipExplanationResponse:
    return await use_case.execute(tenant_id=tenant_id, document_id=document_id)


@router.get(
    "/documents/{document_id}/entities",
    response_model=list[DocumentEntityResponse],
    summary="Get extracted entities for a document",
)
async def get_document_entities_endpoint(
    document_id: UUID,
    _user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    use_case: GetDocumentWithClausesUseCase = Depends(get_get_document_with_clauses_use_case),
    revision_repository: SqlAlchemyDocumentRevisionRepository = Depends(
        get_document_revision_repository
    ),
    revision_id: UUID | None = Query(
        default=None,
        description=(
            "Read the entities of this historical revision instead of the document's "
            "trusted-current revision. Never changes what is current."
        ),
    ),
) -> list[DocumentEntityResponse]:
    document = await use_case.execute(
        tenant_id=tenant_id, document_id=document_id, revision_id=revision_id
    )

    revision_validity: dict[str, bool] = {}
    entities: list[DocumentEntityResponse] = []
    for clause in document.clauses:
        evidence_location = cast(
            JsonDict,
            clause.extracted_entities.get("evidence_location", {})
            if clause.extracted_entities
            else {},
        )
        raw_revision_id = evidence_location.get("revision_id")
        revision_binding_valid = True
        if raw_revision_id is not None:
            revision_key = str(raw_revision_id)
            if revision_key not in revision_validity:
                try:
                    revision_uuid = UUID(revision_key)
                except (TypeError, ValueError):
                    revision_validity[revision_key] = False
                else:
                    revision = await revision_repository.get_by_id(revision_uuid, tenant_id)
                    revision_validity[revision_key] = bool(
                        revision is not None
                        and revision.document_id == document_id
                        and revision.tenant_id == tenant_id
                    )
            revision_binding_valid = revision_validity[revision_key]

        raw_page = evidence_location.get("page_number")
        page_number = (
            int(raw_page)
            if revision_binding_valid
            and isinstance(raw_page, (int, float, str))
            and str(raw_page).lstrip("-").isdigit()
            and int(raw_page) > 0
            else None
        )
        raw_bbox = evidence_location.get("bbox")
        bbox = (
            [float(value) for value in raw_bbox]
            if revision_binding_valid
            and isinstance(raw_bbox, list)
            and len(raw_bbox) == 4
            and all(isinstance(value, (int, float)) for value in raw_bbox)
            else None
        )
        raw_pages = evidence_location.get("page_numbers")
        page_numbers = (
            sorted(
                {
                    int(value)
                    for value in raw_pages
                    if isinstance(value, (int, float, str))
                    and str(value).lstrip("-").isdigit()
                    and int(value) > 0
                }
            )
            if revision_binding_valid and isinstance(raw_pages, list)
            else []
        )
        metadata: JsonDict = {
            "clause_code": clause.clause_code,
            "clause_type": clause.clause_type.value if clause.clause_type is not None else None,
            "evidence_location": {
                "page_number": page_number,
                "page_numbers": page_numbers,
                "bbox": bbox,
                "revision_id": raw_revision_id,
                "normalized": bool(evidence_location.get("normalized", True)),
            },
        }
        entities.append(
            DocumentEntityResponse(
                id=clause.id,
                type="clause",
                text=clause.title or clause.full_text or clause.clause_code,
                page=page_number,
                confidence=float(clause.extraction_confidence or 1.0),
                metadata=metadata,
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
    tenant_id: CurrentTenantId,
    download_use_case: DownloadDocumentUseCase = Depends(get_download_use_case),
) -> FileResponse:
    file_path, media_type = await download_use_case.execute(document_id, user_id, tenant_id)
    return FileResponse(path=file_path, filename=file_path.name, media_type=media_type)


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document by ID",
)
async def delete_document_endpoint(
    document_id: UUID,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    delete_use_case: DeleteDocumentUseCase = Depends(get_delete_use_case),
) -> None:
    await delete_use_case.execute(document_id, user_id, tenant_id)


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
    pending_review_lookup: PendingReviewLookup = Depends(get_pending_review_document_ids),
) -> DocumentListResponse:
    documents, total_count = await list_use_case.execute(
        project_id=project_id,
        tenant_id=tenant_id,
        skip=skip,
        limit=limit,
    )

    # Only PARSED_PENDING_ANALYSIS documents can possibly have a pending HITL
    # review, so skip the query entirely when none are in this page (#712).
    pending_candidate_ids = [
        doc.id for doc in documents if doc.upload_status == DocumentStatus.PARSED_PENDING_ANALYSIS
    ]
    pending_by_document: dict[UUID, tuple[int, UUID | None]] = {}
    if pending_candidate_ids:
        lookup_result = pending_review_lookup(tenant_id, pending_candidate_ids)
        pending_by_document = (
            await lookup_result if inspect.isawaitable(lookup_result) else lookup_result
        )

    items = []
    for doc in documents:
        review_count, review_item_id = pending_by_document.get(doc.id, (0, None))
        has_pending_review = review_count > 0
        analysis_attempt_failed = bool(
            (doc.document_metadata or {}).get("analysis_last_attempt_incomplete")
        )
        lifecycle = document_lifecycle_status(
            doc.upload_status,
            has_pending_review=has_pending_review,
            analysis_attempt_failed=analysis_attempt_failed,
        )
        items.append(
            DocumentListItem(
                id=doc.id,
                filename=doc.filename,
                document_type=doc.document_type.value if doc.document_type is not None else None,
                status=_normalize_document_status_for_polling(doc.upload_status),
                status_detail=_document_status_detail(
                    doc.upload_status,
                    lifecycle,
                    review_count if has_pending_review else None,
                ),
                lifecycle_status=lifecycle,
                retryable=document_is_retryable(lifecycle),
                review_count=review_count if has_pending_review else None,
                review_item_id=review_item_id if has_pending_review else None,
                error_message=doc.parsing_error if doc.upload_status == DocumentStatus.ERROR else None,
                uploaded_at=doc.created_at,
                file_size_bytes=doc.file_size_bytes or 0,
            )
        )
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
    tenant_id: CurrentTenantId,
    parse_use_case: ParseDocumentUseCase = Depends(get_parse_document_use_case),
) -> DocumentUploadResponse:
    try:
        await parse_use_case.execute(tenant_id, document_id, _user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
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
    user_id: CurrentUserId,  # noqa: ARG001
    tenant_id: CurrentTenantId,
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    pending_review_lookup: PendingReviewLookup = Depends(
        get_pending_review_document_ids
    ),
    expected_revision_id: UUID | None = Query(default=None),
    expected_generation: int | None = Query(default=None, ge=1),
    expected_stage: str | None = Query(default=None),
    expected_phase: str | None = Query(default=None),
    expected_outcome: str | None = Query(default=None),
) -> DocumentQueuedResponse:
    """
    Re-dispatch a Celery processing task for a document stuck in queued, uploaded,
    or error state. Resets the document status to UPLOADED and enqueues a fresh
    parse + analysis run.
    """
    document = await repo.get_by_id(tenant_id, document_id)
    if not document or document.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied.",
        )

    expected_authority = (
        expected_revision_id,
        expected_generation,
        expected_stage,
        expected_phase,
        expected_outcome,
    )
    if any(value is not None for value in expected_authority) and any(
        value is None for value in expected_authority
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Expected processing authority must be supplied as a complete tuple.",
        )

    review_count = 0
    if document.upload_status == DocumentStatus.PARSED_PENDING_ANALYSIS:
        lookup_result = pending_review_lookup(tenant_id, [document_id])
        pending = (
            await lookup_result if inspect.isawaitable(lookup_result) else lookup_result
        )
        review_count, _review_item_id = pending.get(document_id, (0, None))

    lifecycle = document_lifecycle_status(
        document.upload_status,
        has_pending_review=review_count > 0,
        analysis_attempt_failed=bool(
            (document.document_metadata or {}).get(
                "analysis_last_attempt_incomplete"
            )
        ),
    )
    if not document_is_retryable(lifecycle):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Document cannot be retried while lifecycle state is "
                f"'{lifecycle.value}'."
            ),
        )

    # An explicit user retry starts a fresh bounded recovery budget while
    # preserving every unrelated piece of document metadata.
    metadata = dict(document.document_metadata or {})
    if metadata.pop("processing_recovery", None) is not None:
        await repo.update_metadata(tenant_id, document_id, metadata)

    await repo.update_status(tenant_id, document_id, DocumentStatus.UPLOADED, parsing_error=None)
    # #711: an explicit reprocess starts a new processing generation in the
    # same transaction, superseding any earlier (possibly still running) worker.
    try:
        generation = await repo.begin_processing_generation(
            tenant_id,
            document_id,
            expected_revision_id=expected_revision_id,
            expected_generation=expected_generation,
            expected_stage=expected_stage,
            expected_phase=expected_phase,
            expected_outcome=expected_outcome,
        )
    except ProcessingAuthorityLost as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Processing authority changed before retry; refresh and retry.",
        ) from exc
    await repo.commit()
    await repo.refresh(document)

    response_data = DocumentResponse.model_validate(document).model_dump()
    response_data["task_id"] = _enqueue_document_processing(document_id, generation=generation)
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
    tenant_id: CurrentTenantId,
    use_case: AnswerRagQuestionUseCase = Depends(get_answer_rag_use_case),
) -> RagAnswerResponse:
    try:
        result = await use_case.execute(
            question=payload.question,
            project_id=project_id,
            tenant_id=tenant_id,
            top_k=payload.top_k or 5,
        )
    except RagProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "RAG_PROVIDER_UNAVAILABLE",
                "message": str(exc),
                "retryable": True,
            },
        ) from exc
    except RagProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied.",
        ) from exc
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
