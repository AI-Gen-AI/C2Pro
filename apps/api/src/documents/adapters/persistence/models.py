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
    DateTime,
    Float,
    ForeignKey,
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
