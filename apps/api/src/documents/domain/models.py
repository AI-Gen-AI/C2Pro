"""
Domain models for the Document bounded context.
A Document is an Aggregate Root for Clauses.
Refers to Suite ID: TS-UD-DOC-CLS-002.
Refers to Suite ID: TS-UD-DOC-DOC-001.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID

from src.core.json_types import JsonDict


# Canonical status for a document's lifecycle.
class DocumentStatus(str, Enum):
    """Represents the status of a document during its lifecycle."""
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PARSING = "processing"  # Database uses "processing"
    PARSED = "parsed"
    PARSED_PENDING_ANALYSIS = "parsed_pending_analysis"  # TASK-BCK-022: Ingestion complete, analysis not yet started
    ANALYZED = "analyzed"  # TASK-BCK-022: Analysis orchestration completed
    ERROR = "error"

class DocumentType(str, Enum):
    """Supported document types."""
    CONTRACT = "contract"
    SCHEDULE = "schedule"
    BUDGET = "budget"
    DRAWING = "drawing"
    SPECIFICATION = "specification"
    TECHNICAL_SPEC = "technical_spec"
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
    WARRANTY = "warranty"
    TERMINATION = "termination"
    DISPUTE = "dispute"
    OTHER = "other"
    GENERAL = "other"


# Alias for ClauseCategory - used in tests and other parts of the codebase
ClauseCategory = ClauseType


@dataclass
class Clause:
    """
    Represents a contractual Clause as a pure domain entity.
    It lives within the Document aggregate.
    """
    id: UUID
    project_id: UUID
    tenant_id: UUID
    document_id: UUID
    clause_code: str
    clause_type: ClauseType | None
    title: str | None
    full_text: str | None
    text_start_offset: int | None = None
    text_end_offset: int | None = None
    extracted_entities: JsonDict = field(default_factory=dict)
    extraction_confidence: float | None = None
    extraction_model: str | None = None
    manually_verified: bool = False
    verified_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.project_id is None:
            raise ValueError("project_id is required")
        if self.tenant_id is None:
            raise ValueError("tenant_id is required")

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
    retention_until: datetime | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    document_metadata: JsonDict = field(default_factory=dict)
    clauses: list[Clause] = field(default_factory=list)
    # TASK-BCK-023: Document versioning
    version: int = 1
    file_hash: str | None = None

    def __post_init__(self) -> None:
        if self.project_id is None:
            raise ValueError("project_id is required")
        if self.tenant_id is None:
            raise ValueError("tenant_id is required")

    def is_parsed(self) -> bool:
        """Business rule: Checks if the document was successfully parsed."""
        return self.upload_status in {
            DocumentStatus.PARSED,
            DocumentStatus.PARSED_PENDING_ANALYSIS,
            DocumentStatus.ANALYZED,
        }

    def has_error(self) -> bool:
        """Business rule: Checks if there was an error during parsing."""
        return self.upload_status == DocumentStatus.ERROR

    def clause_count(self) -> int:
        """Returns the number of clauses extracted from the document."""
        return len(self.clauses)

    def add_clause(self, clause: Clause) -> None:
        """Method to add a clause, maintaining aggregate integrity."""
        if clause.document_id != self.id:
            raise ValueError("Clause does not belong to this document.")
        self.clauses.append(clause)

    def transition_to(self, new_status: DocumentStatus) -> Document:
        """Refers to Suite ID: TS-UD-DOC-DOC-001."""
        allowed: dict[DocumentStatus, set[DocumentStatus]] = {
            DocumentStatus.UPLOADED: {DocumentStatus.QUEUED, DocumentStatus.ERROR},
            DocumentStatus.QUEUED: {DocumentStatus.PARSING, DocumentStatus.ERROR},
            DocumentStatus.PARSING: {DocumentStatus.PARSED, DocumentStatus.ERROR},
            DocumentStatus.PARSED: {DocumentStatus.ERROR},
            DocumentStatus.ERROR: set(),
        }

        if new_status == self.upload_status:
            return self

        if new_status not in allowed.get(self.upload_status, set()):
            raise ValueError("Invalid status transition")

        return Document(
            id=self.id,
            project_id=self.project_id,
            tenant_id=self.tenant_id,
            document_type=self.document_type,
            filename=self.filename,
            upload_status=new_status,
            file_format=self.file_format,
            storage_url=self.storage_url,
            storage_encrypted=self.storage_encrypted,
            file_size_bytes=self.file_size_bytes,
            parsed_at=self.parsed_at,
            parsing_error=self.parsing_error,
            retention_until=self.retention_until,
            created_by=self.created_by,
            created_at=self.created_at,
            updated_at=self.updated_at,
            document_metadata=dict(self.document_metadata),
            clauses=list(self.clauses),
        )


@dataclass(frozen=True)
class DocumentAlertHistoryEntry:
    """TS-UA-DOC-HIST-001: Normalized alert history entry for document evidence timelines."""

    action: str
    detail: str
    occurred_at: datetime


@dataclass(frozen=True)
class DocumentEvidenceAlert:
    """TS-UA-DOC-HIST-001: Alert projection used to build a document history timeline."""

    id: UUID
    title: str
    created_at: datetime
    history: list[DocumentAlertHistoryEntry] = field(default_factory=list)


@dataclass(frozen=True)
class DocumentHistorySnapshot:
    """TS-UA-DOC-HIST-001: Document timeline projection read from persistence."""

    document: Document
    clause_count: int
    alerts: list[DocumentEvidenceAlert] = field(default_factory=list)


@dataclass(frozen=True)
class DocumentAlertSignal:
    """TS-UA-DOC-REL-001: Alert projection used for relationship explanation orchestration."""

    id: UUID
    title: str
    severity: str
    status: str
    created_at: datetime
    updated_at: datetime | None = None
    source_clause_id: UUID | None = None
