"""
C2Pro - Project Schemas

Schemas Pydantic para validación y serialización de proyectos.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.modules.projects.models import ProjectStatus, ProjectType

# ===========================================
# BASE SCHEMAS
# ===========================================


class ProjectBase(BaseModel):
    """Schema base para Project."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)
    code: str | None = Field(None, max_length=50)
    project_type: ProjectType = ProjectType.CONSTRUCTION
    estimated_budget: float | None = Field(None, ge=0)
    currency: str = Field(default="EUR", max_length=3)


# ===========================================
# REQUEST SCHEMAS (Input)
# ===========================================


class ProjectCreateRequest(BaseModel):
    """Request para crear nuevo proyecto."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)
    code: str | None = Field(None, max_length=50, description="Código interno del proyecto")
    project_type: ProjectType = ProjectType.CONSTRUCTION
    estimated_budget: float | None = Field(None, ge=0, description="Presupuesto estimado")
    currency: str = Field(default="EUR", max_length=3)
    start_date: datetime | None = None
    end_date: datetime | None = None
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Construcción Edificio Oficinas",
                "description": "Proyecto de construcción de edificio de oficinas de 5 plantas",
                "code": "PROJ-2024-001",
                "project_type": "construction",
                "estimated_budget": 1500000.00,
                "currency": "EUR",
                "start_date": "2024-01-15T00:00:00",
                "end_date": "2024-12-31T23:59:59",
            }
        }
    )

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: datetime | None, info) -> datetime | None:
        """Valida que la fecha de fin sea posterior a la de inicio."""
        if v and "start_date" in info.data and info.data["start_date"]:
            if v <= info.data["start_date"]:
                raise ValueError("end_date must be after start_date")
        return v


class ProjectUpdateRequest(BaseModel):
    """Request para actualizar proyecto."""

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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Construcción Edificio Oficinas - Actualizado",
                "status": "active",
                "estimated_budget": 1600000.00,
            }
        }
    )


# ===========================================
# RESPONSE SCHEMAS (Output)
# ===========================================


class ProjectListItemResponse(BaseModel):
    """Response para item en lista de proyectos (versión resumida)."""

    id: UUID
    name: str
    description: str | None
    code: str | None
    project_type: ProjectType
    status: ProjectStatus

    # Financial
    estimated_budget: float | None
    currency: str

    # Dates
    start_date: datetime | None
    end_date: datetime | None

    # Analysis
    coherence_score: int | None
    last_analysis_at: datetime | None

    # Computed properties
    document_count: int
    alert_count: dict[str, int]

    # Timestamps
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectDetailResponse(BaseModel):
    """Response detallado de proyecto (incluye relaciones)."""

    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    code: str | None
    project_type: ProjectType
    status: ProjectStatus

    # Financial
    estimated_budget: float | None
    currency: str

    # Dates
    start_date: datetime | None
    end_date: datetime | None

    # Analysis
    coherence_score: int | None
    last_analysis_at: datetime | None

    # Metadata
    metadata: dict

    # Computed properties
    has_contract: bool
    has_schedule: bool
    has_budget: bool
    is_ready_for_analysis: bool
    document_count: int
    alert_count: dict[str, int]

    # Timestamps
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectSummaryResponse(BaseModel):
    """Response de resumen de proyecto para dashboard."""

    id: UUID
    name: str
    code: str | None
    status: ProjectStatus
    coherence_score: int | None
    critical_alerts: int
    high_alerts: int
    medium_alerts: int
    document_count: int

    model_config = ConfigDict(from_attributes=True)


class ProjectStatsResponse(BaseModel):
    """Response con estadísticas de proyectos."""

    total_projects: int
    active_projects: int
    draft_projects: int
    completed_projects: int
    archived_projects: int

    avg_coherence_score: float | None
    total_critical_alerts: int
    total_high_alerts: int


# ===========================================
# DOCUMENT-RELATED SCHEMAS
# ===========================================


class DocumentListResponse(BaseModel):
    """Response básico de documento en lista."""

    id: UUID
    document_type: str
    filename: str
    file_format: str | None
    file_size_bytes: int | None
    upload_status: str
    parsed_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectWithDocumentsResponse(ProjectDetailResponse):
    """Response de proyecto con lista de documentos."""

    documents: list[DocumentListResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ===========================================
# BULK OPERATIONS
# ===========================================


class ProjectBulkDeleteRequest(BaseModel):
    """Request para eliminación masiva de proyectos."""

    project_ids: list[UUID] = Field(..., min_length=1, max_length=100)


class ProjectBulkStatusUpdateRequest(BaseModel):
    """Request para actualización masiva de estado."""

    project_ids: list[UUID] = Field(..., min_length=1, max_length=100)
    status: ProjectStatus


# ===========================================
# PAGINATION
# ===========================================


class ProjectListResponse(BaseModel):
    """Response paginado de lista de proyectos."""

    items: list[ProjectListItemResponse]
    total: int = Field(..., serialization_alias="total_count")
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both 'total' and 'total_count'
        json_schema_extra={
            "example": {
                "items": [],
                "total_count": 42,
                "page": 1,
                "page_size": 20,
                "total_pages": 3,
                "has_next": True,
                "has_prev": False,
            }
        },
    )


# ===========================================
# FILTERS
# ===========================================


class ProjectFilters(BaseModel):
    """Filtros para búsqueda de proyectos."""

    search: str | None = Field(None, description="Búsqueda en nombre, descripción o código")
    status: ProjectStatus | None = None
    project_type: ProjectType | None = None
    min_coherence_score: int | None = Field(None, ge=0, le=100)
    max_coherence_score: int | None = Field(None, ge=0, le=100)
    has_alerts: bool | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


# ===========================================
# ERROR SCHEMAS
# ===========================================


class ProjectErrorResponse(BaseModel):
    """Response de error de proyectos."""

    detail: str
    error_code: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"detail": "Project not found", "error_code": "PROJECT_NOT_FOUND"}
        }
    )


# ===========================================
# WBS-RELATED SCHEMAS
# ===========================================


class WBSItemBase(BaseModel):
    code: str = Field(..., description="WBS code, e.g., '1.1.2'")
    name: str = Field(..., description="Name of the WBS item")
    description: str | None = None
    level: int = Field(..., description="Level in the WBS hierarchy")
    start_date: datetime | None = None
    end_date: datetime | None = None
    cost: float | None = None


class WBSItemCreate(WBSItemBase):
    project_id: UUID
    parent_id: UUID | None = None


class WBSItemUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    description: str | None = None
    level: int | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    cost: float | None = None
    parent_id: UUID | None = None


class WBSItemResponse(WBSItemBase):
    id: UUID
    project_id: UUID
    parent_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================
# BOM-RELATED SCHEMAS
# ===========================================


class BOMItemBase(BaseModel):
    item_code: str | None = Field(None, description="Internal code for the BOM item")
    item_name: str = Field(..., description="Name of the BOM item")
    description: str | None = None
    quantity: float
    unit: str | None = None
    unit_price: float | None = None
    total_price: float | None = None
    supplier: str | None = None
    lead_time_days: int | None = None
    required_on_site_date: datetime | None = None


class BOMItemCreate(BOMItemBase):
    project_id: UUID
    wbs_item_id: UUID | None = None
    contract_clause_id: UUID | None = None


class BOMItemUpdate(BaseModel):
    item_code: str | None = None
    item_name: str | None = None
    description: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    total_price: float | None = None
    supplier: str | None = None
    lead_time_days: int | None = None
    required_on_site_date: datetime | None = None
    wbs_item_id: UUID | None = None
    contract_clause_id: UUID | None = None


class BOMItemResponse(BOMItemBase):
    id: UUID
    project_id: UUID
    wbs_item_id: UUID | None = None
    contract_clause_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
