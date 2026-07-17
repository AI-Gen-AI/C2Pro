"""
C2Pro - WBS Persistence Models

SQLAlchemy ORM models for WBS (Work Breakdown Structure) with nested set model.

Refers to Suite ID: TS-INT-DB-WBS-001.
TASK-BCK-029: WBS API Endpoint with nested set model
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.wbs.domain.enums import WBSNodeStatus, WBSNodeType

if TYPE_CHECKING:
    from src.projects.adapters.persistence.models import ProjectORM


class WBSNodeORM(Base):
    """
    WBS Node ORM model using Nested Set Model.

    Nested Set Model provides efficient tree operations:
    - All descendants: WHERE lft > node.lft AND rgt < node.rgt
    - All ancestors: WHERE lft < node.lft AND rgt > node.rgt
    - Leaf nodes: WHERE rgt = lft + 1
    - Subtree size: (rgt - lft - 1) / 2

    RLS Policy: wbs_nodes_tenant_isolation (filter by tenant_id)
    """

    __tablename__ = "wbs_nodes"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign keys
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("wbs_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Node identity
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Nested Set Model fields
    lft: Mapped[int] = mapped_column(Integer, nullable=False)
    rgt: Mapped[int] = mapped_column(Integer, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Node classification
    node_type: Mapped[WBSNodeType] = mapped_column(
        SQLEnum(WBSNodeType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        server_default="work_package",
    )
    status: Mapped[WBSNodeStatus] = mapped_column(
        SQLEnum(WBSNodeStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        server_default="not_started",
    )

    # Scheduling
    planned_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Budget
    budget_allocated: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    budget_spent: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")

    # Metadata
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )

    # Timestamps
    @staticmethod
    def _utcnow_naive() -> datetime:
        """Return UTC now normalized to a naive timestamp for legacy TIMESTAMP columns."""
        return datetime.now(UTC).replace(tzinfo=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False
    )

    # Relationships
    project: Mapped["ProjectORM"] = relationship(
        "ProjectORM", foreign_keys=[project_id], lazy="select"
    )
    parent: Mapped["WBSNodeORM"] = relationship(
        "WBSNodeORM",
        remote_side=[id],
        foreign_keys=[parent_id],
        lazy="select",
    )

    # Indexes and constraints
    __table_args__ = (
        Index("ix_wbs_nodes_project_id", "project_id"),
        Index("ix_wbs_nodes_tenant_id", "tenant_id"),
        Index("ix_wbs_nodes_parent_id", "parent_id"),
        Index("ix_wbs_nodes_lft", "lft"),
        Index("ix_wbs_nodes_rgt", "rgt"),
        Index("ix_wbs_nodes_depth", "depth"),
        Index("ix_wbs_nodes_status", "status"),
        Index("ix_wbs_nodes_node_type", "node_type"),
        Index(
            "ix_wbs_nodes_project_lft_rgt", "project_id", "lft", "rgt"
        ),  # Composite for tree queries
        UniqueConstraint("project_id", "code", name="uq_wbs_nodes_project_code"),
        CheckConstraint("lft < rgt", name="ck_wbs_nodes_lft_lt_rgt"),
        CheckConstraint("lft > 0", name="ck_wbs_nodes_lft_positive"),
        CheckConstraint("depth >= 0", name="ck_wbs_nodes_depth_non_negative"),
        CheckConstraint("budget_spent >= 0", name="ck_wbs_nodes_budget_spent_non_negative"),
        {"info": {"rls_policy": "wbs_nodes_tenant_isolation"}},
    )

    def __repr__(self) -> str:
        return f"<WBSNodeORM(id={self.id}, code='{self.code}', name='{self.name}')>"

    @property
    def is_root(self) -> bool:
        """Check if this is a root node."""
        return self.parent_id is None and self.depth == 0

    @property
    def is_leaf(self) -> bool:
        """Check if this is a leaf node (no children)."""
        return self.rgt == self.lft + 1

    @property
    def children_count_estimate(self) -> int:
        """Estimate number of nodes in subtree."""
        return (self.rgt - self.lft - 1) // 2
