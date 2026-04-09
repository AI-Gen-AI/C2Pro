"""
SQLAlchemy ORM models for the Procurement bounded context.
These models represent the database schema for procurement-related entities.
"""

import uuid
from decimal import Decimal

from sqlalchemy import (
    DECIMAL,
    Column,
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from src.core.database import Base
from src.procurement.domain.models import (
    BOMCategory,
    ProcurementStatus,
    WBSItemType,
)


class BudgetItemORM(Base):
    """SQLAlchemy model for BudgetItem domain entity."""

    __tablename__ = "procurement_budget_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    name = Column(String, nullable=False)
    code = Column(String, nullable=False, unique=True)
    amount = Column(DECIMAL(10, 2), nullable=False)

    project = relationship("ProjectORM", backref="budget_items")

    def __repr__(self):
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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    level = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    parent_code = Column(String, nullable=True)
    item_type = Column(
        Enum(WBSItemType, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    budget_allocated = Column(DECIMAL(10, 2), nullable=True)
    budget_spent = Column(DECIMAL(10, 2), default=Decimal(0), nullable=False)
    planned_start = Column(DateTime(timezone=True), nullable=True)
    planned_end = Column(DateTime(timezone=True), nullable=True)
    actual_start = Column(DateTime(timezone=True), nullable=True)
    actual_end = Column(DateTime(timezone=True), nullable=True)
    source_clause_id = Column(UUID(as_uuid=True), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    wbs_metadata = Column(JSONB, default={}, nullable=False)
    __mapper_args__ = {"version_id_col": version}

    # Relationships
    # Parent relationship (many-to-one)
    parent = relationship(
        "WBSItemORM",
        remote_side=[project_id, code],
        back_populates="children",
        uselist=False,
        foreign_keys=[project_id, parent_code],
    )

    # Children relationship (one-to-many)
    children = relationship(
        "WBSItemORM",
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys=[project_id, parent_code],
    )

    def __repr__(self):
        return f"<WBSItemORM(id={self.id}, code='{self.code}', name='{self.name}')>"


class BOMItemORM(Base):
    """SQLAlchemy model for BOMItem domain entity."""

    __tablename__ = "procurement_bom_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    item_name = Column(String, nullable=False)
    quantity = Column(DECIMAL(10, 2), nullable=False)
    wbs_item_id = Column(UUID(as_uuid=True), ForeignKey("procurement_wbs_items.id"), nullable=True)
    item_code = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    category = Column(
        Enum(BOMCategory, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    unit = Column(String, nullable=True)
    unit_price = Column(DECIMAL(10, 2), nullable=True)
    total_price = Column(DECIMAL(10, 2), nullable=True)
    currency = Column(String, default="EUR", nullable=False)
    supplier = Column(String, nullable=True)
    lead_time_days = Column(Integer, nullable=True)
    production_time_days = Column(Integer, nullable=True)
    transit_time_days = Column(Integer, nullable=True)
    incoterm = Column(String, nullable=True)
    contract_clause_id = Column(UUID(as_uuid=True), nullable=True)
    budget_item_id = Column(UUID(as_uuid=True), ForeignKey("procurement_budget_items.id"), nullable=True)
    procurement_status = Column(
        Enum(ProcurementStatus, values_callable=lambda x: [e.value for e in x]),
        default=ProcurementStatus.PENDING,
        nullable=False,
    )
    bom_metadata = Column(JSONB, default={}, nullable=False)

    # Relationships
    wbs_item = relationship("WBSItemORM", backref="bom_items")
    budget_item = relationship("BudgetItemORM", backref="bom_items")

    def __repr__(self):
        return f"<BOMItemORM(id={self.id}, item_name='{self.item_name}', quantity={self.quantity})>"


class StakeholderAlertORM(Base):
    """SQLAlchemy model for stakeholder alerts.

    Links stakeholders to alerts for notification tracking.
    """

    __tablename__ = "stakeholder_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    stakeholder_id = Column(UUID(as_uuid=True), ForeignKey("stakeholders.id", ondelete="CASCADE"), nullable=False)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False)
    notification_sent = Column(Integer, default=0, nullable=False)
    notification_sent_at = Column(DateTime(timezone=True), nullable=True)
    notification_method = Column(String(50), nullable=True)
    acknowledged = Column(Integer, default=0, nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default="NOW()")

    __table_args__ = (
        Index("idx_stakeholder_alerts_stakeholder", "stakeholder_id"),
        Index("idx_stakeholder_alerts_alert", "alert_id"),
    )

    def __repr__(self):
        return f"<StakeholderAlertORM(id={self.id}, stakeholder_id={self.stakeholder_id}, alert_id={self.alert_id})>"


class BOMRevisionORM(Base):
    """SQLAlchemy model for BOM item revision history.

    Tracks changes to BOM items over time.
    """

    __tablename__ = "bom_revisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    bom_item_id = Column(UUID(as_uuid=True), ForeignKey("procurement_bom_items.id", ondelete="CASCADE"), nullable=False)
    revision_number = Column(Integer, nullable=False)
    changes_json = Column(JSONB, nullable=False)
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    change_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default="NOW()")

    __table_args__ = (
        UniqueConstraint("bom_item_id", "revision_number", name="bom_revisions_item_number_unique"),
        Index("idx_bom_revisions_item", "bom_item_id"),
        Index("idx_bom_revisions_created", "created_at"),
    )

    def __repr__(self):
        return f"<BOMRevisionORM(id={self.id}, bom_item_id={self.bom_item_id}, revision_number={self.revision_number})>"


class ProcurementPlanSnapshotORM(Base):
    """SQLAlchemy model for procurement plan snapshots.

    Stores point-in-time snapshots of procurement plans.
    """

    __tablename__ = "procurement_plan_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    snapshot_name = Column(String(255), nullable=False)
    snapshot_data = Column(JSONB, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default="NOW()")

    __table_args__ = (
        Index("idx_procurement_snapshots_project", "project_id"),
        Index("idx_procurement_snapshots_created", "created_at"),
    )

    def __repr__(self):
        return f"<ProcurementPlanSnapshotORM(id={self.id}, snapshot_name='{self.snapshot_name}')>"
