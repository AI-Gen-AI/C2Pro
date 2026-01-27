"""
Domain models for the Procurement bounded context.
These are pure domain entities representing core business concepts.
"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


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


class BudgetItem(BaseModel):
    """Represents a single item from the project budget."""
    id: UUID
    name: str
    code: str
    amount: float


# ===========================================
# WBS DOMAIN MODELS
# ===========================================


class WBSItem(BaseModel):
    """
    Domain entity representing a Work Breakdown Structure item.
    Used for AI generation and business logic.
    """
    # Identity
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID

    # Hierarchy
    code: str = Field(..., description="WBS code like '1.2.3'")
    name: str
    description: Optional[str] = None
    level: int = Field(..., ge=0)
    parent_code: Optional[str] = None

    # Classification
    item_type: Optional[WBSItemType] = None

    # Financial
    budget_allocated: Optional[Decimal] = None
    budget_spent: Decimal = Field(default=Decimal(0))

    # Schedule
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None

    # Traceability
    source_clause_id: Optional[UUID] = Field(
        None,
        description="Contract clause that defines this WBS item"
    )

    # Metadata
    wbs_metadata: dict = Field(default_factory=dict)

    # Relationships (not persisted directly, loaded separately)
    children: List[WBSItem] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "project_id": "123e4567-e89b-12d3-a456-426614174000",
                "code": "1.2.1",
                "name": "Foundation Works",
                "description": "Excavation and foundation construction",
                "level": 3,
                "parent_code": "1.2",
                "item_type": "work_package",
                "budget_allocated": "150000.00",
                "source_clause_id": "223e4567-e89b-12d3-a456-426614174001"
            }
        }

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


class WBSItemList(BaseModel):
    """Container for a list of WBS items, used for structured LLM output."""
    items: List[WBSItem] = Field(default_factory=list)


# ===========================================
# BOM DOMAIN MODELS
# ===========================================


class BOMItem(BaseModel):
    """
    Domain entity representing a Bill of Materials item.
    Used for AI generation and business logic.
    """
    # Identity
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    wbs_item_id: Optional[UUID] = None

    # Identification
    item_code: Optional[str] = None
    item_name: str
    description: Optional[str] = None
    category: Optional[BOMCategory] = None

    # Quantity
    quantity: Decimal = Field(..., gt=Decimal(0))
    unit: Optional[str] = None

    # Pricing
    unit_price: Optional[Decimal] = None
    total_price: Optional[Decimal] = None
    currency: str = Field(default="EUR")

    # Procurement
    supplier: Optional[str] = None
    lead_time_days: Optional[int] = Field(None, ge=0)
    production_time_days: Optional[int] = Field(None, ge=0)
    transit_time_days: Optional[int] = Field(None, ge=0)
    incoterm: Optional[str] = None

    # Traceability
    contract_clause_id: Optional[UUID] = Field(
        None,
        description="Contract clause that defines this BOM item"
    )
    budget_item_id: Optional[UUID] = Field(
        None,
        description="Linked budget item for cost tracking"
    )

    # Status
    procurement_status: ProcurementStatus = Field(default=ProcurementStatus.PENDING)

    # Metadata
    bom_metadata: dict = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "project_id": "123e4567-e89b-12d3-a456-426614174000",
                "wbs_item_id": "223e4567-e89b-12d3-a456-426614174001",
                "item_code": "MAT-001",
                "item_name": "Concrete C30/37",
                "description": "Ready-mix concrete for foundation",
                "category": "material",
                "quantity": "150.5",
                "unit": "m3",
                "unit_price": "95.50",
                "total_price": "14372.75",
                "currency": "EUR",
                "supplier": "ABC Concrete Ltd.",
                "lead_time_days": 7,
                "procurement_status": "pending"
            }
        }

    @field_validator('total_price', mode='before')
    def calculate_total_price(cls, v, info):
        """Automatically calculate total price if not provided."""
        if v is None and 'unit_price' in info.data and 'quantity' in info.data:
            unit_price = info.data.get('unit_price')
            quantity = info.data.get('quantity')
            if unit_price is not None and quantity is not None:
                return Decimal(str(unit_price)) * Decimal(str(quantity))
        return v

    @field_validator('lead_time_days', mode='before')
    def calculate_lead_time(cls, v, info):
        """Calculate total lead time from production and transit times if not provided."""
        if v is None:
            production = info.data.get('production_time_days', 0) or 0
            transit = info.data.get('transit_time_days', 0) or 0
            if production or transit:
                return production + transit
        return v

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


class BOMItemList(BaseModel):
    """Container for a list of BOM items, used for structured LLM output."""
    items: List[BOMItem] = Field(default_factory=list)

    def get_total_cost(self) -> Decimal:
        """Calculate total cost of all BOM items."""
        return sum((item.get_total_cost() for item in self.items), Decimal(0))

    def filter_by_category(self, category: BOMCategory) -> List[BOMItem]:
        """Filter BOM items by category."""
        return [item for item in self.items if item.category == category]

    def filter_by_status(self, status: ProcurementStatus) -> List[BOMItem]:
        """Filter BOM items by procurement status."""
        return [item for item in self.items if item.procurement_status == status]
