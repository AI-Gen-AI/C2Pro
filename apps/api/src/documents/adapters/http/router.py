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
from sqlalchemy import select, text
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
from src.documents.application.reextract_budget_source_units import (
    BudgetReextractionError,
    reextract_budget_source_units,
)
from src.documents.application.reupload_document_use_case import (
    ReuploadDocumentUseCase,  # TASK-BCK-023
)
from src.documents.application.services.relationship_explanation_service import (
    EvidenceRelationshipExplanationService,
)
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import DocumentStatus, DocumentType
from src.documents.domain.upload_policy import (
    UPLOAD_EXTENSIONS,
    WBS_ANALYSIS_EXCLUDED_DETAIL,
    UploadFormatError,
    is_analysis_excluded,
    require_upload_extension,
)
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
from src.temporal.adapters.persistence.revision_status_reader import SqlAlchemyRevisionStatusReader
from src.temporal.application.revision_status import RevisionStatus

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

# PC-2b.3: the union of every type's formats; each type is then checked against its OWN set
# (``.csv`` / ``.json`` belong to a ``wbs`` source only and can never reach the contract pipeline).
ALLOWED_EXTENSIONS = set(UPLOAD_EXTENSIONS)
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
        # PQ-HITL-09 S2: unknown media types are 415, while a valid extension
        # assigned to the wrong structured document family remains 400.
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{file_extension}' is not allowed.",
        )
    if document_type is not None:
        try:
            require_upload_extension(document_type, file_extension)
        except UploadFormatError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
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

# Read-only diagnosis for legacy failed attempts written before the durable
# N4 machine-readable blocker was implemented. Never modify budget or data.
N4MissingCapLookup = Callable[[UUID, UUID, list[UUID]], Awaitable[set[UUID]]]


def get_missing_n4_cap_lookup(
    db: AsyncSession = Depends(get_session),
) -> N4MissingCapLookup:
    async def _lookup(
        tenant_id: UUID, project_id: UUID, document_ids: list[UUID],
    ) -> set[UUID]:
        if not document_ids:
            return set()
        absent: set[UUID] = set()
        for document_id in document_ids:
            # Only an actual N4 budget-denied run plus missing cap may be
            # labeled "Budget required"; unrelated ERRORs remain unrelated.
            result = await db.scalar(text("""
                SELECT EXISTS(
                    SELECT 1
                      FROM public.n4_extraction_runs r
                      JOIN public.n4_extraction_windows w
                        ON w.run_id = r.run_id AND w.tenant_id = r.tenant_id
                     WHERE r.tenant_id = CAST(:tenant AS uuid)
                       AND r.project_id = CAST(:project AS uuid)
                       AND r.document_id = CAST(:document AS uuid)
                       AND w.status = 'BLOCKED'
                       AND w.blocked_reason = 'BUDGET_OR_RESERVATION_UNAVAILABLE'
                ) AND (
                  NOT EXISTS (
                    SELECT 1 FROM public.n4_budget_buckets b
                    WHERE b.tenant_id = CAST(:tenant AS uuid)
                      AND b.scope_kind = 'PROJECT'
                      AND b.scope_id = CAST(:project AS uuid)
                      AND b.period_key = to_char(
                        clock_timestamp() AT TIME ZONE 'UTC','YYYY-MM'
                      )
                  )
                  OR NOT EXISTS (
                    SELECT 1 FROM public.n4_budget_buckets b
                    WHERE b.tenant_id = CAST(:tenant AS uuid)
                      AND b.scope_kind = 'DOCUMENT'
                      AND b.scope_id = CAST(:document AS uuid)
                      AND b.period_key = to_char(
                        clock_timestamp() AT TIME ZONE 'UTC','YYYY-MM'
                      )
                  )
                )
            """), {
                "tenant": str(tenant_id), "project": str(project_id),
                "document": str(document_id),
            })
            if result is True:
                absent.add(document_id)
        return absent

    return _lookup



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


_N4_UNSAFE_REPROCESS_BLOCKERS = frozenset({
    "N4_PARTIAL_RESULTS",
    "N4_PRIOR_RUN_RECONCILIATION_REQUIRED",
})


