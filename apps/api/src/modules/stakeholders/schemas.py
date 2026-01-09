"""
Pydantic Schemas for Stakeholder Intelligence Module

This module defines the DTOs for Stakeholders, WBS, BOM, and RACI,
ensuring data validation and clear API contracts.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.modules.stakeholders.models import (
    BOMCategory,
    InterestLevel,
    PowerLevel,
    ProcurementStatus,
    RACIRole,
    StakeholderQuadrant,
    WBSItemType,
)

# ---------------------------------------------------------------------------
# Base Schemas
# ---------------------------------------------------------------------------


class StakeholderBase(BaseModel):
    """Base schema for stakeholder attributes."""

    project_id: UUID = Field(..., description="ID of the project this stakeholder belongs to")
    name: str | None = Field(None, max_length=255, description="Full name of the stakeholder")
    role: str | None = Field(
        None, max_length=100, description="Role or position of the stakeholder"
    )
    organization: str | None = Field(
        None, max_length=255, description="Organization the stakeholder belongs to"
    )
    department: str | None = Field(
        None, max_length=100, description="Department within the organization"
    )
    power_level: PowerLevel = Field(
        PowerLevel.MEDIUM, description="Influence level of the stakeholder"
    )
    interest_level: InterestLevel = Field(
        InterestLevel.MEDIUM, description="Interest level of the stakeholder"
    )
    quadrant: StakeholderQuadrant | None = Field(None, description="Power/Interest grid quadrant")
    email: str | None = Field(None, max_length=255, description="Contact email")
    phone: str | None = Field(None, max_length=50, description="Contact phone number")
    stakeholder_metadata: dict = Field(default_factory=dict, description="Custom metadata")


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
    wbs_metadata: dict = Field(default_factory=dict, description="Custom metadata")


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
    procurement_status: ProcurementStatus = Field(
        ProcurementStatus.PENDING, description="Current procurement status"
    )
    bom_metadata: dict = Field(default_factory=dict, description="Custom metadata")


class RACIBase(BaseModel):
    """Base schema for RACI matrix assignments."""

    project_id: UUID = Field(..., description="Project ID")
    stakeholder_id: UUID = Field(..., description="Stakeholder ID")
    wbs_item_id: UUID = Field(..., description="WBS Item ID")
    raci_role: RACIRole = Field(
        ..., description="RACI role (Responsible, Accountable, Consulted, Informed)"
    )


# ---------------------------------------------------------------------------
# Request Schemas (Create & Update)
# ---------------------------------------------------------------------------


class StakeholderCreate(StakeholderBase):
    """Schema for creating a new stakeholder, including the source clause."""

    source_clause_id: UUID | None = Field(
        None, description="FK to the clause mentioning this stakeholder"
    )


class StakeholderUpdate(BaseModel):
    """Schema for updating a stakeholder. All fields are optional."""

    name: str | None = Field(None, max_length=255)
    role: str | None = Field(None, max_length=100)
    organization: str | None = Field(None, max_length=255)
    power_level: PowerLevel | None = None
    interest_level: InterestLevel | None = None
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    stakeholder_metadata: dict | None = None


class WBSItemCreate(WBSItemBase):
    """Schema for creating a new WBS item, including the funding clause."""

    funded_by_clause_id: UUID | None = Field(
        None, description="FK to the clause that funds this WBS item"
    )


class WBSItemUpdate(BaseModel):
    """Schema for updating a WBS item. All fields are optional."""

    parent_id: UUID | None = None
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    budget_allocated: Decimal | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    wbs_metadata: dict | None = None


class BOMItemCreate(BOMItemBase):
    """Schema for creating a new BOM item, including the contractual clause."""

    contract_clause_id: UUID | None = Field(
        None, description="FK to the clause defining this BOM item"
    )


class BOMItemUpdate(BaseModel):
    """Schema for updating a BOM item. All fields are optional."""

    item_name: str | None = Field(None, max_length=255)
    quantity: Decimal | None = Field(None, gt=Decimal(0))
    unit_price: Decimal | None = None
    supplier: str | None = Field(None, max_length=255)
    procurement_status: ProcurementStatus | None = None
    bom_metadata: dict | None = None


class RACICreate(RACIBase):
    """Schema for creating a new RACI assignment."""

    pass


class RACIUpdate(BaseModel):
    """Schema for updating a RACI role."""

    raci_role: RACIRole


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------


class StakeholderResponse(StakeholderBase):
    """Response schema for a stakeholder, including IDs and timestamps."""

    id: UUID
    source_clause_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WBSItemResponse(WBSItemBase):
    """Response schema for a WBS item, including IDs and timestamps."""

    id: UUID
    funded_by_clause_id: UUID | None
    children: list["WBSItemResponse"] = []  # Self-referencing for hierarchy
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Required for self-referencing model
WBSItemResponse.model_rebuild()


class BOMItemResponse(BOMItemBase):
    """Response schema for a BOM item, including IDs and timestamps."""

    id: UUID
    contract_clause_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RACIResponse(RACIBase):
    """Response schema for a RACI assignment, including ID and verification status."""

    id: UUID
    generated_automatically: bool
    manually_verified: bool
    verified_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StakeholderDetailResponse(StakeholderResponse):
    """Detailed stakeholder response including their RACI assignments."""

    raci_assignments: list[RACIResponse] = []


class WBSDetailResponse(WBSItemResponse):
    """Detailed WBS item response including RACI assignments and BOM items."""

    raci_assignments: list[RACIResponse] = []
    bom_items: list[BOMItemResponse] = []
