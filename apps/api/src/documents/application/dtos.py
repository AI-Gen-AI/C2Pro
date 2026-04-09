"""
Data Transfer Objects (DTOs) for the Documents application layer.

DTOs are simple data carriers used to transfer data between layers,
especially between the presentation (e.g., API) and application layers.
They help to decouple the core business logic from the specific details
of the API, making the system more modular and easier to test.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.documents.domain.models import Document, DocumentStatus, DocumentType


@dataclass(frozen=True)
class CreateDocumentDTO:
    """DTO for creating a new document."""
    project_id: UUID
    filename: str
    document_type: DocumentType
    # Optional fields
    file_format: str | None = None
    storage_url: str | None = None
    file_size_bytes: int | None = None
    created_by: UUID | None = None
    document_metadata: dict | None = None


@dataclass(frozen=True)
class DocumentDTO:
    """
    DTO for document use case responses.
    Part of TASK-BCK-023.
    """
    id: UUID
    project_id: UUID
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
    metadata: dict
    similarity: float


@dataclass(frozen=True)
class RagAnswer:
    """DTO for RAG answers."""
    answer: str
    sources: list[RetrievedChunk] = field(default_factory=list)


class DocumentPollingStatus(str, Enum):
    """Polling status exposed to clients."""
    QUEUED = "queued"
    PROCESSING = "processing"
    PARSED = "parsed"
    ERROR = "error"


class DocumentResponse(BaseModel):
    """Base response DTO for documents."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
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
    clauses: list[dict] | None = None


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
    sources: list[dict] = field(default_factory=list)


class DocumentEntityResponse(BaseModel):
    """Entity extracted or derived from a persisted document."""
    id: UUID
    type: str
    text: str
    page: int
    confidence: float
    metadata: dict = Field(default_factory=dict)