def _document_status_detail(
    status: DocumentStatus,
    lifecycle: DocumentLifecycleStatus,
    review_count: int | None,
    analysis_blocker_code: str | None = None,
) -> str:
    """Context-aware status detail. Falls back to the polling-only text for
    every lifecycle state that isn't one of #712's new truthful states, so
    existing copy for UPLOADED/PROCESSING/PARSED/ANALYSIS_PENDING/ANALYZED/
    ERROR is unchanged."""
    if analysis_blocker_code == "N4_PARTIAL_RESULTS":
        return (
            "Partial N4 findings are available but not approved. "
            "Open the proposed findings to see analyzed windows, evidence and "
            "unresolved references. Automatic retry is disabled."
        )
    if analysis_blocker_code == "N4_PRIOR_RUN_RECONCILIATION_REQUIRED":
        return (
            "An earlier N4 execution requires financial reconciliation. "
            "Previously persisted findings may still be available. "
            "Automatic retry is disabled to prevent duplicate charges."
        )
    if analysis_blocker_code == "N4_BUDGET_NOT_CONFIGURED":
        return (
            "AI budget authorization required: no approved N4 spending cap "
            "is configured for this project/document. The document was "
            "parsed, but contractual AI analysis has not run. "
            "Retry will not work until the budget is configured."
        )
    if analysis_blocker_code == "N4_BUDGET_EXCEEDED":
        return (
            "AI budget limit reached. Contractual AI analysis is incomplete. "
            "An authorized budget decision is required before retrying."
        )
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


