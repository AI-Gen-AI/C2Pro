"""
Data Transfer Objects (DTOs) for the Project module.

These models define the data structures for API requests and responses.
They are part of the application layer and are used to transfer data between
the presentation layer (API routers) and the application services (use cases).

Refers to Suite ID: TS-UA-DTO-ALL-001.
"""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Import domain enums
from src.projects.domain.models import ProjectStatus, ProjectType

# ===========================================
# REQUEST DTOs (Input)
# ===========================================

class ProjectCreateRequest(BaseModel):
    """DTO for creating a new project."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)
    code: str | None = Field(None, max_length=50, description="Internal project code")
    project_type: ProjectType = ProjectType.CONSTRUCTION
    estimated_budget: float | None = Field(None, ge=0, description="Estimated budget")
    currency: str = Field(default="EUR", max_length=3)
    start_date: datetime | None = None
    end_date: datetime | None = None
    metadata: dict = Field(default_factory=dict)

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: datetime | None, info) -> datetime | None:
        if v and "start_date" in info.data and info.data["start_date"]:
            if v <= info.data["start_date"]:
                raise ValueError("end_date must be after start_date")
        return v

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

class ProjectUpdateRequest(BaseModel):
    """DTO for updating a project."""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)
    code: str | None = Field(None, max_length=50)
    project_type: ProjectType | None = None
    status: ProjectStatus | None = None
    estimated_budget: float | None = Field(None, ge=0)
    currency: str | None = Field(None, max_length=3)
    start_date: datetime | None = None
    end_date: datetime | None = None
    metadata: dict | None = None


# ===========================================
# RESPONSE DTOs (Output)
# ===========================================

class ProjectDetailResponse(BaseModel):
    """Detailed DTO for a single project."""
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    code: str | None
    project_type: ProjectType
    status: ProjectStatus
    estimated_budget: float | None
    currency: str
    start_date: datetime | None
    end_date: datetime | None
    coherence_score: int | None
    last_analysis_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ProjectListResponse(BaseModel):
    """Paginated DTO for a list of projects."""
    items: list[ProjectDetailResponse] # Can be a more lightweight item later
    total: int
    page: int
    page_size: int

# ===========================================
# FILTERS DTO
# ===========================================

class ProjectFilters(BaseModel):
    """DTO for project search filters."""
    search: str | None = Field(None, description="Search term in name, description, or code")
    status: ProjectStatus | None = None
    project_type: ProjectType | None = None
    min_coherence_score: int | None = Field(None, ge=0, le=100)
    max_coherence_score: int | None = Field(None, ge=0, le=100)
    has_alerts: bool | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
