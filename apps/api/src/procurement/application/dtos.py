"""
Data Transfer Objects (DTOs) for the Procurement module.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Import enums from the new domain models
from src.procurement.domain.models import BOMCategory, ProcurementStatus, WBSItemType


class WBSItemBase(BaseModel):
    """Base schema for Work Breakdown Structure (WBS) item attributes."""

    project_id: UUID = Field(..., description="ID of the project this WBS item belongs to")
    parent_id: Optional[UUID] = Field(
        None, description="ID of the parent WBS item for hierarchical structure"
    )
    wbs_code: str = Field(
        ..., max_length=50, description="Unique code for the WBS item (e.g., '1.2.1')"
    )
    name: str = Field(..., max_length=255, description="Name of the WBS item")
    description: Optional[str] = Field(None, description="Detailed description of the WBS item")
    level: int = Field(..., ge=0, description="Hierarchy level of the item")
    item_type: Optional[WBSItemType] = Field(None, description="Type of the WBS item")
    budget_allocated: Optional[Decimal] = Field(None, description="Allocated budget for this item")
    budget_spent: Decimal = Field(Decimal(0), description="Budget spent to date")
    planned_start: Optional[datetime] = Field(None, description="Planned start date")
    planned_end: Optional[datetime] = Field(None, description="Planned end date")
    actual_start: Optional[datetime] = Field(None, description="Actual start date")
    actual_end: Optional[datetime] = Field(None, description="Actual end date")
    wbs_metadata: dict = Field(default_factory=dict, description="Custom metadata")


class BOMItemBase(BaseModel):
    """Base schema for Bill of Materials (BOM) item attributes."""

    project_id: UUID = Field(..., description="ID of the project this BOM item belongs to")
    wbs_item_id: Optional[UUID] = Field(None, description="Associated WBS item ID")
    item_code: Optional[str] = Field(None, max_length=50, description="SKU or item code")
    item_name: str = Field(..., max_length=255, description="Name of the material or service")
    description: Optional[str] = Field(None, description="Detailed description")
    category: Optional[BOMCategory] = Field(None, description="Category of the BOM item")
    quantity: Decimal = Field(..., gt=Decimal(0), description="Required quantity")
    unit: Optional[str] = Field(
        None, max_length=20, description="Unit of measure (e.g., 'kg', 'm2', 'units')"
    )
    unit_price: Optional[Decimal] = Field(None, description="Price per unit")
    total_price: Optional[Decimal] = Field(None, description="Total price (quantity * unit_price)")
    currency: str = Field("EUR", max_length=3, description="Currency code (e.g., 'EUR', 'USD')")
    supplier: Optional[str] = Field(None, max_length=255, description="Supplier name")
    lead_time_days: Optional[int] = Field(None, ge=0, description="Procurement lead time in days")
    incoterm: Optional[str] = Field(
        None, max_length=20, description="Incoterm for delivery (e.g., 'FOB', 'CIF')"
    )
    procurement_status: ProcurementStatus = Field(
        ProcurementStatus.PENDING, description="Current procurement status"
    )
    bom_metadata: dict = Field(default_factory=dict, description="Custom metadata")


class WBSItemCreate(WBSItemBase):
    """Schema for creating a new WBS item, including the funding clause."""

    funded_by_clause_id: Optional[UUID] = Field(
        None, description="FK to the clause that funds this WBS item"
    )


class WBSItemUpdate(BaseModel):
    """Schema for updating a WBS item. All fields are optional."""

    parent_id: Optional[UUID] = None
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    budget_allocated: Optional[Decimal] = None
    budget_spent: Optional[Decimal] = None
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    wbs_metadata: Optional[dict] = None

    model_config = ConfigDict(extra="forbid")


class BOMItemCreate(BOMItemBase):
    """Schema for creating a new BOM item, including the contractual clause."""

    contract_clause_id: Optional[UUID] = Field(
        None, description="FK to the clause defining this BOM item"
    )


class BOMItemUpdate(BaseModel):
    """Schema for updating a BOM item. All fields are optional."""

    item_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    quantity: Optional[Decimal] = Field(None, gt=Decimal(0))
    unit: Optional[str] = Field(None, max_length=20)
    unit_price: Optional[Decimal] = None
    total_price: Optional[Decimal] = None
    supplier: Optional[str] = Field(None, max_length=255)
    lead_time_days: Optional[int] = Field(None, ge=0)
    procurement_status: Optional[ProcurementStatus] = None
    bom_metadata: Optional[dict] = None

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------


class WBSItemResponse(WBSItemBase):
    """Response schema for a WBS item, including IDs and timestamps."""

    id: UUID = Field(..., description="Unique ID of the WBS item")
    funded_by_clause_id: Optional[UUID] = Field(
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
    contract_clause_id: Optional[UUID] = Field(
        None, description="FK to the contract clause (legal traceability)"
    )
    created_at: datetime = Field(..., description="Timestamp of creation")
    updated_at: datetime = Field(..., description="Timestamp of last update")

    model_config = ConfigDict(from_attributes=True)