def _wbs_source_status_detail(status: DocumentStatus) -> str:
    """PC-2b.3: a WBS source's truthful state -- it is never queued for, or waiting on, analysis."""
    if status == DocumentStatus.PARSED:
        return "WBS source parsed by the deterministic WBS importer. It is never analysed."
    if status == DocumentStatus.ERROR:
        return "The WBS import has blocking diagnostics. Fix the source and upload a new revision."
    return f"WBS source stored. {WBS_ANALYSIS_EXCLUDED_DETAIL}"


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
    if is_analysis_excluded(document_type):
        # PC-2b.3: a WBS source is never ingested or analysed -- nothing is enqueued.
        response_data["task_id"] = None
        response_data["processing_status"] = DocumentPollingStatus.QUEUED
        response_data["status_detail"] = _wbs_source_status_detail(DocumentStatus.UPLOADED)
        return DocumentQueuedResponse(**response_data)
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
        if isinstance(e, UploadFormatError) or str(e) == STRUCTURED_DOCX_ERROR:
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
    # This identity is sent only after GetDocumentWithClausesUseCase has
    # verified revision ownership within the requested tenant and document.
    # It does not confer TRUSTED status or mutate current lifecycle state.
    response_data["revision_id"] = revision_id
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
    "/documents/{document_id}/revisions",
    response_model=list[RevisionStatus],
    summary="Inspect a document's immutable revision trust states",
)
async def list_document_revision_statuses_endpoint(
    document_id: UUID,
    _user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    get_document: GetDocumentUseCase = Depends(get_get_document_use_case),
    revision_repository: SqlAlchemyDocumentRevisionRepository = Depends(
        get_document_revision_repository
    ),
    db: AsyncSession = Depends(get_session),
) -> list[RevisionStatus]:
    # Verify the document's tenant ownership before consulting lineage.
    # Read-side status is scoped to its exact tenant/project/document and a
    # missing status stays UNKNOWN rather than being promoted to TRUSTED.
    document = await get_document.execute(document_id, _user_id, tenant_id)
    lineage = await revision_repository.list_lineage(document_id, tenant_id)
    reader = SqlAlchemyRevisionStatusReader(db)
    states: list[RevisionStatus] = []
    trusted_current_seen = False
    for revision in lineage:
        if (
            revision.document_id != document_id
            or revision.tenant_id != tenant_id
            or revision.project_id != document.project_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found."
            )
        state = await reader.read(
            tenant_id=tenant_id,
            project_id=document.project_id,
            document_id=document_id,
            revision_id=revision.revision_id,
        )
        resolved_state = (
            state
            if state is not None
            else RevisionStatus.unavailable(
                revision.revision_id, "revision_status_not_available"
            )
        )
        # This endpoint also feeds the Evidence Viewer. The inventory use case
        # already rejects conflicting trusted-current statuses (#996); do not
        # expose contradictory labels through this alternate read path.
        if (
            resolved_state.status == "available"
            and resolved_state.trust_state == "trusted"
            and resolved_state.is_current is True
            and resolved_state.current_basis == "trusted"
        ):
            if trusted_current_seen:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Conflicting current trusted revisions.",
                )
            trusted_current_seen = True
        states.append(resolved_state)
    return states


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
        # Surface the *literal* technical section ID to the evidence UI as
        # unverified source metadata. This is not compliance, an approved WBS
        # reference, a page coordinate or a scored assessment.
        technical_source = (
            clause.extracted_entities.get("technical_requirement")
            if clause.extracted_entities
            else None
        )
        if isinstance(technical_source, dict):
            section = technical_source.get("source_section")
            if (
                isinstance(section, str)
                and section
                and all(part.isdigit() and 1 <= len(part) <= 3 for part in section.split("."))
            ):
                metadata["technical_requirement"] = {
                    "source_section": section,
                    "verification_status": "unverified",
                }
        entities.append(
            DocumentEntityResponse(
                id=clause.id,
                type="clause",
                text=clause.title or clause.full_text or clause.clause_code,
                page=page_number,
                # Unknown extraction confidence must never become a fabricated 100%.
                confidence=clause.extraction_confidence,
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
    revision_id: UUID | None = Query(
        default=None,
        description="Download this exact immutable, hash-verified revision (read-only).",
    ),
) -> FileResponse:
    if revision_id is None:
        file_path, media_type = await download_use_case.execute(document_id, user_id, tenant_id)
    else:
        file_path, media_type = await download_use_case.execute(
            document_id, user_id, tenant_id, revision_id=revision_id
        )
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
    missing_n4_cap_lookup: N4MissingCapLookup = Depends(get_missing_n4_cap_lookup),
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

    # Legacy blocked documents (before #1269) have no persisted blocker
    # code. A scoped read-only ledger/budget lookup diagnoses them without a
    # blind reprocess, additional AI spending or mutation of metadata.
    n4_candidates = [
        doc.id for doc in documents
        if (doc.document_metadata or {}).get("analysis_last_attempt_incomplete") is True
        and not (doc.document_metadata or {}).get("analysis_blocker_code")
        and doc.upload_status in (
            DocumentStatus.PARSED_PENDING_ANALYSIS, DocumentStatus.ERROR,
        )
    ]
    budget_missing: set[UUID] = set()
    if n4_candidates:
        pending = missing_n4_cap_lookup(tenant_id, project_id, n4_candidates)
        budget_missing = await pending if inspect.isawaitable(pending) else pending

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
        blocker_code = (doc.document_metadata or {}).get("analysis_blocker_code")
        if not blocker_code and doc.id in budget_missing:
            blocker_code = "N4_BUDGET_NOT_CONFIGURED"
        # A missing cap is not a transient failure; blind Retry merely
        # re-parses a full document without changing its budget permissions.
        budget_blocked = (
            blocker_code in (
                "N4_BUDGET_NOT_CONFIGURED", "N4_BUDGET_EXCEEDED",
                *_N4_UNSAFE_REPROCESS_BLOCKERS,
            )
            and lifecycle in (
                DocumentLifecycleStatus.FAILED_RETRYABLE, DocumentLifecycleStatus.ERROR,
            )
        )
        wbs_source = is_analysis_excluded(doc.document_type)
        items.append(
            DocumentListItem(
                id=doc.id,
                filename=doc.filename,
                document_type=doc.document_type.value if doc.document_type is not None else None,
                status=_normalize_document_status_for_polling(doc.upload_status),
                status_detail=_wbs_source_status_detail(doc.upload_status) if wbs_source else _document_status_detail(
                    doc.upload_status,
                    lifecycle,
                    review_count if has_pending_review else None,
                    blocker_code if budget_blocked else None,
                ),
                lifecycle_status=lifecycle,
                retryable=not wbs_source and not budget_blocked and document_is_retryable(lifecycle),
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
    expected_revision_id: UUID | None = None,
    expected_generation: int | None = None,
    expected_stage: str | None = None,
    expected_phase: str | None = None,
    expected_outcome: str | None = None,
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
    if is_analysis_excluded(document.document_type):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=WBS_ANALYSIS_EXCLUDED_DETAIL)
    # H-04: the UI's retryable=false is not a server-side authorization rule.
    if (document.document_metadata or {}).get("analysis_blocker_code") in _N4_UNSAFE_REPROCESS_BLOCKERS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="N4 findings or earlier usage require supervised reconciliation, not automatic reprocessing.",
        )
    # A pilot-marked document cannot be sent through a normal retry that
    # would re-enable the N4 -> N12 route. Only CORE's pinned pilot
    # endpoint (new generation, new authority) may operate on it.
    if isinstance((document.document_metadata or {}).get("n4_only_pilot"), dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="N4-only pilot is restricted to its approved operation",
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

    # A legacy or interrupted analysis may not have reached the metadata
    # update. Check durable receipts for the current source revision instead.
    previous_n4_usage = (await repo.session.execute(text("""
        SELECT EXISTS (
            SELECT 1
              FROM public.n4_usage_reservations u
              JOIN public.n4_extraction_runs r
                ON r.tenant_id = u.tenant_id AND r.run_id = u.run_id
              JOIN public.document_revisions dr
                ON dr.tenant_id = r.tenant_id
               AND dr.document_id = r.document_id
               AND dr.revision_id = r.document_revision_id
             WHERE r.tenant_id = CAST(:tenant AS uuid)
               AND r.project_id = CAST(:project AS uuid)
               AND r.document_id = CAST(:document AS uuid)
               AND dr.valid_to IS NULL
               AND u.status IN ('RESERVED', 'UNKNOWN', 'SETTLED')
        )
    """), {
        "tenant": str(tenant_id),
        "project": str(project_id),
        "document": str(document_id),
    })).scalar_one()
    if previous_n4_usage:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Earlier N4 usage exists for this revision; reconcile before reprocessing.",
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
        if all(value is None for value in expected_authority):
            generation = await repo.begin_processing_generation(tenant_id, document_id)
        else:
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
    "/projects/{project_id}/documents/{document_id}/n4-only-pilot/reprocess",
    response_model=DocumentQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Explicit scoped N4-only research pilot (no N12, HITL, or TRUSTED)",
)
async def reprocess_n4_only_pilot_endpoint(
    project_id: UUID,
    document_id: UUID,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
) -> DocumentQueuedResponse:
    """Use the official fenced generation/reprocess machinery, NEVER a SQL reset.

    Disabled unless an expiring one-document, one-owner, one-revision UAT scope
    was provisioned separately by CORE. This endpoint cannot enable arbitrary
    N4-only mode for any other contract.
    """
    from src.analysis.application.n4_only_pilot_policy import (
        N4OnlyPilotDenied,
        N4OnlyPilotScope,
        pilot_marker,
    )

    try:
        scope = N4OnlyPilotScope.from_environment()
        scope.check_target(
            tenant_id=tenant_id, project_id=project_id, document_id=document_id,
            revision_id=scope.revision_id, generation=scope.next_generation,
            scope_digest=scope.digest, user_id=user_id,
        )
    except N4OnlyPilotDenied as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="N4-only pilot not authorized") from exc

    document = await repo.get_by_id(tenant_id, document_id)
    if (
        document is None or document.project_id != project_id
        or document.upload_status != DocumentStatus.ERROR
        or document.document_type != DocumentType.CONTRACT
        or (document.document_metadata or {}).get("parsed_text_revision_id") != str(scope.revision_id)
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="N4-only pilot source is not the pinned retryable contract")

    # Row locks and exact expected lineage prevent racing with an upload,
    # another reprocess, or a recovery worker; no metadata write can commit
    # until the generation CAS succeeds.
    op = (await repo.session.execute(text("""
        SELECT revision_id, generation, stage, phase, outcome, fencing_token
          FROM public.document_processing_operations
         WHERE tenant_id = CAST(:tenant AS uuid) AND document_id = CAST(:document AS uuid)
         FOR UPDATE
    """), {"tenant": str(tenant_id), "document": str(document_id)})).mappings().one_or_none()
    if not op or (
        str(op["revision_id"]) != str(scope.revision_id)
        or op["generation"] != scope.predecessor_generation
        or op["fencing_token"] != scope.predecessor_fence
        or str(op["stage"]) != "ANALYSIS"
        or str(op["phase"]) != "FAILED"
        or str(op["outcome"]) != "fail_retryable"
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="N4-only pilot processing authority has changed")

    metadata = dict(document.document_metadata or {})
    metadata["n4_only_pilot"] = pilot_marker(scope)
    await repo.update_metadata(tenant_id, document_id, metadata)
    await repo.update_status(tenant_id, document_id, DocumentStatus.UPLOADED, parsing_error=None)
    try:
        generation = await repo.begin_processing_generation(
            tenant_id, document_id,
            expected_revision_id=scope.revision_id,
            expected_generation=scope.predecessor_generation,
            expected_stage="ANALYSIS",
            expected_phase="FAILED",
            expected_outcome="fail_retryable",
        )
    except ProcessingAuthorityLost as exc:
        await repo.session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="N4-only pilot retry lost the generation CAS") from exc
    if generation != scope.next_generation:
        await repo.session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="N4-only pilot unexpected new generation")
    await repo.commit()
    await repo.refresh(document)
    payload = DocumentResponse.model_validate(document).model_dump()
    payload["task_id"] = _enqueue_document_processing(
        document_id, revision_id=scope.revision_id, generation=generation
    )
    payload["processing_status"] = DocumentPollingStatus.QUEUED
    payload["status_detail"] = (
        "N4-only pilot ingestion queued; N12/approval will not run."
        if payload["task_id"] else
        "N4-only pilot generation reserved, but worker enqueue unavailable; manual recovery needed."
    )
    return DocumentQueuedResponse(**payload)


