"""
C2Pro - WBS Domain Models

Work Breakdown Structure domain models using Nested Set Model for efficient tree operations.

Nested Set Model fields:
- lft (left): Left boundary of the node's subtree
- rgt (right): Right boundary of the node's subtree
- depth: Level in the tree (root = 0)
- parent_id: Direct parent reference for convenience

Tree operations:
- All descendants: WHERE lft > node.lft AND rgt < node.rgt
- All ancestors: WHERE lft < node.lft AND rgt > node.rgt
- Leaf nodes: WHERE rgt = lft + 1
- Subtree size: (rgt - lft - 1) / 2
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.wbs.domain.enums import WBSNodeStatus, WBSNodeType


@dataclass(frozen=True)
class WBSNode:
    """
    WBS Node domain model using Nested Set Model.

    Immutable value object representing a node in the Work Breakdown Structure tree.
    """

    id: UUID
    project_id: UUID
    tenant_id: UUID

    # Node identity
    code: str  # e.g., "1.2.3" or "WBS-001"
    name: str
    description: str | None

    # Nested Set Model fields
    lft: int  # Left boundary
    rgt: int  # Right boundary
    depth: int  # Tree level (0 = root)
    parent_id: UUID | None  # Direct parent reference

    # Node classification
    node_type: WBSNodeType
    status: WBSNodeStatus

    # Scheduling
    planned_start: datetime | None
    planned_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None

    # Budget
    budget_allocated: float | None
    budget_spent: float

    # Metadata
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @property
    def is_root(self) -> bool:
        """Check if this is a root node."""
        return self.parent_id is None and self.depth == 0

    @property
    def is_leaf(self) -> bool:
        """Check if this is a leaf node (no children)."""
        return self.rgt == self.lft + 1

    @property
    def children_count(self) -> int:
        """Calculate number of direct children."""
        # This is an approximation; actual count requires repository query
        return (self.rgt - self.lft - 1) // 2 if not self.is_leaf else 0

    @property
    def budget_variance(self) -> float | None:
        """Calculate budget variance (allocated - spent)."""
        if self.budget_allocated is None:
            return None
        return self.budget_allocated - self.budget_spent

    @property
    def budget_utilization_pct(self) -> float | None:
        """Calculate budget utilization percentage."""
        if self.budget_allocated is None or self.budget_allocated == 0:
            return None
        return (self.budget_spent / self.budget_allocated) * 100

    @property
    def is_completed(self) -> bool:
        """Check if node is completed."""
        return self.status == WBSNodeStatus.COMPLETED

    @property
    def is_active(self) -> bool:
        """Check if node is actively being worked on."""
        return self.status == WBSNodeStatus.IN_PROGRESS

    def __str__(self) -> str:
        return f"WBSNode({self.code}: {self.name})"
