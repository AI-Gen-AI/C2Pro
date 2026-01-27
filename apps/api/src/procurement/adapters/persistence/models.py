"""
SQLAlchemy ORM models for Procurement bounded context, used by the persistence adapter.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum # Needed for the enums defined here
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
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

# Import enums from our domain models (these will be moved here later)
# For now, defining them here as they are part of the original models.py file
# They will be moved to procurement/domain/models.py in a later step.


class WBSItemType(str, Enum):
    """Types of WBS items."""
    DELIVERABLE = "deliverable"
    WORK_PACKAGE = "work_package"
    ACTIVITY = "activity"


class BOMCategory(str, Enum):
    """Categories of BOM items."""
    MATERIAL = "material"
    EQUIPMENT = "equipment"
    SERVICE = "service"
    CONSUMABLE = "consumable"


class ProcurementStatus(str, Enum):
    """Procurement statuses."""
    PENDING = "pending"
    REQUESTED = "requested"
    ORDERED = "ordered"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


# TYPE_CHECKING imports need to be adjusted for the new module structure
if TYPE_CHECKING:
    from src.projects.adapters.persistence.models import ProjectORM
    from src.documents.adapters.persistence.models import ClauseORM
    from src.stakeholders.adapters.persistence.models import StakeholderWBSRaciORM


class WBSItemORM(Base):
    """
    SQLAlchemy model for WBS Item.
    """

    __tablename__ = "wbs_items"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Project relationship
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Hierarchy
    parent_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("wbs_items.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Identification
    wbs_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)

    # Classification
    item_type: Mapped[WBSItemType | None] = mapped_column(SQLEnum(WBSItemType), nullable=True)

    # Financial
    budget_allocated: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    budget_spent: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    # Schedule
    planned_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    planned_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Traceability
    funded_by_clause_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("clauses.id"),
        nullable=True,
        index=True,
    )

    # WBS Metadata (custom data)
    wbs_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    project: Mapped["ProjectORM"] = relationship(
        "ProjectORM", back_populates="wbs_items", foreign_keys=[project_id], lazy="selectin"
    )

    parent: Mapped["WBSItemORM"] = relationship(
        "WBSItemORM",
        back_populates="children",
        remote_side=[id],
        foreign_keys=[parent_id],
        lazy="select",
    )

    children: Mapped[list["WBSItemORM"]] = relationship(
        "WBSItemORM", back_populates="parent", lazy="select", cascade="all, delete-orphan"
    )

    funded_by_clause: Mapped["ClauseORM"] = relationship(
        "ClauseORM",
        back_populates="wbs_items",
        foreign_keys=[funded_by_clause_id],
        lazy="selectin",
    )

    raci_assignments: Mapped[list["StakeholderWBSRaciORM"]] = relationship(
        "StakeholderWBSRaciORM", back_populates="wbs_item", lazy="select", cascade="all, delete-orphan"
    )

    bom_items: Mapped[list["BOMItemORM"]] = relationship(
        "BOMItemORM", back_populates="wbs_item", lazy="select", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_wbs_items_project", "project_id"),
        Index("ix_wbs_items_parent", "parent_id"),
        Index("ix_wbs_items_code", "wbs_code"),
        Index("ix_wbs_items_clause", "funded_by_clause_id"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )


class BOMItemORM(Base):
    """
    SQLAlchemy model for BOM Item.
    """

    __tablename__ = "bom_items"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Relationships
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    wbs_item_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("wbs_items.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Identification
    item_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[BOMCategory | None] = mapped_column(SQLEnum(BOMCategory), nullable=True)

    # Quantity
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Pricing
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    # Procurement
    supplier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    incoterm: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Traceability
    contract_clause_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("clauses.id"),
        nullable=True,
        index=True,
    )

    # Status
    procurement_status: Mapped[ProcurementStatus] = mapped_column(
        SQLEnum(ProcurementStatus), default=ProcurementStatus.PENDING, index=True
    )

    # BOM Metadata (custom data)
    bom_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    project: Mapped["ProjectORM"] = relationship(
        "ProjectORM", back_populates="bom_items", foreign_keys=[project_id], lazy="selectin"
    )

    wbs_item: Mapped["WBSItemORM"] = relationship(
        "WBSItemORM", back_populates="bom_items", lazy="selectin"
    )

    contract_clause: Mapped["ClauseORM"] = relationship(
        "ClauseORM",
        back_populates="bom_items",
        foreign_keys=[contract_clause_id],
        lazy="selectin",
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