@router.post(
    "/projects/{project_id}/documents/{document_id}/n4-only-pilot/recover-enqueue",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manual recovery of a stranded N4-only enqueue, under a new fenced claim",
)
async def recover_n4_only_enqueue_endpoint(
    project_id: UUID,
    document_id: UUID,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
) -> dict[str, object]:
    """Recover COMMITTED CAS -> NO broker ack without resetting the generation.

    Only a separately enabled, server-authorized owner can claim a queued
    INGESTION attempt that has never reached N4. No auto-retry, no provider,
    no generic recovery and NO N12. Failed dispatch retains the CLAIMED
    DB-clock lease, so the next manual claim cannot duplicate a live worker.
    """
    from src.documents.application.n4_only_enqueue_recovery import (
        N4OnlyEnqueueRecoveryDenied,
        claim_stranded_n4_enqueue,
    )

    try:
        claimed = await claim_stranded_n4_enqueue(
            repo=repo, tenant_id=tenant_id, project_id=project_id,
            document_id=document_id, user_id=user_id,
        )
        # The CLAIMED authority and audit event must be durable before any
        # broker interaction. If this commit fails, no task is sent.
        await repo.commit()
    except N4OnlyEnqueueRecoveryDenied as exc:
        await repo.session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="N4-only enqueue recovery denied; verify owner, fence and receipts",
        ) from exc

    # Exact authority handshake; duplicate messages cannot both adopt it.
    # Reuse the original INGESTION task; the existing trigger selects the
    # N4-only ANALYSIS task from the server-persisted marker.
    task_id: str | None = None
    try:
        from src.core.tasks.ingestion_tasks import process_document_async

        task = process_document_async.apply_async(
            kwargs={
                "document_id": str(document_id),
                "revision_id": str(claimed.revision_id),
                "generation": claimed.generation,
                "authority": claimed.authority.to_message(),
            },
            task_id=f"n4-pilot-recovery-{claimed.authority.attempt_id}",
        )
        task_id = getattr(task, "id", None)
    except Exception:
        # An exception can mean broker rejection OR lost acknowledgement.
        # Never roll back the committed grant and never enqueue a second
        # task now. Wait for DB lease expiry and a *new* owner command.
        logger.exception(
            "n4_only_recovery_broker_ack_unknown",
            document_id=str(document_id),
            generation=claimed.generation,
            fencing_token=claimed.authority.fencing_token,
            attempt_id=str(claimed.authority.attempt_id),
        )

    if task_id is None:
        logger.warning(
            "n4_only_recovery_claimed_but_not_confirmed",
            document_id=str(document_id),
            generation=claimed.generation,
            fencing_token=claimed.authority.fencing_token,
        )
    else:
        logger.info(
            "n4_only_recovery_enqueued",
            document_id=str(document_id),
            generation=claimed.generation,
            fencing_token=claimed.authority.fencing_token,
            task_id=task_id,
        )
    return {
        "status": "ENQUEUED" if task_id else "BROKER_ACK_UNKNOWN_STOP",
        "task_id": task_id,
        "document_revision_id": str(claimed.revision_id),
        "generation": claimed.generation,
        "fencing_token": claimed.authority.fencing_token,
        "n4_billable_in_this_request": False,
        "n12_status": "UNASSESSED",
        "retry_policy": "MANUAL_AFTER_LEASE_AND_RECEIPT_PREFLIGHT_ONLY",
    }


