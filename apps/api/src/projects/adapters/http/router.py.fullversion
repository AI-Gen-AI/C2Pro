"""
C2Pro - Projects HTTP Router (Hexagonal Architecture)

This router follows the hexagonal architecture pattern:
- Delegates business logic to use cases
- Uses DTOs for request/response validation
- Injects dependencies (repository, session)
- Handles HTTP-specific concerns (status codes, errors)

Endpoints:
- GET /projects - List projects with pagination and filters
- POST /projects - Create new project
- GET /projects/{id} - Get project by ID
- PUT /projects/{id} - Update project
- DELETE /projects/{id} - Delete project
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.security import CurrentTenantId, CurrentUserId

# Domain models
from src.projects.domain.models import ProjectStatus, ProjectType

# DTOs
from src.projects.application.dtos import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectDetailResponse,
    ProjectListResponse,
)

# Use cases
from src.projects.application.use_cases import (
    CreateProjectUseCase,
    GetProjectUseCase,
    ListProjectsUseCase,
    UpdateProjectUseCase,
    DeleteProjectUseCase,
)

# Repository
from src.projects.adapters.persistence.project_repository import SQLAlchemyProjectRepository


logger = structlog.get_logger()

# ===========================================
# ROUTER SETUP
# ===========================================

router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
)

# ===========================================
# DEPENDENCY INJECTION
# ===========================================

def get_project_repository(session: AsyncSession = Depends(get_session)) -> SQLAlchemyProjectRepository:
    """Dependency injection for project repository."""
    return SQLAlchemyProjectRepository(session)

# ===========================================
# ENDPOINTS
# ===========================================

@router.get("", response_model=ProjectListResponse, summary="List projects")
async def list_projects(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search in name, code, or description"),
    status: ProjectStatus | None = Query(None, description="Filter by status"),
    project_type: ProjectType | None = Query(None, description="Filter by project type"),
    tenant_id: UUID = Depends(CurrentTenantId),
    repository: SQLAlchemyProjectRepository = Depends(get_project_repository),
    session: AsyncSession = Depends(get_session),
) -> ProjectListResponse:
    """
    List projects with pagination and optional filters.

    **Filters:**
    - `search`: Search in project name, code, or description (case-insensitive)
    - `status`: Filter by project status (draft, active, completed, archived)
    - `project_type`: Filter by project type (construction, engineering, etc.)

    **Pagination:**
    - `page`: Page number (starts at 1)
    - `page_size`: Items per page (max 100)
    """
    try:
        use_case = ListProjectsUseCase(repository)
        projects, total = await use_case.execute(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            search=search,
            status=status,
            project_type=project_type,
        )

        # Commit session after read
        await session.commit()

        # Map to response DTOs
        items = [
            ProjectDetailResponse(
                id=p.id,
                tenant_id=p.tenant_id,
                name=p.name,
                description=p.description,
                code=p.code,
                project_type=p.project_type,
                status=p.status,
                estimated_budget=p.estimated_budget,
                currency=p.currency,
                start_date=p.start_date,
                end_date=p.end_date,
                coherence_score=p.coherence_score,
                last_analysis_at=p.last_analysis_at,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in projects
        ]

        return ProjectListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    except ValueError as e:
        logger.error("list_projects_validation_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("list_projects_failed", error=str(e), tenant_id=str(tenant_id))
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list projects",
        )


@router.post("", response_model=ProjectDetailResponse, status_code=status.HTTP_201_CREATED, summary="Create project")
async def create_project(
    data: ProjectCreateRequest,
    tenant_id: UUID = Depends(CurrentTenantId),
    user_id: UUID = Depends(CurrentUserId),
    repository: SQLAlchemyProjectRepository = Depends(get_project_repository),
    session: AsyncSession = Depends(get_session),
) -> ProjectDetailResponse:
    """
    Create a new project.

    **Required fields:**
    - `name`: Project name (1-255 characters)

    **Optional fields:**
    - `description`: Detailed description
    - `code`: Unique project code
    - `project_type`: Type of project (default: construction)
    - `estimated_budget`: Budget estimate
    - `currency`: Currency code (default: EUR)
    - `start_date`: Project start date
    - `end_date`: Project end date
    """
    try:
        use_case = CreateProjectUseCase(repository)
        project = await use_case.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            name=data.name,
            description=data.description,
            code=data.code,
            project_type=data.project_type,
            estimated_budget=data.estimated_budget,
            currency=data.currency,
            start_date=data.start_date,
            end_date=data.end_date,
        )

        await session.commit()

        return ProjectDetailResponse(
            id=project.id,
            tenant_id=project.tenant_id,
            name=project.name,
            description=project.description,
            code=project.code,
            project_type=project.project_type,
            status=project.status,
            estimated_budget=project.estimated_budget,
            currency=project.currency,
            start_date=project.start_date,
            end_date=project.end_date,
            coherence_score=project.coherence_score,
            last_analysis_at=project.last_analysis_at,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    except ValueError as e:
        logger.error("create_project_validation_error", error=str(e))
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT if "already exists" in str(e) else status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("create_project_failed", error=str(e), tenant_id=str(tenant_id))
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project",
        )


@router.get("/{project_id}", response_model=ProjectDetailResponse, summary="Get project")
async def get_project(
    project_id: UUID,
    tenant_id: UUID = Depends(CurrentTenantId),
    repository: SQLAlchemyProjectRepository = Depends(get_project_repository),
    session: AsyncSession = Depends(get_session),
) -> ProjectDetailResponse:
    """
    Get a project by ID.

    **Tenant isolation:**
    Only returns projects belonging to the authenticated tenant.
    """
    try:
        use_case = GetProjectUseCase(repository)
        project = await use_case.execute(project_id, tenant_id)

        await session.commit()

        return ProjectDetailResponse(
            id=project.id,
            tenant_id=project.tenant_id,
            name=project.name,
            description=project.description,
            code=project.code,
            project_type=project.project_type,
            status=project.status,
            estimated_budget=project.estimated_budget,
            currency=project.currency,
            start_date=project.start_date,
            end_date=project.end_date,
            coherence_score=project.coherence_score,
            last_analysis_at=project.last_analysis_at,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    except ValueError as e:
        logger.error("get_project_not_found", error=str(e), project_id=str(project_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error("get_project_failed", error=str(e), project_id=str(project_id))
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get project",
        )


@router.put("/{project_id}", response_model=ProjectDetailResponse, summary="Update project")
async def update_project(
    project_id: UUID,
    data: ProjectUpdateRequest,
    tenant_id: UUID = Depends(CurrentTenantId),
    user_id: UUID = Depends(CurrentUserId),
    repository: SQLAlchemyProjectRepository = Depends(get_project_repository),
    session: AsyncSession = Depends(get_session),
) -> ProjectDetailResponse:
    """
    Update a project.

    **Partial updates:**
    Only provided fields will be updated. Omitted fields remain unchanged.

    **Updatable fields:**
    - `name`: Project name
    - `description`: Description
    - `code`: Project code (must be unique)
    - `project_type`: Project type
    - `status`: Project status
    - `estimated_budget`: Budget estimate
    - `currency`: Currency code
    - `start_date`: Start date
    - `end_date`: End date
    """
    try:
        use_case = UpdateProjectUseCase(repository)
        project = await use_case.execute(
            project_id=project_id,
            tenant_id=tenant_id,
            user_id=user_id,
            name=data.name,
            description=data.description,
            code=data.code,
            project_type=data.project_type,
            status=data.status,
            estimated_budget=data.estimated_budget,
            currency=data.currency,
            start_date=data.start_date,
            end_date=data.end_date,
        )

        await session.commit()

        return ProjectDetailResponse(
            id=project.id,
            tenant_id=project.tenant_id,
            name=project.name,
            description=project.description,
            code=project.code,
            project_type=project.project_type,
            status=project.status,
            estimated_budget=project.estimated_budget,
            currency=project.currency,
            start_date=project.start_date,
            end_date=project.end_date,
            coherence_score=project.coherence_score,
            last_analysis_at=project.last_analysis_at,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    except ValueError as e:
        logger.error("update_project_error", error=str(e), project_id=str(project_id))
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "not found" in str(e) else status.HTTP_409_CONFLICT if "already exists" in str(e) else status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("update_project_failed", error=str(e), project_id=str(project_id))
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update project",
        )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete project")
async def delete_project(
    project_id: UUID,
    tenant_id: UUID = Depends(CurrentTenantId),
    user_id: UUID = Depends(CurrentUserId),
    repository: SQLAlchemyProjectRepository = Depends(get_project_repository),
    session: AsyncSession = Depends(get_session),
) -> None:
    """
    Delete a project by ID.

    **Note:**
    This permanently deletes the project and all associated data.
    Consider implementing soft deletion for production use.
    """
    try:
        use_case = DeleteProjectUseCase(repository)
        deleted = await use_case.execute(project_id, tenant_id, user_id)

        if not deleted:
            raise ValueError(f"Project {project_id} not found")

        await session.commit()

    except ValueError as e:
        logger.error("delete_project_not_found", error=str(e), project_id=str(project_id))
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error("delete_project_failed", error=str(e), project_id=str(project_id))
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete project",
        )
