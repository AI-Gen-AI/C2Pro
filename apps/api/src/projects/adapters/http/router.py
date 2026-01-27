"""
C2Pro - Projects Router

TRANSITIONAL IMPLEMENTATION:
This router currently uses ORM directly instead of use cases.
TODO: Refactor to use proper application/use_cases/ when implemented.

Endpoints:
- GET /projects - List projects with pagination and filters
- POST /projects - Create new project
- GET /projects/{id} - Get project by ID
- PUT /projects/{id} - Update project
"""

from uuid import UUID, uuid4
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.exceptions import NotFoundError, ConflictError
from src.core.security import CurrentTenantId, CurrentUserId
from src.projects.adapters.persistence.models import ProjectORM

logger = structlog.get_logger()

# ===========================================
# ROUTER SETUP
# ===========================================

router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
)

# ===========================================
# TRANSITIONAL DTOs (inline until proper DTOs are imported)
# ===========================================

from pydantic import BaseModel, Field

class ProjectCreateDTO(BaseModel):
    """DTO for creating a project."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    code: str | None = None
    project_type: str = "construction"
    estimated_budget: float | None = None
    currency: str = "EUR"
    start_date: datetime | None = None
    end_date: datetime | None = None

class ProjectUpdateDTO(BaseModel):
    """DTO for updating a project."""
    name: str | None = None
    description: str | None = None
    code: str | None = None
    project_type: str | None = None
    status: str | None = None
    estimated_budget: float | None = None
    currency: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None

class ProjectResponseDTO(BaseModel):
    """DTO for project response."""
    id: UUID
    tenant_id: UUID
    name: str | None
    created_at: datetime | None
    updated_at: datetime | None

    class Config:
        from_attributes = True

class PaginatedProjectsDTO(BaseModel):
    """DTO for paginated projects list."""
    items: list[ProjectResponseDTO]
    total: int
    page: int
    page_size: int
    total_pages: int

# ===========================================
# ENDPOINTS
# ===========================================

@router.get("", response_model=PaginatedProjectsDTO, summary="List projects")
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    search: str | None = Query(None),
    tenant_id: UUID = Depends(CurrentTenantId),
    db: AsyncSession = Depends(get_session),
) -> PaginatedProjectsDTO:
    """
    List projects with pagination and optional filters.

    **Filters:**
    - `status`: Filter by project status
    - `search`: Search in project name (case-insensitive)
    """
    try:
        # Build base query
        query = select(ProjectORM).where(ProjectORM.tenant_id == tenant_id)

        # Apply filters
        if search:
            query = query.where(ProjectORM.name.ilike(f"%{search}%"))

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Execute
        result = await db.execute(query)
        projects = result.scalars().all()

        # Calculate total pages
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        logger.info(
            "projects_listed",
            tenant_id=str(tenant_id),
            total=total,
            page=page,
            page_size=page_size,
        )

        return PaginatedProjectsDTO(
            items=[ProjectResponseDTO.model_validate(p) for p in projects],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error("list_projects_failed", error=str(e), tenant_id=str(tenant_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list projects"
        )


@router.post("", response_model=ProjectResponseDTO, status_code=status.HTTP_201_CREATED, summary="Create project")
async def create_project(
    data: ProjectCreateDTO,
    tenant_id: UUID = Depends(CurrentTenantId),
    user_id: UUID = Depends(CurrentUserId),
    db: AsyncSession = Depends(get_session),
) -> ProjectResponseDTO:
    """
    Create a new project.

    **Required fields:**
    - `name`: Project name
    """
    try:
        # Check for duplicate code if provided
        if data.code:
            existing = await db.execute(
                select(ProjectORM).where(
                    ProjectORM.tenant_id == tenant_id,
                    ProjectORM.code == data.code
                )
            )
            if existing.scalar_one_or_none():
                raise ConflictError(f"Project with code '{data.code}' already exists")

        # Create project
        project = ProjectORM(
            id=uuid4(),
            tenant_id=tenant_id,
            name=data.name,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.add(project)
        await db.commit()
        await db.refresh(project)

        logger.info(
            "project_created",
            project_id=str(project.id),
            tenant_id=str(tenant_id),
            user_id=str(user_id),
        )

        return ProjectResponseDTO.model_validate(project)

    except ConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with code '{data.code}' already exists"
        )
    except Exception as e:
        logger.error("create_project_failed", error=str(e), tenant_id=str(tenant_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project"
        )


@router.get("/{project_id}", response_model=ProjectResponseDTO, summary="Get project")
async def get_project(
    project_id: UUID,
    tenant_id: UUID = Depends(CurrentTenantId),
    db: AsyncSession = Depends(get_session),
) -> ProjectResponseDTO:
    """
    Get a project by ID.

    **Tenant isolation:**
    Only returns projects belonging to the authenticated tenant.
    """
    try:
        result = await db.execute(
            select(ProjectORM).where(
                ProjectORM.id == project_id,
                ProjectORM.tenant_id == tenant_id,
            )
        )
        project = result.scalar_one_or_none()

        if not project:
            raise NotFoundError(f"Project {project_id} not found")

        logger.info(
            "project_retrieved",
            project_id=str(project_id),
            tenant_id=str(tenant_id),
        )

        return ProjectResponseDTO.model_validate(project)

    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found"
        )
    except Exception as e:
        logger.error("get_project_failed", error=str(e), project_id=str(project_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get project"
        )


@router.put("/{project_id}", response_model=ProjectResponseDTO, summary="Update project")
async def update_project(
    project_id: UUID,
    data: ProjectUpdateDTO,
    tenant_id: UUID = Depends(CurrentTenantId),
    user_id: UUID = Depends(CurrentUserId),
    db: AsyncSession = Depends(get_session),
) -> ProjectResponseDTO:
    """
    Update a project.

    **Partial updates:**
    Only provided fields will be updated.
    """
    try:
        # Get existing project
        result = await db.execute(
            select(ProjectORM).where(
                ProjectORM.id == project_id,
                ProjectORM.tenant_id == tenant_id,
            )
        )
        project = result.scalar_one_or_none()

        if not project:
            raise NotFoundError(f"Project {project_id} not found")

        # Check for duplicate code if updating
        if data.code and data.code != project.code:
            existing = await db.execute(
                select(ProjectORM).where(
                    ProjectORM.tenant_id == tenant_id,
                    ProjectORM.code == data.code,
                    ProjectORM.id != project_id,
                )
            )
            if existing.scalar_one_or_none():
                raise ConflictError(f"Project with code '{data.code}' already exists")

        # Update fields
        if data.name is not None:
            project.name = data.name
        project.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(project)

        logger.info(
            "project_updated",
            project_id=str(project_id),
            tenant_id=str(tenant_id),
            user_id=str(user_id),
        )

        return ProjectResponseDTO.model_validate(project)

    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found"
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error("update_project_failed", error=str(e), project_id=str(project_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update project"
        )
