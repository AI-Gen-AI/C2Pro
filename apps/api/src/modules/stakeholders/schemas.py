"""
Pydantic Schemas for Stakeholder Intelligence Module

This module defines the DTOs for Stakeholders, WBS, BOM, and RACI,
ensuring data validation and clear API contracts.
Includes strict validation for emails, required fields, and legal traceability.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

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

    name: str = Field(..., min_length=1, max_length=255, description="Full name of the stakeholder")
    role: Optional[str] = Field(
        None, max_length=100, description="Role or position of the stakeholder"
    )
    organization: Optional[str] = Field(
        None, max_length=255, description="Organization the stakeholder belongs to"
    )
    department: Optional[str] = Field(
        None, max_length=100, description="Department within the organization"
    )
    power_level: PowerLevel = Field(
        PowerLevel.MEDIUM, description="Influence level of the stakeholder"
    )
    interest_level: InterestLevel = Field(
        InterestLevel.MEDIUM, description="Interest level of the stakeholder"
    )
    quadrant: Optional[StakeholderQuadrant] = Field(None, description="Power/Interest grid quadrant")
    email: Optional[EmailStr] = Field(None, description="Contact email (validated)")
    phone: Optional[str] = Field(None, max_length=50, description="Contact phone number")
    stakeholder_metadata: dict = Field(default_factory=dict, description="Custom metadata")

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        """Validate that name is not empty or whitespace only."""
        if not v or not v.strip():
            raise ValueError("name cannot be empty or whitespace only")
        return v.strip()


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


class RACIBase(BaseModel):
    """Base schema for RACI matrix assignments."""

    stakeholder_id: UUID = Field(..., description="Stakeholder ID")
    wbs_item_id: UUID = Field(..., description="WBS Item ID")
    raci_role: RACIRole = Field(
        ..., description="RACI role (Responsible, Accountable, Consulted, Informed)"
    )


# ---------------------------------------------------------------------------
# Request Schemas (Create & Update)
# ---------------------------------------------------------------------------


class StakeholderCreate(StakeholderBase):
    """
    Schema for creating a new stakeholder.

    IMPORTANT: source_clause_id is optional for manual entry,
    but required when extracted by AI for legal traceability (ROADMAP §4.5).
    """

    project_id: UUID = Field(..., description="ID of the project this stakeholder belongs to")

    # CRITICAL: Legal traceability (ROADMAP §4.5)
    source_clause_id: Optional[UUID] = Field(
        None, description="FK to the clause mentioning this stakeholder (required if AI extracted)"
    )

    # AI extraction metadata
    extraction_confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="AI confidence score (0.0-1.0)"
    )
    extracted_from_document_id: Optional[UUID] = Field(
        None, description="FK to the document from which this stakeholder was extracted"
    )
    is_auto_extracted: bool = Field(
        False, description="Flag indicating if this stakeholder was auto-extracted by AI"
    )

    @model_validator(mode="after")
    def validate_auto_extraction(self):
        """Validate that auto-extracted stakeholders have extraction_confidence."""
        if self.is_auto_extracted and self.extraction_confidence is None:
            raise ValueError(
                "extraction_confidence is required when is_auto_extracted is True"
            )
        return self


class StakeholderUpdate(BaseModel):
    """Schema for updating a stakeholder. All fields are optional."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated name")
    role: Optional[str] = Field(None, max_length=100, description="Updated role")
    organization: Optional[str] = Field(None, max_length=255, description="Updated organization")
    department: Optional[str] = Field(None, max_length=100, description="Updated department")
    power_level: Optional[PowerLevel] = Field(None, description="Updated power level")
    interest_level: Optional[InterestLevel] = Field(None, description="Updated interest level")
    quadrant: Optional[StakeholderQuadrant] = Field(None, description="Updated quadrant")
    email: Optional[EmailStr] = Field(None, description="Updated email (validated)")
    phone: Optional[str] = Field(None, max_length=50, description="Updated phone")
    extraction_confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Updated confidence score"
    )
    stakeholder_metadata: Optional[dict] = Field(None, description="Updated metadata")

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Validate that name is not empty if provided."""
        if v is not None and (not v or not v.strip()):
            raise ValueError("name cannot be empty or whitespace only")
        return v.strip() if v else None

    model_config = ConfigDict(extra="forbid")


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


class RACICreate(RACIBase):
    """
    Schema for creating a new RACI assignment.

    Links stakeholders to WBS items with specific RACI roles.
    """

    project_id: UUID = Field(..., description="Project ID")

    # Additional metadata (optional)
    approval_threshold: Optional[Decimal] = Field(
        None,
        gt=Decimal(0),
        description="Financial approval threshold for this stakeholder on this WBS item (optional)",
    )
    requires_review: bool = Field(
        False, description="Flag indicating if this assignment requires review"
    )

    @field_validator("approval_threshold")
    @classmethod
    def validate_approval_threshold(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate that approval_threshold is positive if provided."""
        if v is not None and v <= 0:
            raise ValueError("approval_threshold must be positive")
        return v


