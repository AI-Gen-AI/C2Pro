"""
Domain models for the Document bounded context.
A Document is an Aggregate Root for Clauses.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID

# Canonical status for a document's lifecycle.
class DocumentStatus(str, Enum):
    """Represents the status of a document during its lifecycle."""
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PARSING = "parsing"
    PARSED = "parsed"
    ERROR = "error"

class DocumentType(str, Enum):
    """Supported document types."""
    CONTRACT = "contract"
    SCHEDULE = "schedule"
    BUDGET = "budget"
    DRAWING = "drawing"
    SPECIFICATION = "specification"
    OTHER = "other"

class ClauseType(str, Enum):
    """Types of contractual clauses."""
    PENALTY = "penalty"
    MILESTONE = "milestone"
    RESPONSIBILITY = "responsibility"
    PAYMENT = "payment"
    DELIVERY = "delivery"
    QUALITY = "quality"
    SCOPE = "scope"
    TERMINATION = "termination"
    DISPUTE = "dispute"
    OTHER = "other"


@dataclass
class Clause:
    """
    Represents a contractual Clause as a pure domain entity.
    It lives within the Document aggregate.
    """
    id: UUID
    project_id: UUID
    document_id: UUID
    clause_code: str
    clause_type: ClauseType | None
    title: str | None
    full_text: str | None
    text_start_offset: int | None = None
    text_end_offset: int | None = None
    extracted_entities: dict = field(default_factory=dict)
    extraction_confidence: float | None = None
    extraction_model: str | None = None
    manually_verified: bool = False
    verified_at: datetime | None = None

    def is_verified(self) -> bool:
        """Business rule: Checks if the clause was manually verified."""
        return self.manually_verified and self.verified_at is not None

    def needs_verification(self) -> bool:
        """Business rule: Checks if the clause requires manual verification based on its type."""
        critical_types = {ClauseType.PENALTY, ClauseType.TERMINATION, ClauseType.PAYMENT}
        return not self.is_verified() and self.clause_type in critical_types


@dataclass
class Document:
    """
    Represents a Document as a pure domain entity and Aggregate Root.
    """
    id: UUID
    project_id: UUID
    document_type: DocumentType
    filename: str
    file_format: str | None = None
    storage_url: str | None = None
    storage_encrypted: bool = True
    file_size_bytes: int | None = None
    upload_status: DocumentStatus
    parsed_at: datetime | None = None
    parsing_error: str | None = None
    retention_until: datetime | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    document_metadata: dict = field(default_factory=dict)
    clauses: list[Clause] = field(default_factory=list)

    def is_parsed(self) -> bool:
        """Business rule: Checks if the document was successfully parsed."""
        return self.upload_status == DocumentStatus.PARSED

    def has_error(self) -> bool:
        """Business rule: Checks if there was an error during parsing."""
        return self.upload_status == DocumentStatus.ERROR

    def clause_count(self) -> int:
        """Returns the number of clauses extracted from the document."""
        return len(self.clauses)

    def add_clause(self, clause: Clause):
        """Method to add a clause, maintaining aggregate integrity."""
        if clause.document_id != self.id:
            raise ValueError("Clause does not belong to this document.")
        self.clauses.append(clause)
