"""
C2Pro - Projects Router

Endpoints para gestión de proyectos.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.security import CurrentUserId, CurrentTenantId
from src.core.exceptions import NotFoundError, ConflictError, ValidationError
from src.modules.projects.service import ProjectService
from src.modules.projects.schemas import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectStatsResponse,
    ProjectFilters,
    ProjectErrorResponse,
)
from src.modules.projects.models import ProjectStatus, ProjectType

import structlog

logger = structlog.get_logger()

# ===========================================
# ROUTER SETUP
# ===========================================

router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
    responses={
        401: {
            "description": "Unauthorized - Authentication required",
            "model": ProjectErrorResponse
        },
        404: {
            "description": "Not Found - Project doesn't exist or access denied",
            "model": ProjectErrorResponse
        }
    }
)

# ===========================================
# ENDPOINTS
# ===========================================

@router.post(
    "",
    response_model=ProjectDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new project",
    description="""
    Creates a new project for the authenticated user's organization.

    Projects always start in DRAFT status and can be moved to ACTIVE
    when ready to begin work.

    **Requirements:**
    - User must be authenticated
    - Project name is required
    - Project code must be unique within the organization (if provided)
    """,
    responses={
        201: {"description": "Project created successfully"},
        409: {"description": "Project with this code already exists"},
        422: {"description": "Validation error"}
    }
)
async def create_project(
    request: ProjectCreateRequest,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_session)
):
    """
    Crea nuevo proyecto para la organización del usuario autenticado.
    """
    try:
        project = await ProjectService.create_project(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            request=request
        )

        logger.info(
            "project_created_via_api",
            project_id=str(project.id),
            tenant_id=str(tenant_id),
            user_id=str(user_id)
        )

        return ProjectDetailResponse.model_validate(project)

    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List projects",
    description="""
    Returns a paginated list of projects for the authenticated user's organization.

    Supports filtering by:
    - Status (draft, active, completed, archived)
    - Type (construction, engineering, industrial, etc.)
    - Search query (searches in name, description, and code)
    - Coherence score range
    - Creation date range

    **Pagination:**
    - Default page size: 20
    - Maximum page size: 100
    """,
    responses={
        200: {"description": "Projects retrieved successfully"}
    }
)
async def list_projects(
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_session),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(default=None, description="Search in name, description, code"),
    status: ProjectStatus | None = Query(default=None, description="Filter by status"),
    project_type: ProjectType | None = Query(default=None, description="Filter by type"),
    min_coherence_score: int | None = Query(default=None, ge=0, le=100),
    max_coherence_score: int | None = Query(default=None, ge=0, le=100),
):
    """
    Lista proyectos con paginación y filtros.
    """
    filters = ProjectFilters(
        search=search,
        status=status,
        project_type=project_type,
        min_coherence_score=min_coherence_score,
        max_coherence_score=max_coherence_score
    )

    response = await ProjectService.list_projects(
        db=db,
        tenant_id=tenant_id,
        page=page,
        page_size=page_size,
        filters=filters
    )

    return response


@router.get(
    "/stats",
    response_model=ProjectStatsResponse,
    summary="Get project statistics",
    description="""
    Returns statistics and metrics for all projects in the organization.

    Includes:
    - Total project count
    - Breakdown by status
    - Average coherence score
    - Total alerts by severity
    """,
    responses={
        200: {"description": "Statistics retrieved successfully"}
    }
)
async def get_project_stats(
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_session)
):
    """
    Obtiene estadísticas de proyectos de la organización.
    """
    stats = await ProjectService.get_project_stats(db=db, tenant_id=tenant_id)
    return stats


@router.get(
    "/{project_id}",
    response_model=ProjectDetailResponse,
    summary="Get project details",
    description="""
    Returns detailed information about a specific project.

    Includes:
    - Basic project information
    - Financial data
    - Coherence analysis results
    - Document counts
    - Alert summaries
    """,
    responses={
        200: {"description": "Project retrieved successfully"},
        404: {"description": "Project not found or access denied"}
    }
)
async def get_project(
    project_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_session)
):
    """
    Obtiene detalles de un proyecto específico.
    """
    try:
        project = await ProjectService.get_project(
            db=db,
            project_id=project_id,
            tenant_id=tenant_id
        )

        return ProjectDetailResponse.model_validate(project)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.put(
    "/{project_id}",
    response_model=ProjectDetailResponse,
    summary="Update project",
    description="""
    Updates an existing project.

    All fields are optional - only provided fields will be updated.

    **Note:** Changing the status to ACTIVE will trigger validation
    to ensure required documents are uploaded.
    """,
    responses={
        200: {"description": "Project updated successfully"},
        404: {"description": "Project not found or access denied"},
        409: {"description": "Project code conflict"},
        422: {"description": "Validation error"}
    }
)
async def update_project(
    project_id: UUID,
    request: ProjectUpdateRequest,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_session)
):
    """
    Actualiza un proyecto existente.
    """
    try:
        project = await ProjectService.update_project(
            db=db,
            project_id=project_id,
            tenant_id=tenant_id,
            request=request
        )

        logger.info(
            "project_updated_via_api",
            project_id=str(project_id),
            tenant_id=str(tenant_id)
        )

        return ProjectDetailResponse.model_validate(project)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
    description="""
    Permanently deletes a project and all associated data.

    **Warning:** This action cannot be undone. All documents,
    analyses, and alerts associated with this project will be deleted.

    **Best Practice:** Consider archiving the project instead of deleting it.
    """,
    responses={
        204: {"description": "Project deleted successfully"},
        404: {"description": "Project not found or access denied"}
    }
)
async def delete_project(
    project_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_session)
):
    """
    Elimina un proyecto permanentemente.

    ADVERTENCIA: Esta acción no se puede deshacer.
    """
    try:
        await ProjectService.delete_project(
            db=db,
            project_id=project_id,
            tenant_id=tenant_id
        )

        logger.info(
            "project_deleted_via_api",
            project_id=str(project_id),
            tenant_id=str(tenant_id)
        )

        return None

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


# ===========================================
# STATUS MANAGEMENT
# ===========================================

@router.patch(
    "/{project_id}/status",
    response_model=ProjectDetailResponse,
    summary="Update project status",
    description="""
    Updates only the status of a project.

    This is a convenience endpoint for common status transitions:
    - DRAFT → ACTIVE (when ready to start work)
    - ACTIVE → COMPLETED (when project is finished)
    - Any status → ARCHIVED (for historical records)

    **Validations:**
    - Moving to ACTIVE requires contract document
    - Moving to COMPLETED requires all analyses to pass
    """,
    responses={
        200: {"description": "Status updated successfully"},
        404: {"description": "Project not found or access denied"},
        422: {"description": "Invalid status transition"}
    }
)
async def update_project_status(
    project_id: UUID,
    new_status: ProjectStatus,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_session)
):
    """
    Actualiza solo el estado de un proyecto.
    """
    try:
        # Obtener proyecto
        project = await ProjectService.get_project(
            db=db,
            project_id=project_id,
            tenant_id=tenant_id
        )

        # Validaciones de transición
        if new_status == ProjectStatus.ACTIVE:
            if not project.has_contract:
                raise ValidationError(
                    "Cannot activate project without contract document"
                )

        # Actualizar estado
        request = ProjectUpdateRequest(status=new_status)
        updated_project = await ProjectService.update_project(
            db=db,
            project_id=project_id,
            tenant_id=tenant_id,
            request=request
        )

        logger.info(
            "project_status_updated",
            project_id=str(project_id),
            old_status=project.status.value,
            new_status=new_status.value
        )

        return ProjectDetailResponse.model_validate(updated_project)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


# ===========================================
# HEALTH CHECK
# ===========================================

@router.get(
    "/health",
    summary="Health check",
    description="Simple health check endpoint for projects service",
    include_in_schema=False
)
async def health():
    """Health check para el servicio de proyectos."""
    return {"status": "ok", "service": "projects"}
