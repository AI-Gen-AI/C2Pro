"""
Data Transfer Objects (DTOs) for the Procurement module.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Import enums from the new domain models
from src.procurement.domain.models import BOMCategory, ProcurementStatus, WBSItemType


class WBSItemBase(BaseModel):
    """Base schema for Work Breakdown Structure (WBS) item attributes."""

    project_id: UUID = Field(..., description="ID of the project this WBS item belongs to")
    parent_id: UUID | None = Field(
        None, description="ID of the parent WBS item for hierarchical structure"
    )
    wbs_code: str = Field(
        ..., max_length=50, description="Unique code for the WBS item (e.g., '1.2.1')"
    )
    name: str = Field(..., max_length=255, description="Name of the WBS item")
    description: str | None = Field(None, description="Detailed description of the WBS item")
    level: int = Field(..., ge=0, description="Hierarchy level of the item")
    item_type: WBSItemType | None = Field(None, description="Type of the WBS item")
    budget_allocated: Decimal | None = Field(None, description="Allocated budget for this item")
    budget_spent: Decimal = Field(Decimal(0), description="Budget spent to date")
    planned_start: datetime | None = Field(None, description="Planned start date")
    planned_end: datetime | None = Field(None, description="Planned end date")
    actual_start: datetime | None = Field(None, description="Actual start date")
    actual_end: datetime | None = Field(None, description="Actual end date")
    wbs_metadata: dict[str, object] = Field(default_factory=dict, description="Custom metadata")


class BOMItemBase(BaseModel):
    """Base schema for Bill of Materials (BOM) item attributes."""

    project_id: UUID = Field(..., description="ID of the project this BOM item belongs to")
    wbs_item_id: UUID | None = Field(None, description="Associated WBS item ID")
    item_code: str | None = Field(None, max_length=50, description="SKU or item code")
    item_name: str = Field(..., max_length=255, description="Name of the material or service")
    description: str | None = Field(None, description="Detailed description")
    category: BOMCategory | None = Field(None, description="Category of the BOM item")
    quantity: Decimal = Field(..., gt=Decimal(0), description="Required quantity")
    unit: str | None = Field(
        None, max_length=20, description="Unit of measure (e.g., 'kg', 'm2', 'units')"
    )
    unit_price: Decimal | None = Field(None, description="Price per unit")
    total_price: Decimal | None = Field(None, description="Total price (quantity * unit_price)")
    currency: str = Field("EUR", max_length=3, description="Currency code (e.g., 'EUR', 'USD')")
    supplier: str | None = Field(None, max_length=255, description="Supplier name")
    lead_time_days: int | None = Field(None, ge=0, description="Procurement lead time in days")
    incoterm: str | None = Field(
        None, max_length=20, description="Incoterm for delivery (e.g., 'FOB', 'CIF')"
    )
    source_document_id: UUID | None = Field(
        None, description="Source document that produced this parsed BOM item"
    )
    procurement_status: ProcurementStatus = Field(
        ProcurementStatus.PENDING, description="Current procurement status"
    )
    bom_metadata: dict[str, object] = Field(default_factory=dict, description="Custom metadata")


class WBSItemCreate(WBSItemBase):
    """Schema for creating a new WBS item, including the funding clause."""

    funded_by_clause_id: UUID | None = Field(
        None, description="FK to the clause that funds this WBS item"
    )


class WBSItemUpdate(BaseModel):
    """Schema for updating a WBS item. All fields are optional."""

    expected_version: int | None = Field(None, ge=1)
    parent_id: UUID | None = None
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    budget_allocated: Decimal | None = None
    budget_spent: Decimal | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    wbs_metadata: dict[str, object] | None = None

    model_config = ConfigDict(extra="forbid")


class BOMItemCreate(BOMItemBase):
    """Schema for creating a new BOM item, including the contractual clause."""

    contract_clause_id: UUID | None = Field(
        None, description="FK to the clause defining this BOM item"
    )


class BOMItemUpdate(BaseModel):
    """Schema for updating a BOM item. All fields are optional."""

    item_name: str | None = Field(None, max_length=255)
    description: str | None = None
    quantity: Decimal | None = Field(None, gt=Decimal(0))
    unit: str | None = Field(None, max_length=20)
    unit_price: Decimal | None = None
    total_price: Decimal | None = None
    supplier: str | None = Field(None, max_length=255)
    lead_time_days: int | None = Field(None, ge=0)
    source_document_id: UUID | None = None
    procurement_status: ProcurementStatus | None = None
    bom_metadata: dict[str, object] | None = None

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------


class WBSItemResponse(WBSItemBase):
    """Response schema for a WBS item, including IDs and timestamps."""

    id: UUID = Field(..., description="Unique ID of the WBS item")
    funded_by_clause_id: UUID | None = Field(
        None, description="FK to the funding clause (legal traceability)"
    )
    children: list["WBSItemResponse"] = []  # Self-referencing for hierarchy
    created_at: datetime = Field(..., description="Timestamp of creation")
    updated_at: datetime = Field(..., description="Timestamp of last update")

    model_config = ConfigDict(from_attributes=True)


# Required for self-referencing model
WBSItemResponse.model_rebuild()


class BOMItemResponse(BOMItemBase):
    """Response schema for a BOM item, including IDs and timestamps."""

    id: UUID = Field(..., description="Unique ID of the BOM item")
    contract_clause_id: UUID | None = Field(
        None, description="FK to the contract clause (legal traceability)"
    )
    created_at: datetime = Field(..., description="Timestamp of creation")
    updated_at: datetime = Field(..., description="Timestamp of last update")

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Planning Schemas
# ---------------------------------------------------------------------------


class ProcurementPlanningRequest(BaseModel):
    """Request DTO for procurement planning."""

    project_id: UUID
    required_on_site: datetime


class PlanningDecision(BaseModel):
    """Service output for procurement planning decisions."""

    plan_fingerprint: str
    conflicts: list[dict[str, object]] = Field(default_factory=list)
    requires_human_review: bool = False
