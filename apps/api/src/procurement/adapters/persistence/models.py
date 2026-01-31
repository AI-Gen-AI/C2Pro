"""
SQLAlchemy ORM models for the Procurement bounded context.
These models represent the database schema for procurement-related entities.
"""

from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import (
    Column,
    String,
    Integer,
    DECIMAL,
    DateTime,
    ForeignKey,
    Enum,
    Boolean,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from apps.api.src.procurement.domain.models import (
    BOMCategory,
    ProcurementStatus,
    WBSItemType,
)

Base = declarative_base()


class BudgetItemORM(Base):
    """SQLAlchemy model for BudgetItem domain entity."""

    __tablename__ = "procurement_budget_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    code = Column(String, nullable=False, unique=True)
    amount = Column(DECIMAL(10, 2), nullable=False)

    def __repr__(self):
        return f"<BudgetItemORM(id={self.id}, name='{self.name}', amount={self.amount})>"


class WBSItemORM(Base):
    """SQLAlchemy model for WBSItem domain entity."""

    __tablename__ = "procurement_wbs_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    level = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    parent_code = Column(String, ForeignKey("procurement_wbs_items.code"), nullable=True)
    item_type = Column(Enum(WBSItemType), nullable=True)
    budget_allocated = Column(DECIMAL(10, 2), nullable=True)
    budget_spent = Column(DECIMAL(10, 2), default=Decimal(0), nullable=False)
    planned_start = Column(DateTime(timezone=True), nullable=True)
    planned_end = Column(DateTime(timezone=True), nullable=True)
    actual_start = Column(DateTime(timezone=True), nullable=True)
    actual_end = Column(DateTime(timezone=True), nullable=True)
    source_clause_id = Column(UUID(as_uuid=True), nullable=True)
    wbs_metadata = Column(JSONB, default={}, nullable=False)

    # Relationships
    # Parent relationship (many-to-one)
    parent = relationship(
        "WBSItemORM",
        remote_side=[code], # 'code' of the parent WBSItemORM
        back_populates="children",
        uselist=False # A child has only one parent
    )

    # Children relationship (one-to-many)
    children = relationship(
        "WBSItemORM",
        back_populates="parent",
        cascade="all, delete-orphan", # Cascade operations to children
        foreign_keys=[parent_code] # Specify the foreign key on the local side
    )

    def __repr__(self):
        return f"<WBSItemORM(id={self.id}, code='{self.code}', name='{self.name}')>"


class BOMItemORM(Base):
    """SQLAlchemy model for BOMItem domain entity."""

    __tablename__ = "procurement_bom_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False)
    item_name = Column(String, nullable=False)
    quantity = Column(DECIMAL(10, 2), nullable=False)
    wbs_item_id = Column(UUID(as_uuid=True), ForeignKey("procurement_wbs_items.id"), nullable=True)
    item_code = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    category = Column(Enum(BOMCategory), nullable=True)
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
        Enum(ProcurementStatus), default=ProcurementStatus.PENDING, nullable=False
    )
    bom_metadata = Column(JSONB, default={}, nullable=False)

    # Relationships
    wbs_item = relationship("WBSItemORM", backref="bom_items")
    budget_item = relationship("BudgetItemORM", backref="bom_items")

    def __repr__(self):
        return f"<BOMItemORM(id={self.id}, item_name='{self.item_name}', quantity={self.quantity})>"
