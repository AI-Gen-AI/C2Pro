"""
C2Pro - Document & Clause Schemas

Pydantic schemas for document and clause validation and serialization.
"""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

# ===========================================
# DOCUMENT SCHEMAS
# ===========================================

class DocumentBase(BaseModel):
    document_type: str = Field(..., description="Type of the document, e.g., 'contract', 'schedule', 'budget'")
    file_name: str = Field(..., description="Original name of the file")
    mime_type: str | None = Field(None, description="MIME type of the file")
    file_size_bytes: int | None = Field(None, description="Size of the file in bytes")

class DocumentCreate(DocumentBase):
    project_id: UUID

class DocumentUpdate(BaseModel):
    upload_status: str | None = None

class DocumentResponse(DocumentBase):
    id: UUID
    project_id: UUID
    storage_path: str
    upload_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ===========================================
# CLAUSE SCHEMAS
# ===========================================

class ClauseBase(BaseModel):
    clause_number: str | None = Field(None, description="Clause number, e.g., '14.2.a'")
    text: str = Field(..., description="The full text of the clause")
    topic: str | None = Field(None, description="Main topic of the clause, e.g., 'Penalties'")

class ClauseCreate(ClauseBase):
    document_id: UUID

class ClauseUpdate(ClauseBase):
    pass

class ClauseResponse(ClauseBase):
    id: UUID
    document_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ===========================================
# DOCUMENT EXTRACTION SCHEMAS
# ===========================================

class DocumentExtractionBase(BaseModel):
    model_version: str | None = Field(None, description="Version of the AI model used for extraction")
    extraction_type: str = Field(..., description="Type of extraction, e.g., 'clauses', 'dates'")
    data: dict | list = Field(..., description="The extracted data in JSON format")
    tokens_used: int | None = Field(None, description="Number of tokens used for the extraction")
    confidence_score: float | None = Field(None, description="Confidence score of the extraction")

class DocumentExtractionCreate(DocumentExtractionBase):
    document_id: UUID

class DocumentExtractionResponse(DocumentExtractionBase):
    id: UUID
    document_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