@router.get(
    "/projects/{project_id}/documents/{document_id}/n4-findings",
    summary="Read the pinned N4 run's provisional candidates without approval",
)
async def read_n4_partial_findings(
    project_id: UUID,
    document_id: UUID,
    user_id: CurrentUserId,  # noqa: ARG001 -- authentication required
    tenant_id: CurrentTenantId,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
) -> dict[str, object]:
    """Read durable PROPOSED candidates; never invoke N4, HITL or Score.

    The document's fenced analysis result pins run, source digest and revision.
    A newer empty retry must not erase a prior run containing valid evidence.
    """
    import re

    doc = await repo.get_by_id(tenant_id, document_id)
    if doc is None or doc.project_id != project_id:
        raise HTTPException(status_code=404, detail="document unavailable")
    metadata = doc.document_metadata or {}
    run_raw = metadata.get("analysis_n4_run_id")
    revision_raw = metadata.get("analysis_n4_revision_id")
    digest = metadata.get("analysis_n4_source_sha256")
    if not run_raw or not revision_raw or not digest:
        # NOT_AVAILABLE is not the claim that the contract contains zero risks.
        return {
            "status": "RESULTS_NOT_AVAILABLE", "findings": [],
            "total_findings": None, "coverage": None,
            "n12_status": "UNASSESSED", "original_pdf_coverage": "UNVERIFIED",
            "trusted": False, "approvable": False,
        }
    try:
        pinned_run = UUID(str(run_raw))
        pinned_revision = UUID(str(revision_raw))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=404, detail="N4 run unavailable") from exc
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise HTTPException(status_code=404, detail="N4 source identity unavailable")

    run = (await repo.session.execute(text("""
        SELECT r.run_id, r.status, r.total_windows, r.generation
          FROM public.n4_extraction_runs r
          JOIN public.document_revisions dr
            ON dr.tenant_id = r.tenant_id
           AND dr.document_id = r.document_id
           AND dr.revision_id = r.document_revision_id
           AND dr.valid_to IS NULL
          JOIN public.document_processing_operations op
            ON op.tenant_id = r.tenant_id
           AND op.document_id = r.document_id
           AND op.revision_id = r.document_revision_id
           AND op.generation >= r.generation
         WHERE r.tenant_id = CAST(:tenant AS uuid)
           AND r.project_id = CAST(:project AS uuid)
           AND r.document_id = CAST(:document AS uuid)
           AND r.document_revision_id = CAST(:revision AS uuid)
           AND r.run_id = CAST(:run AS uuid)
           AND r.source_sha256 = :digest
    """), {
        "tenant": str(tenant_id), "project": str(project_id),
        "document": str(document_id), "revision": str(pinned_revision),
        "run": str(pinned_run), "digest": digest,
    })).mappings().one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="N4 run unavailable or superseded")

    windows = (await repo.session.execute(text("""
        SELECT w.ordinal, w.status, w.blocked_reason, w.unresolved_refs,
               (w.committed_at IS NOT NULL
                AND w.findings_sha256 IS NOT NULL) AS has_result
          FROM public.n4_extraction_windows w
         WHERE w.tenant_id = CAST(:tenant AS uuid)
           AND w.run_id = CAST(:run AS uuid)
         ORDER BY w.ordinal
    """), {"tenant": str(tenant_id), "run": str(pinned_run)})).mappings().all()
    read_count = sum(1 for w in windows if w["has_result"])
    examined = sum(1 for w in windows if w["status"] == "EXAMINED")
    blocked = sum(1 for w in windows if w["status"] == "BLOCKED")
    count = (await repo.session.execute(text("""
        SELECT count(*) FROM public.n4_candidate_findings
         WHERE tenant_id = CAST(:tenant AS uuid)
           AND run_id = CAST(:run AS uuid)
    """), {"tenant": str(tenant_id), "run": str(pinned_run)})).scalar_one()
    rows = (await repo.session.execute(text("""
        SELECT f.finding_key, f.window_ordinal, f.claim, f.source_refs
          FROM public.n4_candidate_findings f
         WHERE f.tenant_id = CAST(:tenant AS uuid)
           AND f.run_id = CAST(:run AS uuid)
         ORDER BY f.window_ordinal, f.finding_key
         LIMIT :limit OFFSET :offset
    """), {
        "tenant": str(tenant_id), "run": str(pinned_run),
        "limit": limit, "offset": offset,
    })).mappings().all()
    findings: list[dict[str, object]] = []
    for row in rows:
        claim = row["claim"] if isinstance(row["claim"], dict) else {}
        refs = row["source_refs"] if isinstance(row["source_refs"], list) else []
        # Both the claim and its immutable span must attest the N2 quote.
        # A forged/mismatched source ref alone must never elevate a quote.
        matched_n2 = (
            claim.get("source_evidence_status") == "EXACT_MODEL_SAFE_MATCH"
            and isinstance(claim.get("source_quote"), str)
            and bool(claim["source_quote"].strip())
            and any(
                isinstance(ref, dict)
                and ref.get("document_revision_id") == str(pinned_revision)
                and ref.get("source_sha256") == digest
                and ref.get("source_kind") == "MODEL_SAFE_PROJECTION"
                and ref.get("evidence_status") == "EXACT_MODEL_SAFE_MATCH"
                and isinstance(ref.get("analysis_span"), list)
                and len(ref["analysis_span"]) == 2
                and all(type(value) is int and value >= 0 for value in ref["analysis_span"])
                and ref["analysis_span"][1] > ref["analysis_span"][0]
                for ref in refs
            )
        )
        findings.append({
            "finding_key": row["finding_key"],
            "window_ordinal": row["window_ordinal"],
            "title": str(claim.get("title") or "Untitled provisional finding"),
            "interpretation": str(claim.get("risk_reason") or ""),
            "clause_ref": claim.get("clause_ref"),
            "source_quote": claim.get("source_quote") if matched_n2 else None,
            "n2_quote_status": "N2_EXACT_MATCH" if matched_n2 else "NOT_LOCATED",
            "original_pdf_quote_status": "UNVERIFIED",
            "severity": "UNASSESSED",
            "review_state": "PROPOSED",
            "approvable": False,
        })
    return {
        "status": "PARTIAL_UNASSESSED" if run["status"] != "COMPLETE"
            else "PROPOSED_UNASSESSED",
        "run_id": str(pinned_run),
        "document_revision_id": str(pinned_revision),
        "ledger_status": str(run["status"]),
        "total_findings": int(count), "offset": offset, "limit": limit,
        "findings": findings,
        "coverage": {
            "total": int(run["total_windows"]),
            "windows_with_result": read_count,
            "examined": examined,
            "blocked": blocked,
            "windows": [
                {
                    "ordinal": int(w["ordinal"]), "status": str(w["status"]),
                    "blocked_reason": w["blocked_reason"],
                    "unresolved_refs": w["unresolved_refs"] or [],
                    "has_result": bool(w["has_result"]),
                }
                for w in windows
            ],
            "semantic_recall_certified": False,
            "original_pdf_coverage_certified": False,
        },
        "n12_status": "UNASSESSED", "original_pdf_coverage": "UNVERIFIED",
        "trusted": False, "approvable": False,
    }


