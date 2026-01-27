"""
Data Transfer Objects (DTOs) for the Stakeholders module.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

# Import enums from the new domain models
from src.stakeholders.domain.models import InterestLevel, PowerLevel, RACIRole, StakeholderQuadrant


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


class RACIBase(BaseModel):
    """Base schema for RACI matrix assignments."""

    stakeholder_id: UUID = Field(..., description="Stakeholder ID")
    wbs_item_id: UUID = Field(..., description="WBS Item ID")
    raci_role: RACIRole = Field(
        ..., description="RACI role (Responsible, Accountable, Consulted, Informed)"
    )
    evidence_text: Optional[str] = Field(
        None, description="Evidence snippet supporting the assignment"
    )


# ---------------------------------------------------------------------------
# Request Schemas (Create & Update)
# ---------------------------------------------------------------------------


class StakeholderCreate(StakeholderBase):
    """
    Schema for creating a new stakeholder.
    """

    project_id: UUID = Field(..., description="ID of the project this stakeholder belongs to")

    source_clause_id: Optional[UUID] = Field(
        None, description="FK to the clause mentioning this stakeholder (required if AI extracted)"
    )

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


# ---------------------------------------------------------------------------
# API Schemas for Stakeholder Matrix (Power/Interest)
# ---------------------------------------------------------------------------


class StakeholderCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    role: Optional[str] = Field(None, max_length=100)
    company: Optional[str] = Field(None, max_length=255)
    department: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    type: Optional[str] = Field(None, max_length=50)
    power_score: Optional[int] = Field(None, ge=1, le=10)
    interest_score: Optional[int] = Field(None, ge=1, le=10)
    source_clause_id: Optional[UUID] = None
    stakeholder_metadata: Optional[dict] = None
    feedback_comment: Optional[str] = Field(None, max_length=500)


class StakeholderUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    role: Optional[str] = Field(None, max_length=100)
    company: Optional[str] = Field(None, max_length=255)
    department: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    type: Optional[str] = Field(None, max_length=50)
    power_score: Optional[int] = Field(None, ge=1, le=10)
    interest_score: Optional[int] = Field(None, ge=1, le=10)
    source_clause_id: Optional[UUID] = None
    stakeholder_metadata: Optional[dict] = None
    feedback_comment: Optional[str] = Field(None, max_length=500)

    model_config = ConfigDict(extra="forbid")


class StakeholderResponseOut(BaseModel):
    id: UUID
    project_id: UUID
    name: Optional[str]
    role: Optional[str]
    company: Optional[str]
    department: Optional[str]
    email: Optional[EmailStr]
    phone: Optional[str]
    power_score: int
    interest_score: int
    power_level: PowerLevel
    interest_level: InterestLevel
    quadrant: Optional[StakeholderQuadrant]
    source_clause_id: Optional[UUID]

    model_config = ConfigDict(from_attributes=True)


class RACICreate(RACIBase):
    """
    Schema for creating a new RACI assignment.
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


# ---------------------------------------------------------------------------
# RACI Matrix Visualization Schemas
# ---------------------------------------------------------------------------


class RaciMatrixItem(BaseModel):
    """
    Schema for visualizing the RACI matrix.
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
    """

    project_id: UUID = Field(..., description="Project ID")
    matrix_items: list[RaciMatrixItem] = Field(
        default_factory=list, description="List of RACI matrix items"
    )
    total_assignments: int = Field(0, description="Total number of RACI assignments")
    unverified_count: int = Field(0, description="Number of unverified assignments")


class RaciMatrixAssignment(BaseModel):
    """Assignment cell for the matrix view (task x stakeholder)."""

    stakeholder_id: UUID = Field(..., description="Stakeholder ID")
    role: str = Field(..., description="RACI role label (RESPONSIBLE, ACCOUNTABLE, CONSULTED, INFORMED)")
    is_verified: bool = Field(False, description="Whether this assignment is manually verified")


class RaciMatrixTaskRow(BaseModel):
    """Matrix row for a task with its stakeholder assignments."""

    task_id: UUID = Field(..., description="Task (WBS item) ID")
    task_name: str = Field(..., description="Task name")
    assignments: list[RaciMatrixAssignment] = Field(
        default_factory=list, description="Assignments for this task"
    )


class RaciMatrixViewResponse(BaseModel):
    """Response schema for the nested matrix view."""

    matrix: list[RaciMatrixTaskRow] = Field(default_factory=list, description="Matrix rows")


class RaciAssignmentUpsertRequest(BaseModel):
    """Request schema for creating or updating a single assignment."""

    task_id: UUID = Field(..., description="Task (WBS item) ID")
    stakeholder_id: UUID = Field(..., description="Stakeholder ID")
    role: str = Field(..., description="RACI role label (RESPONSIBLE, ACCOUNTABLE, CONSULTED, INFORMED)")


class RaciAssignmentUpsertResponse(BaseModel):
    """Response schema for a created or updated assignment."""

    task_id: UUID = Field(..., description="Task (WBS item) ID")
    stakeholder_id: UUID = Field(..., description="Stakeholder ID")
    role: str = Field(..., description="RACI role label (RESPONSIBLE, ACCOUNTABLE, CONSULTED, INFORMED)")
    is_verified: bool = Field(False, description="Whether this assignment is manually verified")
