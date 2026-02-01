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

from pydantic import BaseModel

from src.documents.domain.models import DocumentStatus, DocumentType


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


class DocumentQueuedResponse(DocumentResponse):
    """Response for async document upload."""
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
    status: DocumentPollingStatus
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


class RagQuestionRequest(BaseModel):
    """Request for RAG questions."""
    question: str
    top_k: int | None = None


class RagAnswerResponse(BaseModel):
    """Response for RAG answers."""
    answer: str
    sources: list[dict] = field(default_factory=list)