@router.get(
    "/projects/{project_id}/documents/{document_id}/n4-only-pilot/findings",
    summary="Read the authorized N4 pilot ledger; N2 citations are NOT PDF-verified",
)
async def read_n4_only_pilot_findings(
    project_id: UUID,
    document_id: UUID,
    user_id: CurrentUserId,
    tenant_id: CurrentTenantId,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
) -> dict[str, object]:
    """Owner-scoped read-only output, independent of automatic HITL creation."""
    from src.analysis.application.n4_only_pilot_policy import (
        N4OnlyPilotDenied,
        require_readable_pilot,
    )

    doc = await repo.get_by_id(tenant_id, document_id)
    if doc is None or doc.project_id != project_id:
        raise HTTPException(status_code=404, detail="document unavailable")
    marker = (doc.document_metadata or {}).get("n4_only_pilot")
    if not isinstance(marker, dict):
        raise HTTPException(status_code=404, detail="pilot findings unavailable")
    generation = marker.get("generation")
    if not isinstance(generation, int) or isinstance(generation, bool):
        raise HTTPException(status_code=404, detail="pilot findings unavailable")
    try:
        scope = require_readable_pilot(
            marker, tenant_id=tenant_id, project_id=project_id,
            document_id=document_id,
            revision_id=marker.get("revision_id") if isinstance(marker, dict) else None,
            generation=generation,
            user_id=user_id,
        )
        if (doc.document_metadata or {}).get("parsed_text_revision_id") != str(scope.revision_id):
            raise N4OnlyPilotDenied("N4 pilot document revision has been superseded")
    except N4OnlyPilotDenied as exc:
        raise HTTPException(status_code=404, detail="pilot findings unavailable") from exc

    # The trusted DB metadata, not an unvalidated query parameter, chooses
    # the exact tenant/doc/revision/generation. No writes or approval endpoint.
    run = (await repo.session.execute(text("""
        SELECT r.run_id, r.status, r.fencing_token, r.total_windows
          FROM public.n4_extraction_runs r
          JOIN public.document_processing_operations op
            ON op.tenant_id = r.tenant_id
           AND op.document_id = r.document_id
           AND op.revision_id = r.document_revision_id
           AND op.generation = r.generation
           AND op.fencing_token = r.fencing_token
         WHERE r.tenant_id = CAST(:tenant AS uuid)
           AND r.project_id = CAST(:project AS uuid)
           AND r.document_id = CAST(:document AS uuid)
           AND r.document_revision_id = CAST(:revision AS uuid)
           AND r.source_sha256 = :source_sha
           AND r.generation = :generation
           AND r.fencing_token > :predecessor_fence
           AND EXISTS (
               SELECT 1 FROM public.document_revisions dr
                WHERE dr.document_id = r.document_id
                  AND dr.tenant_id = r.tenant_id
                  AND dr.revision_id = r.document_revision_id
                  AND dr.valid_to IS NULL
           )
         ORDER BY r.created_at DESC LIMIT 1
    """), {
        "tenant": str(tenant_id), "project": str(project_id),
        "document": str(document_id), "revision": str(scope.revision_id),
        "generation": scope.next_generation,
        "source_sha": scope.source_sha256,
        "predecessor_fence": scope.predecessor_fence,
    })).mappings().one_or_none()
    if run is None:
        # Queued without a persisted run is possible. PARTIAL without one
        # could be a crash before any window was booked; don't imply
        # COMPLETED and don't open a retry or create any review.
        if marker["state"] == "QUEUED":
            return {
                "status": "NOT_RUN", "findings": [], "total_findings": 0,
                "n12_status": "UNASSESSED", "original_pdf_coverage": "UNVERIFIED",
            }
        raise HTTPException(status_code=404, detail="pilot run unavailable or superseded")
    count = (await repo.session.execute(text("""
        SELECT count(*) FROM public.n4_candidate_findings
         WHERE tenant_id = CAST(:tenant AS uuid) AND run_id = CAST(:run AS uuid)
    """), {"tenant": str(tenant_id), "run": str(run["run_id"])})).scalar_one()
    rows = (await repo.session.execute(text("""
        SELECT f.finding_key, f.window_ordinal, f.claim, f.source_refs
          FROM public.n4_candidate_findings f
         WHERE f.tenant_id = CAST(:tenant AS uuid)
           AND f.run_id = CAST(:run AS uuid)
         ORDER BY f.window_ordinal, f.finding_key
         LIMIT :limit OFFSET :offset
    """), {
        "tenant": str(tenant_id), "run": str(run["run_id"]),
        "limit": limit, "offset": offset,
    })).mappings().all()
    items: list[dict[str, object]] = []
    for row in rows:
        claim = row["claim"] if isinstance(row["claim"], dict) else {}
        refs = row["source_refs"] if isinstance(row["source_refs"], list) else []
        exact = any(
            isinstance(ref, dict)
            and ref.get("source_kind") == "MODEL_SAFE_PROJECTION"
            and ref.get("evidence_status") == "EXACT_MODEL_SAFE_MATCH"
            and isinstance(ref.get("analysis_span"), list)
            for ref in refs
        )
        items.append({
            "finding_key": row["finding_key"],
            "window_ordinal": row["window_ordinal"],
            "claim": claim,
            "n2_source_refs": refs,
            "n2_quote_status": "VERIFIED_IN_N2" if exact else "UNVERIFIED_IN_N2",
            "pdf_quote_status": "UNVERIFIED",
            "review_state": "PROPOSED",
        })
    return {
        "status": (
            "PARTIAL_UNASSESSED" if marker["state"] == "PARTIAL_UNASSESSED"
            else str(run["status"])
        ),
        "pilot_status": marker["state"],
        "ledger_status": str(run["status"]),
        "run_id": str(run["run_id"]),
        "document_revision_id": str(scope.revision_id),
        "generation": scope.next_generation,
        "fencing_token": int(run["fencing_token"]),
        "total_windows": int(run["total_windows"]),
        "total_findings": count,
        "offset": offset, "limit": limit,
        "findings": items,
        "n12_status": "UNASSESSED",
        "original_pdf_coverage": "UNVERIFIED",
        "trusted": False,
    }


