"""
Pydantic schemas for the Documents module.

This module defines the data transfer objects (DTOs) for documents and clauses,
used for API request validation and response serialization.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.modules.documents.models import ClauseType, DocumentStatus, DocumentType

# ---------------------------------------------------------------------------
# Base Schemas
# ---------------------------------------------------------------------------


class DocumentBase(BaseModel):
    """Base schema for document attributes."""

    filename: str = Field(..., min_length=1, max_length=255, description="Original filename of the document")
    document_type: DocumentType = Field(
        ..., description="Type of the document (e.g., CONTRACT, SCHEDULE)"
    )
    file_format: Optional[str] = Field(None, max_length=10, description="Format of the file (e.g., pdf, xlsx)")
    file_size_bytes: Optional[int] = Field(None, gt=0, description="Size of the file in bytes")

    @field_validator("file_size_bytes")
    @classmethod
    def validate_file_size(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("file_size_bytes must be positive")
        return v


class ClauseBase(BaseModel):
    """Base schema for clause attributes."""

    document_id: UUID = Field(..., description="ID of the document this clause belongs to")
    clause_code: str = Field(
        ..., description="Unique code or identifier for the clause within the document"
    )
    clause_type: Optional[ClauseType] = Field(
        None, description="Type of the clause (e.g., PAYMENT, LIABILITY)"
    )
    title: Optional[str] = Field(None, description="Title of the clause")
    full_text: Optional[str] = Field(None, description="Full text of the clause")
    extracted_entities: dict = Field(
        default_factory=dict, description="Entities extracted from the clause text by AI"
    )
    extraction_confidence: Optional[float] = Field(
        None, description="AI confidence score for the extraction"
    )
    manually_verified: bool = Field(
        False, description="Flag indicating if the clause has been manually verified"
    )


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------


class DocumentCreate(DocumentBase):
    """Schema for creating a new document record before file upload."""

    project_id: UUID = Field(..., description="ID of the project this document belongs to")
    storage_url: str = Field(..., description="URL where the document is stored")
    storage_encrypted: bool = Field(True, description="Whether the document is encrypted in storage")
    upload_status: DocumentStatus = Field(
        DocumentStatus.UPLOADED, description="Initial upload status"
    )
    retention_until: Optional[datetime] = Field(None, description="Date until document should be retained")
    created_by: Optional[UUID] = Field(None, description="ID of the user who created the document")
    metadata: dict = Field(default_factory=dict, description="Arbitrary metadata for the document")


class DocumentUpdate(BaseModel):
    """Schema for updating an existing document's metadata."""

    filename: Optional[str] = Field(None, min_length=1, max_length=255, description="New filename for the document")
    document_type: Optional[DocumentType] = Field(None, description="New type for the document")
    file_format: Optional[str] = Field(None, max_length=10, description="Updated file format")
    file_size_bytes: Optional[int] = Field(None, gt=0, description="Updated file size in bytes")
    storage_url: Optional[str] = Field(None, description="Updated storage URL")
    storage_encrypted: Optional[bool] = Field(None, description="Updated encryption status")
    upload_status: Optional[DocumentStatus] = Field(None, description="Updated upload status")
    parsed_at: Optional[datetime] = Field(None, description="Timestamp when the document was parsed")
    retention_until: Optional[datetime] = Field(None, description="Updated retention date")
    metadata: Optional[dict] = Field(None, description="Updated metadata for the document")

    @field_validator("file_size_bytes")
    @classmethod
    def validate_file_size(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("file_size_bytes must be positive")
        return v

    model_config = ConfigDict(extra="forbid")


class ClauseCreate(ClauseBase):
    """Schema for creating a new clause."""

    project_id: UUID = Field(..., description="ID of the project, used for linking and context")


class ClauseUpdate(BaseModel):
    """Schema for updating an existing clause."""

    clause_code: Optional[str] = Field(None, description="New code for the clause")
    clause_type: Optional[ClauseType] = Field(None, description="New type for the clause")
    title: Optional[str] = Field(None, description="New title for the clause")
    full_text: Optional[str] = Field(None, description="Updated full text of the clause")
    extracted_entities: Optional[dict] = Field(None, description="Updated extracted entities")
    extraction_confidence: Optional[float] = Field(
        None, description="Updated extraction confidence score"
    )
    manually_verified: Optional[bool] = Field(None, description="Updated verification status")

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------


class DocumentResponse(DocumentBase):
    """Schema for a document response, including its status and storage info."""

    id: UUID = Field(..., description="Unique ID of the document")
    project_id: UUID = Field(..., description="ID of the project this document belongs to")
    storage_url: str = Field(..., description="URL where the document is stored")
    storage_encrypted: bool = Field(..., description="Whether the document is encrypted in storage")
    upload_status: DocumentStatus = Field(
        ..., description="Current status of the document upload and parsing"
    )
    parsed_at: Optional[datetime] = Field(
        None, description="Timestamp when the document was last parsed"
    )
    parsing_error: Optional[str] = Field(None, description="Error message if parsing failed")
    retention_until: Optional[datetime] = Field(None, description="Date until document should be retained")
    created_by: Optional[UUID] = Field(None, description="ID of the user who created the document")
    created_at: datetime = Field(..., description="Timestamp of creation")
    updated_at: datetime = Field(..., description="Timestamp of last update")
    metadata: dict = Field(
        default_factory=dict,
        description="Arbitrary metadata for the document",
        alias="document_metadata",
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ClauseResponse(ClauseBase):
    """Schema for a clause response, including its unique ID and project context."""

    clause_id: UUID = Field(..., description="Unique ID of the clause", alias="id")
    project_id: UUID = Field(..., description="ID of the project this clause belongs to")
    created_at: datetime = Field(..., description="Timestamp of creation")
    updated_at: datetime = Field(..., description="Timestamp of last update")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DocumentDetailResponse(DocumentResponse):
    """A detailed document response that includes all its associated clauses."""

    clauses: list[ClauseResponse] = Field(
        default_factory=list, description="List of clauses extracted from the document"
    )


class UploadFileResponse(BaseModel):
    """Response schema after successfully initiating a file upload."""

    filename: str = Field(..., description="Name of the uploaded file")
    message: str = Field(..., description="Status message")
    document_id: UUID = Field(..., description="ID of the created document record")


class DocumentUploadResponse(BaseModel):
    """Response schema for document parsing completion."""

    document_id: UUID = Field(..., description="ID of the document record")
    status: DocumentStatus = Field(..., description="Parsing status for the document")
    message: str = Field(..., description="Status message")

class DocumentQueuedResponse(DocumentResponse):
    """
    Response schema for a document that has been successfully queued for processing.
    Includes the task_id for polling or tracking the background job.
    """
    task_id: str | None = Field(None, description="The ID of the background task processing this document.")


class RagQuestionRequest(BaseModel):
    """Request schema for querying documents via RAG."""

    question: str = Field(..., min_length=3, description="Question to ask about the project documents")
    top_k: Optional[int] = Field(5, ge=1, le=10, description="Number of chunks to retrieve")


class RagAnswerSource(BaseModel):
    """Source snippet used to answer a RAG question."""

    content: str
    metadata: dict = Field(default_factory=dict)
    similarity: float


class RagAnswerResponse(BaseModel):
    """Response schema for a RAG answer with sources."""

    answer: str
    sources: list[RagAnswerSource] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Polling Schemas
# ---------------------------------------------------------------------------


class DocumentPollingStatus(str, Enum):
    """
    Enum for simplified document processing statuses for frontend polling.
    """

    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    PARSED = "PARSED"
    ERROR = "ERROR"


class DocumentListItem(BaseModel):
    """
    Schema for a single document item in a project's document list.
    Designed for efficient polling.
    """

    id: UUID = Field(..., description="Unique ID of the document")
    filename: str = Field(..., description="Original filename of the document")
    status: DocumentPollingStatus = Field(
        ..., description="Current processing status of the document"
    )
    error_message: Optional[str] = Field(
        None, description="Error message if document processing failed"
    )
    uploaded_at: datetime = Field(..., description="Timestamp when the document was uploaded")
    file_size_bytes: int = Field(..., description="Size of the file in bytes")

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    """
    Schema for the response when listing documents for a project,
    containing a list of DocumentListItem.
    """

    items: list[DocumentListItem] = Field(..., description="List of documents")
    total_count: int = Field(..., description="Total number of documents matching the criteria")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum number of items returned")
