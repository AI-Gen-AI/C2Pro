"""TS-E2E-SEC-TNT-001

C2Pro - Document, Clause & Chunk Models (SQLAlchemy ORM)

SQLAlchemy models for documents, clauses, and document chunks, used by the persistence adapter.
TASK-IMPL-006: Added DocumentChunkORM model for Gate 4 traceability.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.core.json_types import JsonDict

# TYPE_CHECKING imports need to be adjusted for the new module structure
if TYPE_CHECKING:
    from src.core.auth.models import User
    from src.core.dlq.models import DLQFailedTask


# These enums are defined in domain layer, but ORM needs an Enum as SQLEnum
# So we import them from our domain models
# Import for SQLAlchemy mapper registration of DocumentORM <-> DLQFailedTask relationship.
from src.core.dlq.models import DLQFailedTask
from src.documents.domain.models import ClauseType, DocumentStatus, DocumentType


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class DocumentORM(Base): # Renamed to DocumentORM to distinguish from domain entity
    """
    SQLAlchemy model for Document.
    """

    __tablename__ = "documents"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Tenant relationship
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Project relationship
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Classification
    document_type: Mapped[DocumentType] = mapped_column(
        SQLEnum(DocumentType, name="document_type", create_type=False, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_format: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    # Storage
    storage_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_encrypted: Mapped[bool] = mapped_column(Boolean, default=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Processing
    upload_status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus, name="document_status", create_type=False, values_callable=lambda obj: [e.value for e in obj]),
        default=DocumentStatus.UPLOADED,
        index=True,
    )
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    parsing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Versioning (TASK-BCK-023)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Retention
    retention_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Document Metadata (custom data)
    document_metadata: Mapped[JsonDict] = mapped_column(JSONB, default=dict)

    # Audit
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now_naive, onupdate=_utc_now_naive, nullable=False
    )

    # Relationships
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by], lazy="select")

    clauses: Mapped[list["ClauseORM"]] = relationship(
        "ClauseORM", back_populates="document", lazy="select", cascade="all, delete-orphan"
    )

    # TASK-BCK-022: DLQ relationship for failed analysis triggers
    dlq_tasks: Mapped[list["DLQFailedTask"]] = relationship(
        "DLQFailedTask", back_populates="document", lazy="select"
    )

    # Indexes
    __table_args__ = (
        Index("ix_documents_project", "project_id"),
        Index("ix_documents_tenant", "tenant_id"),
        Index("ix_documents_type", "document_type"),
        Index("ix_documents_status", "upload_status"),
        Index("ix_documents_created", "created_at"),
        Index("ix_documents_file_hash", "file_hash"),  # TASK-BCK-023
        Index("ix_documents_id_version", "id", "version"),  # TASK-BCK-023
        {"info": {"rls_policy": "tenant_isolation"}},
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentORM(id={self.id}, type={self.document_type.value}, filename='{self.filename}')>"
        )


class ClauseORM(Base): # Renamed to ClauseORM to distinguish from domain entity
    """
    SQLAlchemy model for Clause.
    """

    __tablename__ = "clauses"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Tenant relationship
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Relationships
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Lane C / C3a: the immutable revision this clause was extracted from. NULL only
    # for legacy rows whose revision could not be proven (never fabricated).
    revision_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    # Identification
    clause_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    clause_type: Mapped[ClauseType | None] = mapped_column(
        SQLEnum(
            ClauseType,
            name="clausetype",
            create_type=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Content
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # AI Extraction
    extracted_entities: Mapped[JsonDict] = mapped_column(
        JSONB,
        default=dict,
    )
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    extraction_model: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Audit and human verification
    manually_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now_naive, onupdate=_utc_now_naive, nullable=False
    )

    # Relationships
    document: Mapped["DocumentORM"] = relationship(
        "DocumentORM", back_populates="clauses", lazy="selectin"
    )

    verifier: Mapped["User"] = relationship("User", foreign_keys=[verified_by], lazy="select")



    # Constraints and Indexes
    __table_args__ = (
        Index("ix_clauses_project", "project_id"),
        Index("ix_clauses_document", "document_id"),
        Index("ix_clauses_tenant", "tenant_id"),
        Index("ix_clauses_type", "clause_type"),
        Index("ix_clauses_code", "clause_code"),
        Index("ix_clauses_verified", "manually_verified", "verified_at"),
        Index("ix_clauses_tenant_document_revision", "tenant_id", "document_id", "revision_id"),
        # A clause can only be bound to a revision of its own document in its own tenant.
        ForeignKeyConstraint(
            ["revision_id", "document_id", "tenant_id"],
            [
                "document_revisions.revision_id",
                "document_revisions.document_id",
                "document_revisions.tenant_id",
            ],
            name="fk_clauses_revision_identity",
        ),
        {"info": {"rls_policy": "tenant_isolation"}},
    )

    def __repr__(self) -> str:
        return f"<ClauseORM(id={self.id}, code='{self.clause_code}', type={self.clause_type})>"


class DocumentChunkORM(Base):
    """
    SQLAlchemy model for DocumentChunk.

    Stores document chunks for RAG (Retrieval Augmented Generation).
    TASK-IMPL-006: Created ORM model for Gate 4 traceability.
    """

    __tablename__ = "document_chunks"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # Tenant relationship
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    chunk_metadata: Mapped[JsonDict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Indexes
    __table_args__ = (
        Index("ix_document_chunks_project", "project_id"),
        Index("ix_document_chunks_document", "document_id"),
        Index("ix_document_chunks_tenant", "tenant_id"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )

    def __repr__(self) -> str:
        return f"<DocumentChunkORM(id={self.id}, document_id={self.document_id})>"



class DocumentProcessingOperationORM(Base):
    """#711: the single processing authority for one document.

    One row per document. It names the canonical revision and processing
    generation being worked on, the current stage (INGESTION -> ANALYSIS), and
    the exact attempt that owns it: attempt_id + owner_token + a monotonic
    fencing_token under a PostgreSQL-clock lease. Every canonical durable
    write re-verifies this row inside its own transaction (see
    ``src.core.processing_authority``); a worker whose attempt was superseded can keep
    computing but can never persist.
    """

    __tablename__ = "document_processing_operations"

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    revision_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    generation: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="1")
    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    phase: Mapped[str] = mapped_column(String(16), nullable=False)
    attempt_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    owner_token: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    fencing_token: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "stage IN ('INGESTION','ANALYSIS')", name="ck_document_processing_operations_stage"
        ),
        CheckConstraint(
            "phase IN ('PENDING','CLAIMED','RUNNING','COMPLETED','FAILED')",
            name="ck_document_processing_operations_phase",
        ),
        CheckConstraint(
            "fencing_token >= 0", name="ck_document_processing_operations_fence"
        ),
        {"info": {"rls_policy": "tenant_isolation"}},
    )


# Lane C / C3a: ClauseORM's composite revision FK targets ``document_revisions``.
# Register that table wherever the clause model is mapped, so mapper configuration
# never depends on some other module having imported the temporal models first.
from src.temporal.adapters.persistence import models as _temporal_models  # noqa: E402, F401