@router.post(
    "/projects/{project_id}/documents/{document_id}/reextract-source-units",
    summary="Re-derive the original XLSX budget rows of the current, already analysed revision",
)
async def reextract_budget_source_units_endpoint(
    project_id: UUID,
    document_id: UUID,
    expected_revision_id: UUID,
    expected_blob_hash: str,
    user_id: CurrentUserId,  # noqa: ARG001
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_session),
    repo: SqlAlchemyDocumentRepository = Depends(get_document_repository),
    rev_repo: SqlAlchemyDocumentRevisionRepository = Depends(get_document_revision_repository),
    storage: IStorageService = Depends(get_storage_service),
    file_parser: CompositeFileParser = Depends(get_file_parser_service),
) -> JsonDict:
    """Recompute only ``document_source_units`` and the revision-keyed summaries of the current
    revision from its SHA-256-verified original bytes. Same document, revision and hash; no
    reprocess, no N4/N12, no LLM, no change to analysis/HITL state. Idempotent and CAS-guarded."""
    try:
        return await reextract_budget_source_units(
            session=db,
            document_repository=repo,
            revision_repository=rev_repo,
            storage=storage,
            file_parser=file_parser,
            tenant_id=tenant_id,
            project_id=project_id,
            document_id=document_id,
            expected_revision_id=expected_revision_id,
            expected_blob_hash=expected_blob_hash,
        )
    except BudgetReextractionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc


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
