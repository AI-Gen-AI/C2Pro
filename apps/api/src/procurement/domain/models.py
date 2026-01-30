"""
Domain models for the Procurement bounded context.
These are pure domain entities representing core business concepts.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from uuid import UUID, uuid4


# ===========================================
# ENUMS
# ===========================================


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


# ===========================================
# BUDGET-RELATED DOMAIN MODELS
# ===========================================


@dataclass
class BudgetItem:
    """Represents a single item from the project budget."""
    id: UUID
    name: str
    code: str
    amount: float


# ===========================================
# WBS DOMAIN MODELS
# ===========================================


@dataclass
class WBSItem:
    """
    Domain entity representing a Work Breakdown Structure item.
    Used for AI generation and business logic.
    """
    # Identity
    id: UUID = field(default_factory=uuid4)
    project_id: UUID

    # Hierarchy
    code: str
    name: str
    description: Optional[str] = None
    level: int
    parent_code: Optional[str] = None

    # Classification
    item_type: Optional[WBSItemType] = None

    # Financial
    budget_allocated: Optional[Decimal] = None
    budget_spent: Decimal = field(default=Decimal(0))

    # Schedule
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None

    # Traceability
    source_clause_id: Optional[UUID] = None

    # Metadata
    wbs_metadata: dict = field(default_factory=dict)

    # Relationships (not persisted directly, loaded separately)
    children: List["WBSItem"] = field(default_factory=list)

    def is_leaf(self) -> bool:
        """Check if this WBS item is a leaf node (has no children)."""
        return len(self.children) == 0

    def is_completed(self) -> bool:
        """Check if this WBS item is completed."""
        return self.actual_end is not None

    def is_started(self) -> bool:
        """Check if this WBS item has started."""
        return self.actual_start is not None

    def get_budget_variance(self) -> Decimal:
        """Calculate the budget variance (allocated - spent)."""
        if self.budget_allocated is None:
            return Decimal(0)
        return self.budget_allocated - self.budget_spent

    def is_over_budget(self) -> bool:
        """Check if this WBS item is over budget."""
        if self.budget_allocated is None:
            return False
        return self.budget_spent > self.budget_allocated


@dataclass
class WBSItemList:
    """Container for a list of WBS items, used for structured LLM output."""
    items: List[WBSItem] = field(default_factory=list)


# ===========================================
# BOM DOMAIN MODELS
# ===========================================


@dataclass
class BOMItem:
    """
    Domain entity representing a Bill of Materials item.
    Used for AI generation and business logic.
    """
    # Identity
    id: UUID = field(default_factory=uuid4)
    project_id: UUID
    wbs_item_id: Optional[UUID] = None

    # Identification
    item_code: Optional[str] = None
    item_name: str
    description: Optional[str] = None
    category: Optional[BOMCategory] = None

    # Quantity
    quantity: Decimal
    unit: Optional[str] = None

    # Pricing
    unit_price: Optional[Decimal] = None
    total_price: Optional[Decimal] = None
    currency: str = "EUR"

    # Procurement
    supplier: Optional[str] = None
    lead_time_days: Optional[int] = None
    production_time_days: Optional[int] = None
    transit_time_days: Optional[int] = None
    incoterm: Optional[str] = None

    # Traceability
    contract_clause_id: Optional[UUID] = None
    budget_item_id: Optional[UUID] = None

    # Status
    procurement_status: ProcurementStatus = ProcurementStatus.PENDING

    # Metadata
    bom_metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Derive total_price and lead_time_days when omitted."""
        if self.total_price is None and self.unit_price is not None and self.quantity is not None:
            self.total_price = Decimal(str(self.unit_price)) * Decimal(str(self.quantity))
        if self.lead_time_days is None:
            production = self.production_time_days or 0
            transit = self.transit_time_days or 0
            if production or transit:
                self.lead_time_days = production + transit

    def get_total_cost(self) -> Decimal:
        """Get the total cost of this BOM item."""
        if self.total_price is not None:
            return self.total_price
        if self.unit_price is not None and self.quantity is not None:
            return self.unit_price * self.quantity
        return Decimal(0)

    def is_procurement_complete(self) -> bool:
        """Check if procurement is complete for this item."""
        return self.procurement_status == ProcurementStatus.DELIVERED

    def is_procurement_in_progress(self) -> bool:
        """Check if procurement is in progress."""
        return self.procurement_status in [
            ProcurementStatus.REQUESTED,
            ProcurementStatus.ORDERED,
            ProcurementStatus.IN_TRANSIT
        ]

    def update_status(self, new_status: ProcurementStatus) -> None:
        """Update the procurement status."""
        self.procurement_status = new_status

    def get_estimated_delivery_date(self, order_date: datetime) -> Optional[datetime]:
        """Calculate estimated delivery date based on order date and lead time."""
        if self.lead_time_days is None:
            return None
        from datetime import timedelta
        return order_date + timedelta(days=self.lead_time_days)


@dataclass
class BOMItemList:
    """Container for a list of BOM items, used for structured LLM output."""
    items: List[BOMItem] = field(default_factory=list)

    def get_total_cost(self) -> Decimal:
        """Calculate total cost of all BOM items."""
        return sum((item.get_total_cost() for item in self.items), Decimal(0))

    def filter_by_category(self, category: BOMCategory) -> List[BOMItem]:
        """Filter BOM items by category."""
        return [item for item in self.items if item.category == category]

    def filter_by_status(self, status: ProcurementStatus) -> List[BOMItem]:
        """Filter BOM items by procurement status."""
        return [item for item in self.items if item.procurement_status == status]
