"""
Pydantic schemas for the Documents module.

This module defines the data transfer objects (DTOs) for documents and clauses,
used for API request validation and response serialization.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.modules.documents.models import ClauseType, DocumentStatus, DocumentType

# ---------------------------------------------------------------------------
# Base Schemas
# ---------------------------------------------------------------------------


class DocumentBase(BaseModel):
    """Base schema for document attributes."""

    project_id: UUID = Field(..., description="ID of the project this document belongs to")
    document_type: DocumentType = Field(
        ..., description="Type of the document (e.g., CONTRACT, SCHEDULE)"
    )
    filename: str = Field(..., description="Original filename of the document")
    file_format: str | None = Field(None, description="Format of the file (e.g., pdf, xlsx)")
    file_size_bytes: int | None = Field(None, description="Size of the file in bytes")
    metadata: dict = Field(default_factory=dict, description="Arbitrary metadata for the document")


class ClauseBase(BaseModel):
    """Base schema for clause attributes."""

    document_id: UUID = Field(..., description="ID of the document this clause belongs to")
    clause_code: str = Field(
        ..., description="Unique code or identifier for the clause within the document"
    )
    clause_type: ClauseType | None = Field(
        None, description="Type of the clause (e.g., PAYMENT, LIABILITY)"
    )
    title: str | None = Field(None, description="Title of the clause")
    full_text: str | None = Field(None, description="Full text of the clause")
    extracted_entities: dict = Field(
        default_factory=dict, description="Entities extracted from the clause text by AI"
    )
    extraction_confidence: float | None = Field(
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

    pass


class DocumentUpdate(BaseModel):
    """Schema for updating an existing document's metadata."""

    filename: str | None = Field(None, description="New filename for the document")
    document_type: DocumentType | None = Field(None, description="New type for the document")
    metadata: dict | None = Field(None, description="Updated metadata for the document")


class ClauseCreate(ClauseBase):
    """Schema for creating a new clause."""

    project_id: UUID = Field(..., description="ID of the project, used for linking and context")


class ClauseUpdate(BaseModel):
    """Schema for updating an existing clause."""

    clause_code: str | None = Field(None, description="New code for the clause")
    clause_type: ClauseType | None = Field(None, description="New type for the clause")
    title: str | None = Field(None, description="New title for the clause")
    full_text: str | None = Field(None, description="Updated full text of the clause")
    extracted_entities: dict | None = Field(None, description="Updated extracted entities")
    extraction_confidence: float | None = Field(
        None, description="Updated extraction confidence score"
    )
    manually_verified: bool | None = Field(None, description="Updated verification status")


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------


class DocumentResponse(DocumentBase):
    """Schema for a document response, including its status and storage info."""

    id: UUID = Field(..., description="Unique ID of the document")
    storage_url: str = Field(..., description="URL where the document is stored")
    upload_status: DocumentStatus = Field(
        ..., description="Current status of the document upload and parsing"
    )
    parsed_at: datetime | None = Field(
        None, description="Timestamp when the document was last parsed"
    )
    parsing_error: str | None = Field(None, description="Error message if parsing failed")
    created_at: datetime = Field(..., description="Timestamp of creation")
    updated_at: datetime = Field(..., description="Timestamp of last update")

    class Config:
        from_attributes = True


class ClauseResponse(ClauseBase):
    """Schema for a clause response, including its unique ID and project context."""

    clause_id: UUID = Field(..., description="Unique ID of the clause", alias="id")
    project_id: UUID = Field(..., description="ID of the project this clause belongs to")
    created_at: datetime = Field(..., description="Timestamp of creation")
    updated_at: datetime = Field(..., description="Timestamp of last update")

    class Config:
        from_attributes = True
        populate_by_name = True


class DocumentDetailResponse(DocumentResponse):
    """A detailed document response that includes all its associated clauses."""

    clauses: list[ClauseResponse] = Field(
        [], description="List of clauses extracted from the document"
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
