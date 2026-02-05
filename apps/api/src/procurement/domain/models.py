"""
Domain models for the Procurement bounded context.
These are pure domain entities representing core business concepts.

Refers to Suite ID: TS-UD-PROC-BOM-001.
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
    # Required fields first
    project_id: UUID
    code: str
    name: str
    level: int

    # Optional/default fields after
    id: UUID = field(default_factory=uuid4)
    description: Optional[str] = None
    parent_code: Optional[str] = None
    item_type: Optional[WBSItemType] = None
    budget_allocated: Optional[Decimal] = None
    budget_spent: Decimal = field(default=Decimal(0))
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    source_clause_id: Optional[UUID] = None
    wbs_metadata: dict = field(default_factory=dict)
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
    # Required fields first
    project_id: UUID
    item_name: str
    quantity: Decimal

    # Optional/default fields after
    id: UUID = field(default_factory=uuid4)
    wbs_item_id: Optional[UUID] = None
    item_code: Optional[str] = None
    description: Optional[str] = None
    category: Optional[BOMCategory] = None
    unit: Optional[str] = None
    unit_price: Optional[Decimal] = None
    total_price: Optional[Decimal] = None
    currency: str = "EUR"
    supplier: Optional[str] = None
    lead_time_days: Optional[int] = None
    production_time_days: Optional[int] = None
    transit_time_days: Optional[int] = None
    incoterm: Optional[str] = None
    contract_clause_id: Optional[UUID] = None
    budget_item_id: Optional[UUID] = None
    procurement_status: ProcurementStatus = ProcurementStatus.PENDING
    bom_metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Derive total_price and lead_time_days when omitted."""
        if self.project_id is None:
            raise ValueError("project_id is required")
        if not self.item_name or not self.item_name.strip():
            raise ValueError("item_name is required")
        if self.quantity is None or self.quantity <= 0:
            raise ValueError("quantity must be > 0")
        if self.unit_price is not None and self.unit_price < 0:
            raise ValueError("unit_price must be >= 0")
        if len(self.currency) != 3 or not self.currency.isupper():
            raise ValueError("currency must be 3 uppercase letters")
        for value in (self.lead_time_days, self.production_time_days, self.transit_time_days):
            if value is not None and value < 0:
                raise ValueError("time component must be >= 0")

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
