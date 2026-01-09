"""
C2Pro - Document & Clause Models

Modelos SQLAlchemy para documentos y cláusulas.
La tabla clauses es CRÍTICA para trazabilidad legal (ROADMAP §5.3).
"""

from datetime import datetime
from enum import Enum
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

if TYPE_CHECKING:
    from src.modules.analysis.models import Alert
    from src.modules.auth.models import User
    from src.modules.projects.models import Project
    from src.modules.stakeholders.models import Stakeholder


class DocumentType(str, Enum):
    """Tipos de documento soportados."""

    CONTRACT = "contract"
    SCHEDULE = "schedule"
    BUDGET = "budget"
    DRAWING = "drawing"
    SPECIFICATION = "specification"
    OTHER = "other"


class DocumentStatus(str, Enum):
    """Estados de procesamiento de documento."""

    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    ERROR = "error"


class ClauseType(str, Enum):
    """Tipos de cláusula contractual."""

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


class Document(Base):
    """
    Modelo de Documento.

    Almacena documentos del proyecto (contrato, cronograma, presupuesto).
    Los archivos se guardan en Cloudflare R2 cifrados.
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
        nullable=True,  # pdf, xlsx, bc3, p6, mpp
    )

    # Storage (ROADMAP §6.1: cifrado obligatorio)
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

    # Retention (ROADMAP §6.1)
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
    project: Mapped["Project"] = relationship(
        "Project", back_populates="documents", lazy="selectin"
    )

    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by], lazy="select")

    clauses: Mapped[list["Clause"]] = relationship(
        "Clause", back_populates="document", lazy="select", cascade="all, delete-orphan"
    )

    extracted_stakeholders: Mapped[list["Stakeholder"]] = relationship(
        "Stakeholder",
        back_populates="extracted_from_document",
        foreign_keys="Stakeholder.extracted_from_document_id",
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
            f"<Document(id={self.id}, type={self.document_type.value}, filename='{self.filename}')>"
        )

    @property
    def is_parsed(self) -> bool:
        """Verifica si el documento fue parseado."""
        return self.upload_status == DocumentStatus.PARSED

    @property
    def has_error(self) -> bool:
        """Verifica si hubo error en parsing."""
        return self.upload_status == DocumentStatus.ERROR

    @property
    def clause_count(self) -> int:
        """Número de cláusulas extraídas."""
        return len(self.clauses)


class Clause(Base):
    """
    Modelo de Cláusula Contractual.

    CRÍTICO: Esta es la entidad central para trazabilidad legal (ROADMAP §5.3).
    Permite rastrear desde cláusulas del contrato hasta WBS, BOM, stakeholders, alertas.
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

    # Identificación
    clause_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,  # "4.2.1", "Anexo III.2"
    )
    clause_type: Mapped[ClauseType | None] = mapped_column(
        SQLEnum(ClauseType), nullable=True, index=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Contenido
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Extracción de IA
    extracted_entities: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,  # stakeholders, dates, amounts encontrados
    )
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    extraction_model: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Auditoría y verificación humana (ROADMAP §2.2: Human-in-the-loop)
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
    project: Mapped["Project"] = relationship("Project", foreign_keys=[project_id], lazy="selectin")

    document: Mapped["Document"] = relationship(
        "Document", back_populates="clauses", lazy="selectin"
    )

    verifier: Mapped["User"] = relationship("User", foreign_keys=[verified_by], lazy="select")

    # Relaciones inversas (qué referencia a esta cláusula)
    # Estas se definen en los otros modelos con back_populates
    alerts: Mapped[list["Alert"]] = relationship(
        "Alert",
        back_populates="source_clause",
        foreign_keys="Alert.source_clause_id",
        lazy="select",
    )

    stakeholders: Mapped[list["Stakeholder"]] = relationship(
        "Stakeholder",
        back_populates="source_clause",
        foreign_keys="Stakeholder.source_clause_id",
        lazy="select",
    )

    wbs_items: Mapped[list["WBSItem"]] = relationship(
        "WBSItem",
        back_populates="funded_by_clause",
        foreign_keys="WBSItem.funded_by_clause_id",
        lazy="select",
    )

    bom_items: Mapped[list["BOMItem"]] = relationship(
        "BOMItem",
        back_populates="contract_clause",
        foreign_keys="BOMItem.contract_clause_id",
        lazy="select",
    )

    # Constraints e Indexes
    __table_args__ = (
        Index("ix_clauses_project", "project_id"),
        Index("ix_clauses_document", "document_id"),
        Index("ix_clauses_type", "clause_type"),
        Index("ix_clauses_code", "clause_code"),
        Index("ix_clauses_verified", "manually_verified", "verified_at"),
        # Constraint único: solo una cláusula con mismo código por documento
        {
            "info": {"rls_policy": "tenant_isolation"},
        },
    )

    def __repr__(self) -> str:
        return f"<Clause(id={self.id}, code='{self.clause_code}', type={self.clause_type})>"

    @property
    def is_verified(self) -> bool:
        """Verifica si fue verificada manualmente."""
        return self.manually_verified and self.verified_at is not None

    @property
    def needs_verification(self) -> bool:
        """Verifica si necesita verificación manual."""
        # Tipos críticos que requieren verificación
        critical_types = {ClauseType.PENALTY, ClauseType.TERMINATION, ClauseType.PAYMENT}
        return not self.is_verified and self.clause_type in critical_types

    @property
    def confidence_level(self) -> str:
        """Nivel de confianza de la extracción."""
        if self.extraction_confidence is None:
            return "unknown"
        elif self.extraction_confidence >= 0.9:
            return "high"
        elif self.extraction_confidence >= 0.7:
            return "medium"
        else:
            return "low"

    @property
    def has_references(self) -> bool:
        """Verifica si tiene entidades que la referencian."""
        return (
            len(self.alerts) > 0
            or len(self.stakeholders) > 0
            or len(self.wbs_items) > 0
            or len(self.bom_items) > 0
        )
