"""
C2Pro - Document & Clause Models (SQLAlchemy ORM)

SQLAlchemy models for documents and clauses, used by the persistence adapter.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

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
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

# TYPE_CHECKING imports need to be adjusted for the new module structure
if TYPE_CHECKING:
    # Assuming these modules will also have their persistence models
    from src.analysis.adapters.persistence.models import Alert
    from src.core.auth.models import User, Tenant
    from src.projects.adapters.persistence.models import ProjectORM
    from src.stakeholders.adapters.persistence.models import StakeholderORM
    from src.procurement.adapters.persistence.models import BOMItemORM, WBSItemORM


# These enums are defined in domain layer, but ORM needs an Enum as SQLEnum
# So we import them from our domain models
from src.documents.domain.models import DocumentStatus, DocumentType, ClauseType


class DocumentORM(Base): # Renamed to DocumentORM to distinguish from domain entity
    """
    SQLAlchemy model for Document.
    """

    __tablename__ = "documents"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Project relationship
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Classification
    document_type: Mapped[DocumentType] = mapped_column(
        SQLEnum(DocumentType, values_callable=lambda obj: [e.value for e in obj]),
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
        SQLEnum(DocumentStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=DocumentStatus.UPLOADED,
        index=True,
    )
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    parsing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Retention
    retention_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Document Metadata (custom data)
    document_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Audit
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    project: Mapped["ProjectORM"] = relationship(
        "ProjectORM", back_populates="documents", lazy="selectin"
    )

    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by], lazy="select")

    clauses: Mapped[list["ClauseORM"]] = relationship(
        "ClauseORM", back_populates="document", lazy="select", cascade="all, delete-orphan"
    )

    extracted_stakeholders: Mapped[list["StakeholderORM"]] = relationship(
        "StakeholderORM",
        back_populates="extracted_from_document",
        foreign_keys="StakeholderORM.extracted_from_document_id",
        lazy="select",
    )

    # Indexes
    __table_args__ = (
        Index("ix_documents_project", "project_id"),
        Index("ix_documents_type", "document_type"),
        Index("ix_documents_status", "upload_status"),
        Index("ix_documents_created", "created_at"),
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
        SQLEnum(ClauseType), nullable=True, index=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Content
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # AI Extraction
    extracted_entities: Mapped[dict] = mapped_column(
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    project: Mapped["ProjectORM"] = relationship("ProjectORM", foreign_keys=[project_id], lazy="selectin")

    document: Mapped["DocumentORM"] = relationship(
        "DocumentORM", back_populates="clauses", lazy="selectin"
    )

    verifier: Mapped["User"] = relationship("User", foreign_keys=[verified_by], lazy="select")

    alerts: Mapped[list["Alert"]] = relationship(
        "Alert",
        back_populates="source_clause",
        foreign_keys="Alert.source_clause_id",
        lazy="select",
    )

    stakeholders: Mapped[list["StakeholderORM"]] = relationship(
        "StakeholderORM",
        back_populates="source_clause",
        foreign_keys="StakeholderORM.source_clause_id",
        lazy="select",
    )

    wbs_items: Mapped[list["WBSItemORM"]] = relationship(
        "WBSItemORM",
        back_populates="funded_by_clause",
        foreign_keys="WBSItemORM.funded_by_clause_id",
        lazy="select",
    )

    bom_items: Mapped[list["BOMItemORM"]] = relationship(
        "BOMItemORM",
        back_populates="contract_clause",
        foreign_keys="BOMItemORM.contract_clause_id",
        lazy="select",
    )

    # Constraints and Indexes
    __table_args__ = (
        Index("ix_clauses_project", "project_id"),
        Index("ix_clauses_document", "document_id"),
        Index("ix_clauses_type", "clause_type"),
        Index("ix_clauses_code", "clause_code"),
        Index("ix_clauses_verified", "manually_verified", "verified_at"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )

    def __repr__(self) -> str:
        return f"<ClauseORM(id={self.id}, code='{self.clause_code}', type={self.clause_type})>"
