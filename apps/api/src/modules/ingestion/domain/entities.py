"""
C2Pro - Ingestion Domain Entities

Defines the canonical data contract for document chunks and ingestion errors.

Increment I1: Canonical Ingestion Contract
- IngestionChunk: Core DTO with provenance metadata (doc_id, version_id, page, bbox, source_hash, confidence)
- IngestionError: Typed exception for ingestion failures

Increment I2: OCR + Table Parsing Reliability
- TableData: DTO for extracted table data with structure preservation
"""

from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from typing import Optional


class IngestionChunk(BaseModel):
    """
    Canonical data contract for a processed document chunk.

    Refers to I1.1: Contract test - each chunk must include:
    - doc_id: Unique document identifier
    - version_id: Unique document version identifier
    - page: Page number (1-indexed)
    - content: Extracted text content
    - bbox: Bounding box [x1, y1, x2, y2] normalized to 0-1
    - source_hash: Hash of the raw content section
    - confidence: OCR/extraction confidence score (0.0-1.0)
    - metadata: Optional arbitrary metadata (e.g., needs_review flag)

    This DTO ensures all necessary provenance metadata is captured
    for downstream analysis, human-in-the-loop routing, and audit trails.
    """

    doc_id: UUID = Field(
        ...,
        description="Unique identifier for the document."
    )

    version_id: UUID = Field(
        ...,
        description="Unique identifier for the document version."
    )

    page: int = Field(
        ...,
        ge=1,
        description="Page number of the chunk (1-indexed)."
    )

    content: str = Field(
        ...,
        min_length=1,
        description="Extracted text content of the chunk."
    )

    bbox: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Bounding box [x1, y1, x2, y2] of the chunk on the page, normalized 0-1."
    )

    source_hash: str = Field(
        ...,
        min_length=1,
        description="Hash of the raw content section this chunk originated from."
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0) of the chunk's extraction/OCR accuracy."
    )

    metadata: dict = Field(
        default_factory=dict,
        description="Additional arbitrary metadata for the chunk (e.g., needs_review flag for HITL routing)."
    )

    @field_validator("bbox")
    @classmethod
    def validate_bbox_values(cls, v: list[float]) -> list[float]:
        """Validate that bbox coordinates are normalized between 0 and 1."""
        for coord in v:
            if not (0.0 <= coord <= 1.0):
                raise ValueError(f"BBox coordinate {coord} must be between 0.0 and 1.0 (normalized)")
        return v

    model_config = {
        "frozen": False,  # Allow mutation for metadata updates
        "str_strip_whitespace": True,
        "validate_assignment": True,
    }


class IngestionError(Exception):
    """
    Custom exception for errors occurring during document ingestion.

    Refers to I1.3: Malformed document returns typed ingestion error.

    This typed exception allows the system to:
    - Distinguish ingestion failures from other errors
    - Capture document context (doc_id, version_id)
    - Route failures to manual preprocessing queues
    - Log structured error data for observability

    Attributes:
        message: Human-readable error description
        doc_id: Optional document identifier for context
        version_id: Optional version identifier for context
    """

    def __init__(
        self,
        message: str,
        doc_id: Optional[UUID] = None,
        version_id: Optional[UUID] = None
    ):
        self.message = message
        self.doc_id = doc_id
        self.version_id = version_id
        super().__init__(self.message)

    def __str__(self) -> str:
        """String representation with context."""
        parts = [self.message]
        if self.doc_id:
            parts.append(f"doc_id={self.doc_id}")
        if self.version_id:
            parts.append(f"version_id={self.version_id}")
        return " | ".join(parts)

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"IngestionError(message={self.message!r}, "
            f"doc_id={self.doc_id!r}, version_id={self.version_id!r})"
        )


class TableData(BaseModel):
    """
    DTO for extracted table data.

    Refers to I2.2: Table extraction preserves row/column counts on fixture tables.

    This DTO ensures that table structure (rows, columns, merged cells) is
    correctly preserved during extraction. Critical for:
    - Financial data accuracy (budget tables, payment schedules)
    - Contractual obligations (deliverables, milestones)
    - Technical specifications (BOMs, material lists)

    Attributes:
        rows: List of rows, where each row is a list of cell strings
        confidence: Overall confidence score for the table extraction (0.0-1.0)
        bbox: Optional bounding box [x1, y1, x2, y2] normalized to 0-1
        metadata: Arbitrary metadata (e.g., needs_human_review for low confidence)
    """

    rows: list[list[str]] = Field(
        ...,
        description="List of rows, where each row is a list of cell strings."
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0) of the table extraction."
    )

    bbox: Optional[list[float]] = Field(
        None,
        min_length=4,
        max_length=4,
        description="Bounding box [x1, y1, x2, y2] of the table on the page, normalized 0-1."
    )

    metadata: dict = Field(
        default_factory=dict,
        description="Additional arbitrary metadata for the table (e.g., needs_human_review flag)."
    )

    @field_validator("bbox")
    @classmethod
    def validate_bbox_if_present(cls, v: Optional[list[float]]) -> Optional[list[float]]:
        """Validate that bbox coordinates are normalized between 0 and 1 if provided."""
        if v is not None:
            for coord in v:
                if not (0.0 <= coord <= 1.0):
                    raise ValueError(f"BBox coordinate {coord} must be between 0.0 and 1.0 (normalized)")
        return v

    @field_validator("rows")
    @classmethod
    def validate_row_consistency(cls, v: list[list[str]]) -> list[list[str]]:
        """Validate that all rows have the same number of columns (consistent table structure)."""
        if not v:
            raise ValueError("Table must have at least one row")

        # Check column count consistency
        column_count = len(v[0])
        if column_count == 0:
            raise ValueError("Table rows must have at least one column")

        for i, row in enumerate(v):
            if len(row) != column_count:
                raise ValueError(
                    f"Row {i} has {len(row)} columns, expected {column_count}. "
                    f"All rows must have the same column count."
                )

        return v

    model_config = {
        "frozen": False,
        "str_strip_whitespace": True,
        "validate_assignment": True,
    }
