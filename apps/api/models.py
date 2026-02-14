"""
Domain models for the Documents module.
"""
import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentStatus(str, enum.Enum):
    """Status of a document in the processing pipeline."""

    UPLOADED = "UPLOADED"
    PARSING = "PARSING"
    PARSED = "PARSED"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class DocumentType(str, enum.Enum):
    """Type of the document."""

    CONTRACT = "CONTRACT"
    BLUEPRINT = "BLUEPRINT"
    BUDGET = "BUDGET"
    SCHEDULE = "SCHEDULE"
    OTHER = "OTHER"


class Document(BaseModel):
    """Domain model for a document."""

    id: UUID
    project_id: UUID
    tenant_id: UUID
    filename: str
    storage_path: str
    document_type: DocumentType
    status: DocumentStatus
    file_size_bytes: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)