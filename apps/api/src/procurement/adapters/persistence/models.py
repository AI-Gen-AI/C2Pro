"""
SQLAlchemy ORM models for the Procurement bounded context.
These models represent the database schema for procurement-related entities.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    DECIMAL,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.procurement.domain.models import (
    BOMCategory,
    ProcurementStatus,
    WBSItemType,
)

__all__ = ["BOMCategory", "ProcurementStatus", "WBSItemType"]

from typing import Any


class BudgetItemORM(Base):
    """SQLAlchemy model for BudgetItem domain entity."""

    __tablename__ = "procurement_budget_items"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(18, 2), nullable=False)

    project: Mapped[Any] = relationship("ProjectORM", backref="budget_items")

    def __repr__(self) -> str:
        return f"<BudgetItemORM(id={self.id}, name='{self.name}', amount={self.amount})>"


class WBSItemORM(Base):
    """SQLAlchemy model for WBSItem domain entity."""

    __tablename__ = "procurement_wbs_items"
    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_procurement_wbs_project_code"),
        ForeignKeyConstraint(
            ["project_id", "parent_code"],
            ["procurement_wbs_items.project_id", "procurement_wbs_items.code"],
            name="fk_wbs_parent_per_project",
            ondelete="CASCADE",
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_code: Mapped[str | None] = mapped_column(String, nullable=True)
    item_type: Mapped[WBSItemType | None] = mapped_column(
        Enum(WBSItemType, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    budget_allocated: Mapped[Decimal | None] = mapped_column(DECIMAL(18, 2), nullable=True)
    budget_spent: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 2), default=Decimal(0), nullable=False
    )
    planned_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_clause_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    source_document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    wbs_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default={}, nullable=False)
    __mapper_args__ = {"version_id_col": version}

    # Relationships
    parent: Mapped[Any] = relationship(
        "WBSItemORM",
        remote_side=[project_id, code],
        back_populates="children",
        uselist=False,
        foreign_keys=[project_id, parent_code],
    )
    children: Mapped[list["WBSItemORM"]] = relationship(
        "WBSItemORM",
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys=[project_id, parent_code],
        uselist=True,
    )

    def __repr__(self) -> str:
        return f"<WBSItemORM(id={self.id}, code='{self.code}', name='{self.name}')>"


class BOMItemORM(Base):
    """SQLAlchemy model for BOMItem domain entity."""

    __tablename__ = "procurement_bom_items"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    item_name: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)
    wbs_item_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("procurement_wbs_items.id"), nullable=True
    )
    item_code: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[BOMCategory | None] = mapped_column(
        Enum(BOMCategory, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(DECIMAL(18, 2), nullable=True)
    total_price: Mapped[Decimal | None] = mapped_column(DECIMAL(18, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String, default="EUR", nullable=False)
    supplier: Mapped[str | None] = mapped_column(String, nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    production_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transit_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    incoterm: Mapped[str | None] = mapped_column(String, nullable=True)
    contract_clause_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    source_document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True
    )
    budget_item_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("procurement_budget_items.id"), nullable=True
    )
    procurement_status: Mapped[ProcurementStatus] = mapped_column(
        Enum(ProcurementStatus, values_callable=lambda x: [e.value for e in x]),
        default=ProcurementStatus.PENDING,
        nullable=False,
    )
    bom_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default={}, nullable=False)

    # Relationships
    wbs_item: Mapped[Any] = relationship("WBSItemORM", backref="bom_items")
    budget_item: Mapped[Any] = relationship("BudgetItemORM", backref="bom_items")
    source_document: Mapped[Any] = relationship("DocumentORM", backref="bom_items")

    def __repr__(self) -> str:
        return f"<BOMItemORM(id={self.id}, item_name='{self.item_name}', quantity={self.quantity})>"


class StakeholderAlertORM(Base):
    """SQLAlchemy model for stakeholder alerts.

    Links stakeholders to alerts for notification tracking.
    """

    __tablename__ = "stakeholder_alerts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    stakeholder_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("stakeholders.id", ondelete="CASCADE"), nullable=False
    )
    alert_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False
    )
    notification_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notification_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    acknowledged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )

    __table_args__ = (
        Index("idx_stakeholder_alerts_stakeholder", "stakeholder_id"),
        Index("idx_stakeholder_alerts_alert", "alert_id"),
    )

    def __repr__(self) -> str:
        return f"<StakeholderAlertORM(id={self.id}, stakeholder_id={self.stakeholder_id}, alert_id={self.alert_id})>"


class BOMRevisionORM(Base):
    """SQLAlchemy model for BOM item revision history.

    Tracks changes to BOM items over time.
    """

    __tablename__ = "bom_revisions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    bom_item_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("procurement_bom_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    changes_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    changed_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )

    __table_args__ = (
        UniqueConstraint("bom_item_id", "revision_number", name="bom_revisions_item_number_unique"),
        Index("idx_bom_revisions_item", "bom_item_id"),
        Index("idx_bom_revisions_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<BOMRevisionORM(id={self.id}, bom_item_id={self.bom_item_id}, revision_number={self.revision_number})>"


class ProcurementPlanSnapshotORM(Base):
    """SQLAlchemy model for procurement plan snapshots.

    Stores point-in-time snapshots of procurement plans.
    """

    __tablename__ = "procurement_plan_snapshots"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_name: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )

    __table_args__ = (
        Index("idx_procurement_snapshots_project", "project_id"),
        Index("idx_procurement_snapshots_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ProcurementPlanSnapshotORM(id={self.id}, snapshot_name='{self.snapshot_name}')>"
