"""
C2Pro - Analysis Models

Modelos SQLAlchemy para análisis de coherencia y alertas.
Incluye trazabilidad legal mediante FKs a clauses (ROADMAP §5.3).

Refers to Suite ID: TS-INT-DB-CLS-001.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    ARRAY,
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

from src.analysis.domain.enums import AnalysisStatus, AnalysisType, AlertSeverity, AlertStatus
from src.core.database import Base
from src.core.approval import ApprovalStatus

if TYPE_CHECKING:
    from src.core.auth.models import User


 


class Analysis(Base):
    """
    Modelo de Análisis.

    Representa un análisis de coherencia ejecutado sobre un proyecto.
    Genera alertas que pueden referenciar cláusulas específicas.
    """

    __tablename__ = "analyses"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Project relationship
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Analysis type
    analysis_type: Mapped[AnalysisType] = mapped_column(
        SQLEnum(AnalysisType, values_callable=lambda obj: [e.value for e in obj]),
        default=AnalysisType.COHERENCE,
    )

    # Status
    status: Mapped[AnalysisStatus] = mapped_column(
        SQLEnum(AnalysisStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=AnalysisStatus.PENDING,
    )

    # Results
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Coherence Score (ROADMAP §12)
    coherence_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        # CHECK constraint definido en migración: BETWEEN 0 AND 100
    )
    coherence_breakdown: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,  # Detalle por regla
    )

    # Alerts count
    alerts_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    alerts: Mapped[list["Alert"]] = relationship(
        "Alert", back_populates="analysis", lazy="select", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_analyses_project", "project_id"),
        Index("ix_analyses_status", "status"),
        Index("ix_analyses_created", "created_at"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )

    def __repr__(self) -> str:
        return (
            f"<Analysis(id={self.id}, type={self.analysis_type.value}, status={self.status.value})>"
        )

    @property
    def is_completed(self) -> bool:
        """Verifica si el análisis completó."""
        return self.status == AnalysisStatus.COMPLETED

    @property
    def has_error(self) -> bool:
        """Verifica si hubo error."""
        return self.status == AnalysisStatus.ERROR

    @property
    def duration_seconds(self) -> int | None:
        """Duración del análisis en segundos."""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None

    @property
    def critical_alerts(self) -> int:
        """Número de alertas críticas."""
        return sum(1 for a in self.alerts if a.severity == AlertSeverity.CRITICAL)


class Alert(Base):
    """
    Modelo de Alerta.

    CRÍTICO: Incluye FK a clause (source_clause_id) para trazabilidad legal.
    Cada alerta puede rastrear su origen a una cláusula contractual específica.
    """

    __tablename__ = "alerts"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Relationships
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Classification
    severity: Mapped[AlertSeverity] = mapped_column(
        SQLEnum(AlertSeverity, values_callable=lambda obj: [e.value for e in obj]), nullable=False
    )
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rule_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,  # Referencia a regla de coherencia (ej: "R1", "R5")
    )

    # Content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)

    # TRAZABILIDAD LEGAL (ROADMAP §5.3)
    source_clause_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("clauses.id"),
        nullable=True,
        index=True,  # FK a cláusula que origina la alerta
    )

    # Related clause IDs (array of UUIDs)
    related_clause_ids: Mapped[list[UUID] | None] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)), nullable=True
    )

    # Affected entities (stored as JSONB)
    affected_entities: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,  # {"documents": [], "wbs": [], "bom": []}
    )

    # Impact level
    impact_level: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Metadata (includes evidence and other data)
    alert_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Status
    status: Mapped[AlertStatus] = mapped_column(
        SQLEnum(AlertStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=AlertStatus.OPEN,
    )

    # Approval workflow
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        SQLEnum(ApprovalStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=ApprovalStatus.PENDING,
        index=True,
        nullable=False,
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Resolution
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    analysis: Mapped["Analysis"] = relationship(
        "Analysis", back_populates="alerts", lazy="selectin"
    )

    resolver: Mapped["User"] = relationship("User", foreign_keys=[resolved_by], lazy="select")
    reviewer: Mapped["User"] = relationship("User", foreign_keys=[reviewed_by], lazy="select")

    # Indexes
    __table_args__ = (
        Index("ix_alerts_project", "project_id"),
        Index("ix_alerts_analysis", "analysis_id"),
        Index("ix_alerts_severity", "severity"),
        Index("ix_alerts_status", "status"),
        Index("ix_alerts_clause", "source_clause_id"),  # Para trazabilidad
        Index("ix_alerts_created", "created_at"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )

    def __repr__(self) -> str:
        return (
            f"<Alert(id={self.id}, severity={self.severity.value}, title='{self.title[:30]}...')>"
        )

    @property
    def is_open(self) -> bool:
        """Verifica si está abierta."""
        return self.status == AlertStatus.OPEN

    @property
    def is_resolved(self) -> bool:
        """Verifica si fue resuelta."""
        return self.status == AlertStatus.RESOLVED

    @property
    def is_critical(self) -> bool:
        """Verifica si es crítica."""
        return self.severity == AlertSeverity.CRITICAL

    @property
    def has_clause_reference(self) -> bool:
        """Verifica si tiene referencia a cláusula (trazabilidad)."""
        return self.source_clause_id is not None

    @property
    def clause_code(self) -> str | None:
        """Código de la cláusula fuente (si existe)."""
        return None

    @property
    def age_days(self) -> int:
        """Días desde que se creó la alerta."""
        return (datetime.utcnow() - self.created_at).days

    @property
    def is_stale(self) -> bool:
        """Verifica si es una alerta antigua sin resolver (>30 días)."""
        return self.is_open and self.age_days > 30

    def mark_resolved(self, user_id: UUID, notes: str | None = None) -> None:
        """Marca la alerta como resuelta."""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.utcnow()
        self.resolved_by = user_id
        self.resolution_notes = notes

    def mark_acknowledged(self) -> None:
        """Marca la alerta como reconocida."""
        self.status = AlertStatus.ACKNOWLEDGED

    def mark_dismissed(self, user_id: UUID, notes: str) -> None:
        """
        Marca la alerta como descartada.

        IMPORTANTE: Requiere notas (anti-gaming, ROADMAP §12).
        """
        if not notes:
            raise ValueError("Dismissing alert requires resolution_notes (anti-gaming)")

        self.status = AlertStatus.DISMISSED
        self.resolved_at = datetime.utcnow()
        self.resolved_by = user_id
        self.resolution_notes = notes


class Extraction(Base):
    """
    Modelo de Extracción.

    Almacena datos extraídos de documentos mediante IA.
    Separado de Document para permitir múltiples extracciones por documento.
    """

    __tablename__ = "extractions"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Document relationship
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Extraction metadata
    extraction_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,  # contract_metadata, milestones, budget_items
    )

    # Data
    data_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # AI tracking (ROADMAP §6.2)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    document: Mapped["DocumentORM"] = relationship(
        "DocumentORM", foreign_keys=[document_id], lazy="selectin"
    )

    # Indexes
    __table_args__ = (
        Index("ix_extractions_document", "document_id"),
        Index("ix_extractions_type", "extraction_type"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )

    def __repr__(self) -> str:
        return f"<Extraction(id={self.id}, type={self.extraction_type})>"

    @property
    def confidence_level(self) -> str:
        """Nivel de confianza de la extracción."""
        if self.confidence_score is None:
            return "unknown"
        elif self.confidence_score >= 0.9:
            return "high"
        elif self.confidence_score >= 0.7:
            return "medium"
        else:
            return "low"
