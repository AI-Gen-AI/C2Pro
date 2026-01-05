"""
C2Pro - Stakeholder, WBS & BOM Models

Modelos SQLAlchemy para Stakeholder Intelligence y gestión de WBS/BOM.
TODOS incluyen FKs a clauses para trazabilidad legal (ROADMAP §4.5, §5.3).
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from decimal import Decimal

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.modules.projects.models import Project
    from src.modules.documents.models import Clause, Document
    from src.modules.auth.models import User
    from src.modules.analysis.models import Alert


class PowerLevel(str, Enum):
    """Nivel de poder del stakeholder."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InterestLevel(str, Enum):
    """Nivel de interés del stakeholder."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StakeholderQuadrant(str, Enum):
    """Cuadrante poder/interés (ROADMAP §4.5)."""
    KEY_PLAYER = "key_player"           # high/high
    KEEP_SATISFIED = "keep_satisfied"   # high/low
    KEEP_INFORMED = "keep_informed"     # low/high
    MONITOR = "monitor"                 # low/low


class RACIRole(str, Enum):
    """Roles RACI."""
    RESPONSIBLE = "R"   # Ejecuta
    ACCOUNTABLE = "A"   # Responsable final
    CONSULTED = "C"     # Consultado
    INFORMED = "I"      # Informado


class WBSItemType(str, Enum):
    """Tipos de item WBS."""
    DELIVERABLE = "deliverable"
    WORK_PACKAGE = "work_package"
    ACTIVITY = "activity"


class BOMCategory(str, Enum):
    """Categorías de items BOM."""
    MATERIAL = "material"
    EQUIPMENT = "equipment"
    SERVICE = "service"
    CONSUMABLE = "consumable"


class ProcurementStatus(str, Enum):
    """Estados de procurement."""
    PENDING = "pending"
    REQUESTED = "requested"
    ORDERED = "ordered"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Stakeholder(Base):
    """
    Modelo de Stakeholder.

    IMPORTANTE: Incluye FK a clause (source_clause_id) para trazabilidad legal.
    Permite rastrear desde qué cláusula se extrajo el stakeholder.
    """

    __tablename__ = "stakeholders"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    # Project relationship
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Identificación
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Clasificación (ROADMAP §4.5)
    power_level: Mapped[PowerLevel] = mapped_column(
        SQLEnum(PowerLevel),
        default=PowerLevel.MEDIUM
    )
    interest_level: Mapped[InterestLevel] = mapped_column(
        SQLEnum(InterestLevel),
        default=InterestLevel.MEDIUM
    )
    quadrant: Mapped[StakeholderQuadrant | None] = mapped_column(
        SQLEnum(StakeholderQuadrant),
        nullable=True,
        index=True
    )

    # Contacto
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # TRAZABILIDAD LEGAL (ROADMAP §4.5)
    source_clause_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("clauses.id"),
        nullable=True,
        index=True  # FK a cláusula que menciona al stakeholder
    )

    # Extracción
    extraction_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    extracted_from_document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id"),
        nullable=True
    )

    # Metadata
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        foreign_keys=[project_id],
        lazy="selectin"
    )

    source_clause: Mapped["Clause"] = relationship(
        "Clause",
        back_populates="stakeholders",
        foreign_keys=[source_clause_id],
        lazy="selectin"  # Cargar para trazabilidad
    )

    extracted_from_document: Mapped["Document"] = relationship(
        "Document",
        foreign_keys=[extracted_from_document_id],
        lazy="select"
    )

    # RACI assignments
    raci_assignments: Mapped[list["StakeholderWBSRaci"]] = relationship(
        "StakeholderWBSRaci",
        back_populates="stakeholder",
        lazy="select",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_stakeholders_project", "project_id"),
        Index("ix_stakeholders_quadrant", "quadrant"),
        Index("ix_stakeholders_clause", "source_clause_id"),
        Index("ix_stakeholders_email", "email"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )

    def __repr__(self) -> str:
        return f"<Stakeholder(id={self.id}, name='{self.name}', quadrant={self.quadrant})>"

    @property
    def full_title(self) -> str:
        """Título completo del stakeholder."""
        parts = []
        if self.name:
            parts.append(self.name)
        if self.role:
            parts.append(f"({self.role})")
        if self.organization:
            parts.append(f"- {self.organization}")
        return " ".join(parts) if parts else "Unknown Stakeholder"

    @property
    def is_key_player(self) -> bool:
        """Verifica si es key player (high power + high interest)."""
        return self.quadrant == StakeholderQuadrant.KEY_PLAYER

    @property
    def has_clause_reference(self) -> bool:
        """Verifica si tiene referencia a cláusula."""
        return self.source_clause_id is not None


class WBSItem(Base):
    """
    Modelo de WBS Item (Work Breakdown Structure).

    IMPORTANTE: Incluye FK a clause (funded_by_clause_id) para trazabilidad.
    Permite rastrear qué cláusula contractual financia cada item WBS.
    """

    __tablename__ = "wbs_items"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    # Project relationship
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Jerarquía
    parent_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("wbs_items.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # Identificación
    wbs_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True  # "1.2.3.4"
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)  # Nivel en jerarquía

    # Clasificación
    item_type: Mapped[WBSItemType | None] = mapped_column(
        SQLEnum(WBSItemType),
        nullable=True
    )

    # Financial
    budget_allocated: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    budget_spent: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    # Schedule
    planned_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    planned_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # TRAZABILIDAD LEGAL (ROADMAP §4.2)
    funded_by_clause_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("clauses.id"),
        nullable=True,
        index=True  # Cláusula que financia este WBS
    )

    # Metadata
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        foreign_keys=[project_id],
        lazy="selectin"
    )

    parent: Mapped["WBSItem"] = relationship(
        "WBSItem",
        remote_side=[id],
        foreign_keys=[parent_id],
        lazy="select"
    )

    children: Mapped[list["WBSItem"]] = relationship(
        "WBSItem",
        back_populates="parent",
        lazy="select",
        cascade="all, delete-orphan"
    )

    funded_by_clause: Mapped["Clause"] = relationship(
        "Clause",
        foreign_keys=[funded_by_clause_id],
        lazy="selectin"  # Cargar para trazabilidad
    )

    # RACI assignments
    raci_assignments: Mapped[list["StakeholderWBSRaci"]] = relationship(
        "StakeholderWBSRaci",
        back_populates="wbs_item",
        lazy="select",
        cascade="all, delete-orphan"
    )

    # BOM items
    bom_items: Mapped[list["BOMItem"]] = relationship(
        "BOMItem",
        back_populates="wbs_item",
        lazy="select",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_wbs_items_project", "project_id"),
        Index("ix_wbs_items_parent", "parent_id"),
        Index("ix_wbs_items_code", "wbs_code"),
        Index("ix_wbs_items_clause", "funded_by_clause_id"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )

    def __repr__(self) -> str:
        return f"<WBSItem(id={self.id}, code='{self.wbs_code}', name='{self.name}')>"

    @property
    def has_clause_reference(self) -> bool:
        """Verifica si tiene referencia a cláusula."""
        return self.funded_by_clause_id is not None

    @property
    def budget_variance(self) -> Decimal:
        """Variación presupuestaria."""
        if self.budget_allocated:
            return self.budget_spent - self.budget_allocated
        return Decimal(0)

    @property
    def is_over_budget(self) -> bool:
        """Verifica si excedió presupuesto."""
        return self.budget_variance > 0


class BOMItem(Base):
    """
    Modelo de BOM Item (Bill of Materials).

    IMPORTANTE: Incluye FK a clause (contract_clause_id) para trazabilidad.
    Permite rastrear qué cláusula contractual define/requiere cada material.
    """

    __tablename__ = "bom_items"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    # Relationships
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    wbs_item_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("wbs_items.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # Identificación
    item_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[BOMCategory | None] = mapped_column(
        SQLEnum(BOMCategory),
        nullable=True,
        index=True
    )

    # Quantity
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)  # kg, m3, m2, units

    # Pricing
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    # Procurement
    supplier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    incoterm: Mapped[str | None] = mapped_column(String(20), nullable=True)  # EXW, FOB, CIF

    # TRAZABILIDAD LEGAL (ROADMAP §4.2)
    contract_clause_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("clauses.id"),
        nullable=True,
        index=True  # Cláusula contractual que define/requiere este material
    )

    # Status
    procurement_status: Mapped[ProcurementStatus] = mapped_column(
        SQLEnum(ProcurementStatus),
        default=ProcurementStatus.PENDING,
        index=True
    )

    # Metadata
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        foreign_keys=[project_id],
        lazy="selectin"
    )

    wbs_item: Mapped["WBSItem"] = relationship(
        "WBSItem",
        back_populates="bom_items",
        lazy="selectin"
    )

    contract_clause: Mapped["Clause"] = relationship(
        "Clause",
        foreign_keys=[contract_clause_id],
        lazy="selectin"  # Cargar para trazabilidad
    )

    # Indexes
    __table_args__ = (
        Index("ix_bom_items_project", "project_id"),
        Index("ix_bom_items_wbs", "wbs_item_id"),
        Index("ix_bom_items_category", "category"),
        Index("ix_bom_items_clause", "contract_clause_id"),
        Index("ix_bom_items_status", "procurement_status"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )

    def __repr__(self) -> str:
        return f"<BOMItem(id={self.id}, name='{self.item_name}', qty={self.quantity})>"

    @property
    def has_clause_reference(self) -> bool:
        """Verifica si tiene referencia a cláusula."""
        return self.contract_clause_id is not None

    @property
    def is_ordered(self) -> bool:
        """Verifica si fue ordenado."""
        return self.procurement_status in {
            ProcurementStatus.ORDERED,
            ProcurementStatus.IN_TRANSIT,
            ProcurementStatus.DELIVERED
        }


class StakeholderWBSRaci(Base):
    """
    Modelo de Matriz RACI.

    Relaciona stakeholders con WBS items mediante roles RACI.
    """

    __tablename__ = "stakeholder_wbs_raci"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    # Relationships
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    stakeholder_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stakeholders.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    wbs_item_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("wbs_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # RACI Role
    raci_role: Mapped[RACIRole] = mapped_column(
        SQLEnum(RACIRole),
        nullable=False,
        index=True
    )

    # Metadata
    generated_automatically: Mapped[bool] = mapped_column(Boolean, default=True)
    manually_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        foreign_keys=[project_id],
        lazy="selectin"
    )

    stakeholder: Mapped["Stakeholder"] = relationship(
        "Stakeholder",
        back_populates="raci_assignments",
        lazy="selectin"
    )

    wbs_item: Mapped["WBSItem"] = relationship(
        "WBSItem",
        back_populates="raci_assignments",
        lazy="selectin"
    )

    verifier: Mapped["User"] = relationship(
        "User",
        foreign_keys=[verified_by],
        lazy="select"
    )

    # Indexes
    __table_args__ = (
        Index("ix_raci_stakeholder", "stakeholder_id"),
        Index("ix_raci_wbs", "wbs_item_id"),
        Index("ix_raci_role", "raci_role"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )

    def __repr__(self) -> str:
        return f"<RACI(stakeholder={self.stakeholder_id}, wbs={self.wbs_item_id}, role={self.raci_role.value})>"

    @property
    def is_verified(self) -> bool:
        """Verifica si fue verificado manualmente."""
        return self.manually_verified and self.verified_at is not None
