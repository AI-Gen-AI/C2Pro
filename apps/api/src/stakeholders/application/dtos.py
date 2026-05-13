"""
Data Transfer Objects (DTOs) for the Stakeholders module.

Refers to Suite ID: TS-UA-DTO-ALL-001.
"""
from datetime import datetime
from decimal import Decimal
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
    email: EmailStr | None = Field(None, description="Contact email (validated)")
    phone: str | None = Field(None, max_length=50, description="Contact phone number")
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
    evidence_text: str | None = Field(
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

    source_clause_id: UUID | None = Field(
        None, description="FK to the clause mentioning this stakeholder (required if AI extracted)"
    )

    extraction_confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="AI confidence score (0.0-1.0)"
    )
    extracted_from_document_id: UUID | None = Field(
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

    name: str | None = Field(None, min_length=1, max_length=255, description="Updated name")
    role: str | None = Field(None, max_length=100, description="Updated role")
    organization: str | None = Field(None, max_length=255, description="Updated organization")
    department: str | None = Field(None, max_length=100, description="Updated department")
    power_level: PowerLevel | None = Field(None, description="Updated power level")
    interest_level: InterestLevel | None = Field(None, description="Updated interest level")
    quadrant: StakeholderQuadrant | None = Field(None, description="Updated quadrant")
    email: EmailStr | None = Field(None, description="Updated email (validated)")
    phone: str | None = Field(None, max_length=50, description="Updated phone")
    extraction_confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Updated confidence score"
    )
    stakeholder_metadata: dict | None = Field(None, description="Updated metadata")

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v: str | None) -> str | None:
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
    role: str | None = Field(None, max_length=100)
    company: str | None = Field(None, max_length=255)
    department: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    type: str | None = Field(None, max_length=50)
    power_score: int | None = Field(None, ge=1, le=10)
    interest_score: int | None = Field(None, ge=1, le=10)
    source_clause_id: UUID | None = None
    stakeholder_metadata: dict | None = None
    feedback_comment: str | None = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("name cannot be empty or whitespace only")
        return value.strip()


class StakeholderUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    role: str | None = Field(None, max_length=100)
    company: str | None = Field(None, max_length=255)
    department: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    type: str | None = Field(None, max_length=50)
    power_score: int | None = Field(None, ge=1, le=10)
    interest_score: int | None = Field(None, ge=1, le=10)
    source_clause_id: UUID | None = None
    stakeholder_metadata: dict | None = None
    feedback_comment: str | None = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("name cannot be empty or whitespace only")
        return value.strip()

    model_config = ConfigDict(extra="forbid")


class StakeholderResponseOut(BaseModel):
    id: UUID
    project_id: UUID
    name: str | None
    role: str | None
    company: str | None
    department: str | None
    email: str | None
    phone: str | None
    power_score: int | None
    interest_score: int | None
    power_level: PowerLevel
    interest_level: InterestLevel
    quadrant: StakeholderQuadrant | None
    source_clause_id: UUID | None

    model_config = ConfigDict(from_attributes=True)


class RACICreate(RACIBase):
    """
    Schema for creating a new RACI assignment.
    """

    project_id: UUID = Field(..., description="Project ID")

    # Additional metadata (optional)
    approval_threshold: Decimal | None = Field(
        None,
        gt=Decimal(0),
        description="Financial approval threshold for this stakeholder on this WBS item (optional)",
    )
    requires_review: bool = Field(
        False, description="Flag indicating if this assignment requires review"
    )

    @field_validator("approval_threshold")
    @classmethod
    def validate_approval_threshold(cls, v: Decimal | None) -> Decimal | None:
        """Validate that approval_threshold is positive if provided."""
        if v is not None and v <= 0:
            raise ValueError("approval_threshold must be positive")
        return v


class RACIUpdate(BaseModel):
    """Schema for updating a RACI assignment."""

    raci_role: RACIRole | None = Field(None, description="Updated RACI role")
    approval_threshold: Decimal | None = Field(
        None, gt=Decimal(0), description="Updated approval threshold"
    )
    requires_review: bool | None = Field(None, description="Updated review requirement")

    @field_validator("approval_threshold")
    @classmethod
    def validate_approval_threshold(cls, v: Decimal | None) -> Decimal | None:
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
    source_clause_id: UUID | None = Field(
        None, description="FK to the source clause (legal traceability)"
    )

    # AI extraction metadata
    extraction_confidence: float | None = Field(
        None, description="AI confidence score (0.0-1.0)"
    )
    extracted_from_document_id: UUID | None = Field(
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
    verified_at: datetime | None = Field(None, description="Timestamp of verification")
    verified_by: UUID | None = Field(None, description="User who verified this assignment")

    # Additional fields (if added to model in the future)
    approval_threshold: Decimal | None = Field(
        None, description="Financial approval threshold"
    )
    requires_review: bool | None = Field(None, description="Review requirement flag")

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
    stakeholder_role: str | None = Field(None, description="Stakeholder role")
    stakeholder_organization: str | None = Field(None, description="Organization")

    wbs_item_id: UUID = Field(..., description="WBS Item ID")
    wbs_code: str = Field(..., description="WBS code (e.g., '1.2.3')")
    wbs_name: str = Field(..., description="WBS item name")

    raci_role: RACIRole = Field(..., description="RACI role")
    approval_threshold: Decimal | None = Field(None, description="Approval threshold")

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
    stakeholder_name: str | None = Field(None, description="Stakeholder name")
    role: str = Field(..., description="RACI role label (RESPONSIBLE, ACCOUNTABLE, CONSULTED, INFORMED)")
    is_verified: bool = Field(False, description="Whether this assignment is manually verified")


class RaciMatrixTaskRow(BaseModel):
    """Matrix row for a task with its stakeholder assignments."""

    task_id: UUID = Field(..., description="Task (WBS item) ID")
    task_code: str = Field(..., description="Task code")
    task_name: str = Field(..., description="Task name")
    sequence_index: int = Field(..., description="Timeline sequence index for the task")
    planned_start: datetime | None = Field(None, description="Planned start date")
    planned_end: datetime | None = Field(None, description="Planned end date")
    assignments: list[RaciMatrixAssignment] = Field(
        default_factory=list, description="Assignments for this task"
    )


class RaciMatrixViewResponse(BaseModel):
    """Response schema for the nested matrix view."""

    matrix: list[RaciMatrixTaskRow] = Field(default_factory=list, description="Matrix rows")


class RaciFlatRow(BaseModel):
    """Flat RACI row for global view."""

    task_id: UUID
    task_name: str
    project_id: UUID
    project_name: str
    assignments: list[RaciMatrixAssignment] = Field(default_factory=list)


class RaciGlobalViewResponse(BaseModel):
    """Response schema for global RACI view across all projects."""

    rows: list[RaciFlatRow] = Field(default_factory=list, description="All RACI rows across projects")
    total_tasks: int = 0
    total_assignments: int = 0


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


# ---------------------------------------------------------------------------
# AI RACI Generation DTOs
# ---------------------------------------------------------------------------


class RaciWBSItemInput(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    clause_text: str | None = None


class RaciStakeholderInput(BaseModel):
    id: UUID
    name: str | None = None
    role: str | None = None
    company: str | None = None
    stakeholder_type: str | None = None


class RaciGenerationAssignment(BaseModel):
    wbs_item_id: UUID
    stakeholder_id: UUID
    role: RACIRole
    evidence_text: str | None = None


class RaciGenerationResult(BaseModel):
    assignments: list[RaciGenerationAssignment]
    warnings: list[str] = Field(default_factory=list)
