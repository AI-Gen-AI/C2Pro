"""
C2Pro - Project Models

Modelos SQLAlchemy para proyectos y entidades relacionadas.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
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
    from src.modules.analysis.models import Alert, Analysis
    from src.modules.auth.models import Tenant
    from src.modules.documents.models import Document
    from src.modules.stakeholders.models import BOMItem, Stakeholder, WBSItem


class ProjectStatus(str, Enum):
    """Estados posibles de un proyecto."""

    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProjectType(str, Enum):
    """Tipos de proyecto."""

    CONSTRUCTION = "construction"
    ENGINEERING = "engineering"
    INDUSTRIAL = "industrial"
    INFRASTRUCTURE = "infrastructure"
    OTHER = "other"


class Project(Base):
    """
    Modelo principal de Proyecto.

    Un proyecto agrupa contrato, cronograma y presupuesto para análisis.
    """

    __tablename__ = "projects"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Tenant isolation (CRÍTICO para seguridad)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Código interno

    # Classification
    project_type: Mapped[ProjectType] = mapped_column(
        SQLEnum(ProjectType, values_callable=lambda obj: [e.value for e in obj]),
        default=ProjectType.CONSTRUCTION,
    )
    status: Mapped[ProjectStatus] = mapped_column(
        SQLEnum(ProjectStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=ProjectStatus.DRAFT,
    )

    # Financial
    estimated_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    # Dates
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Analysis results (cached)
    coherence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_analysis_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Project Metadata (custom data)
    project_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant", back_populates="projects", lazy="selectin", foreign_keys=[tenant_id]
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="project", lazy="selectin", cascade="all, delete-orphan"
    )

    analyses: Mapped[list["Analysis"]] = relationship(
        "Analysis", back_populates="project", lazy="selectin", cascade="all, delete-orphan"
    )

    alerts: Mapped[list["Alert"]] = relationship(
        "Alert", back_populates="project", lazy="selectin", cascade="all, delete-orphan"
    )

    # New relationships (v2.4.0)
    stakeholders: Mapped[list["Stakeholder"]] = relationship(
        "Stakeholder", back_populates="project", lazy="select", cascade="all, delete-orphan"
    )

    wbs_items: Mapped[list["WBSItem"]] = relationship(
        "WBSItem", back_populates="project", lazy="select", cascade="all, delete-orphan"
    )

    bom_items: Mapped[list["BOMItem"]] = relationship(
        "BOMItem", back_populates="project", lazy="select", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        # Index compuesto para queries por tenant
        Index("ix_projects_tenant_created", "tenant_id", "created_at"),
        Index("ix_projects_tenant_status", "tenant_id", "status"),
        # RLS policy info (para documentación)
        {"info": {"rls_policy": "tenant_isolation"}},
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name='{self.name}', tenant={self.tenant_id})>"

    @property
    def has_contract(self) -> bool:
        """Verifica si tiene contrato subido."""
        return any(d.document_type == "contract" for d in self.documents)

    @property
    def has_schedule(self) -> bool:
        """Verifica si tiene cronograma subido."""
        return any(d.document_type == "schedule" for d in self.documents)

    @property
    def has_budget(self) -> bool:
        """Verifica si tiene presupuesto subido."""
        return any(d.document_type == "budget" for d in self.documents)

    @property
    def is_ready_for_analysis(self) -> bool:
        """Verifica si tiene los documentos mínimos para análisis."""
        return self.has_contract  # Mínimo: contrato

    @property
    def document_count(self) -> int:
        """Número de documentos."""
        return len(self.documents)

    @property
    def alert_count(self) -> dict[str, int]:
        """Cuenta de alertas por severidad."""
        from src.modules.analysis.models import AlertSeverity

        counts = {s.value: 0 for s in AlertSeverity}
        for alert in self.alerts:
            if not alert.resolved_at:
                counts[alert.severity.value] += 1
        return counts
