"""
Data Transfer Objects (DTOs) for the Documents application layer.

DTOs are simple data carriers used to transfer data between layers,
especially between the presentation (e.g., API) and application layers.
They help to decouple the core business logic from the specific details
of the API, making the system more modular and easier to test.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.core.json_types import JsonDict
from src.documents.domain.models import Document, DocumentStatus, DocumentType


@dataclass(frozen=True)
class CreateDocumentDTO:
    """DTO for creating a new document."""
    project_id: UUID
    tenant_id: UUID
    filename: str
    document_type: DocumentType
    # Optional fields
    file_format: str | None = None
    storage_url: str | None = None
    file_size_bytes: int | None = None
    created_by: UUID | None = None
    document_metadata: JsonDict | None = None


@dataclass(frozen=True)
class DocumentDTO:
    """
    DTO for document use case responses.
    Part of TASK-BCK-023.
    """
    id: UUID
    project_id: UUID
    tenant_id: UUID
    document_type: DocumentType
    filename: str
    upload_status: DocumentStatus
    version: int
    file_hash: str | None
    file_format: str | None = None
    storage_url: str | None = None
    file_size_bytes: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @staticmethod
    def from_domain(document: Document) -> "DocumentDTO":
        """Create DTO from domain model."""
        return DocumentDTO(
            id=document.id,
            project_id=document.project_id,
            tenant_id=document.tenant_id,
            document_type=document.document_type,
            filename=document.filename,
            upload_status=document.upload_status,
            version=document.version,
            file_hash=document.file_hash,
            file_format=document.file_format,
            storage_url=document.storage_url,
            file_size_bytes=document.file_size_bytes,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )


@dataclass(frozen=True)
class RetrievedChunk:
    """DTO for retrieved document chunks."""
    content: str
    metadata: JsonDict
    similarity: float


@dataclass(frozen=True)
class RagAnswer:
    """DTO for RAG answers."""
    answer: str
    sources: list[RetrievedChunk] = field(default_factory=list)


class DocumentPollingStatus(StrEnum):
    """Polling status exposed to clients."""
    QUEUED = "queued"
    PROCESSING = "processing"
    PARSED = "parsed"
    ERROR = "error"


class DocumentLifecycleStatus(StrEnum):
    """User-facing lifecycle state; unlike the polling status it never merges
    "parsed", "analysis pending" and "analyzed".

    #712: PARSED_PENDING_ANALYSIS is durably overloaded -- the same stored
    status covers "analysis not started yet", "analysis ran and paused for
    HITL review", and "analysis ran and came back incomplete/retryable".
    document_lifecycle_status() below disambiguates those three using
    context that already exists durably (a pending review_items row; the
    document's own analysis_last_attempt_incomplete metadata flag) rather
    than inventing a new stored status for them. NEEDS_CHANGES is the one
    case that DOES get its own stored DocumentStatus (set by
    finalize_v3's reject path), because "a human rejected this" is a durable
    fact the document row itself must carry, not something to re-derive from
    a join every time.
    """
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PARSED = "parsed"
    ANALYSIS_PENDING = "analysis_pending"
    REVIEW_REQUIRED = "review_required"
    ANALYZED = "analyzed"
    NEEDS_CHANGES = "needs_changes"
    FAILED_RETRYABLE = "failed_retryable"
    ERROR = "error"


_LIFECYCLE_BY_STORED_STATUS = {
    DocumentStatus.UPLOADED: DocumentLifecycleStatus.UPLOADED,
    DocumentStatus.QUEUED: DocumentLifecycleStatus.UPLOADED,
    DocumentStatus.PARSING: DocumentLifecycleStatus.PROCESSING,
    DocumentStatus.PARSED: DocumentLifecycleStatus.PARSED,
    DocumentStatus.ANALYZED: DocumentLifecycleStatus.ANALYZED,
    DocumentStatus.NEEDS_CHANGES: DocumentLifecycleStatus.NEEDS_CHANGES,
    DocumentStatus.ERROR: DocumentLifecycleStatus.ERROR,
}


def document_lifecycle_status(
    status: DocumentStatus,
    *,
    has_pending_review: bool = False,
    analysis_attempt_failed: bool = False,
) -> DocumentLifecycleStatus:
    """Map the stored document status (+ durable context) to its lifecycle state.

    PARSED_PENDING_ANALYSIS is context-sensitive: a pending HITL review
    (``has_pending_review``) means analysis ran and is waiting on a human,
    never "not started"; a recorded failed attempt with no pending review
    (``analysis_attempt_failed``) means the automatic pipeline gave up and a
    user-triggered retry is the honest next step. Every other stored status
    maps 1:1, unconditionally.
    """
    if status == DocumentStatus.PARSED_PENDING_ANALYSIS:
        if has_pending_review:
            return DocumentLifecycleStatus.REVIEW_REQUIRED
        if analysis_attempt_failed:
            return DocumentLifecycleStatus.FAILED_RETRYABLE
        return DocumentLifecycleStatus.ANALYSIS_PENDING
    return _LIFECYCLE_BY_STORED_STATUS[status]


# Lifecycle states the existing reprocess endpoint (POST .../reprocess) can
# genuinely recover: it unconditionally resets upload_status to UPLOADED and
# re-enqueues parsing + analysis, which is a real fix for a system/parsing
# fault (ERROR) or an exhausted automatic analysis attempt (FAILED_RETRYABLE).
# It is NOT offered for REVIEW_REQUIRED (a decision is pending, not a retry)
# or NEEDS_CHANGES (a human already decided; re-upload/correction is the
# honest next step, not blindly re-running the same pipeline).
_RETRYABLE_LIFECYCLE_STATUSES = frozenset(
    {DocumentLifecycleStatus.ERROR, DocumentLifecycleStatus.FAILED_RETRYABLE}
)


def document_is_retryable(lifecycle_status: DocumentLifecycleStatus) -> bool:
    """Whether the UI's Retry action is honest for this lifecycle state."""
    return lifecycle_status in _RETRYABLE_LIFECYCLE_STATUSES


class DocumentResponse(BaseModel):
    """Base response DTO for documents."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    tenant_id: UUID
    document_type: DocumentType
    filename: str
    upload_status: DocumentStatus
    file_format: str | None = None
    storage_url: str | None = None
    storage_encrypted: bool = True
    file_size_bytes: int | None = None
    parsed_at: datetime | None = None
    parsing_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    version: int = 1  # TASK-BCK-023
    file_hash: str | None = None  # TASK-BCK-023


class DocumentQueuedResponse(DocumentResponse):
    """Response for async document upload."""
    processing_status: DocumentPollingStatus = DocumentPollingStatus.QUEUED
    status_detail: str = "Upload accepted. Ingestion is queued; analysis has not started."
    task_id: str | None = None


class DocumentUploadResponse(BaseModel):
    """Response for parse endpoints."""
    document_id: UUID
    status: DocumentStatus
    message: str


class DocumentListItem(BaseModel):
    """List item for documents."""
    id: UUID
    filename: str
    document_type: str | None = None
    status: DocumentPollingStatus
    status_detail: str
    lifecycle_status: DocumentLifecycleStatus
    retryable: bool = False
    review_count: int | None = None
    review_item_id: UUID | None = None
    error_message: str | None = None
    uploaded_at: datetime | None = None
    file_size_bytes: int | None = None


class DocumentListResponse(BaseModel):
    """Paginated list response for documents."""
    items: list[DocumentListItem]
    total_count: int
    skip: int
    limit: int


class DocumentDetailResponse(DocumentResponse):
    """Detailed document response."""
    clauses: list[JsonDict] | None = None


class EvidenceHistoryEventResponse(BaseModel):
    """A persisted evidence-history event for a document timeline."""

    id: str
    title: str
    detail: str
    occurred_at: datetime
    source_type: str | None = None
    source_id: str | None = None


class DocumentHistoryResponse(BaseModel):
    """Ordered history events for a single document."""

    document_id: UUID
    items: list[EvidenceHistoryEventResponse]


class RelationshipExplanationCitationResponse(BaseModel):
    """Citation payload for a relationship explanation."""

    clause_id: UUID
    clause_code: str
    label: str
    page: int | None = None
    reason: str


class DocumentRelationshipExplanationResponse(BaseModel):
    """Structured relationship explanation payload for a document."""

    document_id: UUID
    summary: str
    strongest_cluster: str
    review_priority: str
    latest_signal: str
    citations: list[RelationshipExplanationCitationResponse]


class RagQuestionRequest(BaseModel):
    """Request for RAG questions."""
    question: str
    top_k: int | None = None


class RagAnswerResponse(BaseModel):
    """Response for RAG answers."""
    answer: str
    sources: list[JsonDict] = field(default_factory=list)


class DocumentEntityResponse(BaseModel):
    """Entity extracted or derived from a persisted document."""
    id: UUID
    type: str
    text: str
    page: int | None = None
    confidence: float
    metadata: JsonDict = Field(default_factory=dict)