class RACIUpdate(BaseModel):
    """Schema for updating a RACI assignment."""

    raci_role: Optional[RACIRole] = Field(None, description="Updated RACI role")
    approval_threshold: Optional[Decimal] = Field(
        None, gt=Decimal(0), description="Updated approval threshold"
    )
    requires_review: Optional[bool] = Field(None, description="Updated review requirement")

    @field_validator("approval_threshold")
    @classmethod
    def validate_approval_threshold(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate that approval_threshold is positive if provided."""
        if v is not None and v <= 0:
            raise ValueError("approval_threshold must be positive")
        return v

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------


class StakeholderResponse(StakeholderBase):
    """Response schema for a stakeholder, including IDs and timestamps."""

    id: UUID = Field(..., description="Unique ID of the stakeholder")
    project_id: UUID = Field(..., description="ID of the project")

    # Legal traceability
    source_clause_id: Optional[UUID] = Field(
        None, description="FK to the source clause (legal traceability)"
    )

    # AI extraction metadata
    extraction_confidence: Optional[float] = Field(
        None, description="AI confidence score (0.0-1.0)"
    )
    extracted_from_document_id: Optional[UUID] = Field(
        None, description="FK to the document from which this was extracted"
    )

    # Timestamps
    created_at: datetime = Field(..., description="Timestamp of creation")
    updated_at: datetime = Field(..., description="Timestamp of last update")

    model_config = ConfigDict(from_attributes=True)


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


class RACIResponse(RACIBase):
    """Response schema for a RACI assignment, including ID and verification status."""

    id: UUID = Field(..., description="Unique ID of the RACI assignment")
    project_id: UUID = Field(..., description="Project ID")

    # Metadata
    generated_automatically: bool = Field(
        ..., description="Flag indicating if this was auto-generated by AI"
    )
    manually_verified: bool = Field(..., description="Flag indicating if manually verified")
    verified_at: Optional[datetime] = Field(None, description="Timestamp of verification")
    verified_by: Optional[UUID] = Field(None, description="User who verified this assignment")

    # Additional fields (if added to model in the future)
    approval_threshold: Optional[Decimal] = Field(
        None, description="Financial approval threshold"
    )
    requires_review: Optional[bool] = Field(None, description="Review requirement flag")

    # Timestamp
    created_at: datetime = Field(..., description="Timestamp of creation")

    model_config = ConfigDict(from_attributes=True)


class StakeholderDetailResponse(StakeholderResponse):
    """Detailed stakeholder response including their RACI assignments."""

    raci_assignments: list[RACIResponse] = []


class WBSDetailResponse(WBSItemResponse):
    """Detailed WBS item response including RACI assignments and BOM items."""

    raci_assignments: list[RACIResponse] = []
    bom_items: list[BOMItemResponse] = []


# ---------------------------------------------------------------------------
# RACI Matrix Visualization Schemas
# ---------------------------------------------------------------------------


class RaciMatrixItem(BaseModel):
    """
    Schema for visualizing the RACI matrix.

    Provides a simplified view of stakeholder-WBS relationships
    for matrix display in the UI.
    """

    stakeholder_id: UUID = Field(..., description="Stakeholder ID")
    stakeholder_name: str = Field(..., description="Stakeholder name")
    stakeholder_role: Optional[str] = Field(None, description="Stakeholder role")
    stakeholder_organization: Optional[str] = Field(None, description="Organization")

    wbs_item_id: UUID = Field(..., description="WBS Item ID")
    wbs_code: str = Field(..., description="WBS code (e.g., '1.2.3')")
    wbs_name: str = Field(..., description="WBS item name")

    raci_role: RACIRole = Field(..., description="RACI role")
    approval_threshold: Optional[Decimal] = Field(None, description="Approval threshold")

    # Status flags
    is_verified: bool = Field(False, description="Whether this assignment is manually verified")
    is_auto_generated: bool = Field(True, description="Whether this was auto-generated")

    model_config = ConfigDict(from_attributes=False)


class RaciMatrixResponse(BaseModel):
    """
    Response schema for the complete RACI matrix view.

    Provides a structured representation of all RACI assignments
    for a project or specific scope.
    """

    project_id: UUID = Field(..., description="Project ID")
    matrix_items: list[RaciMatrixItem] = Field(
        default_factory=list, description="List of RACI matrix items"
    )
    total_assignments: int = Field(0, description="Total number of RACI assignments")
    unverified_count: int = Field(0, description="Number of unverified assignments")
