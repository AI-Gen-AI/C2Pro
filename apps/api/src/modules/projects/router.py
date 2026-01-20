"""
C2Pro - Projects Router

Endpoints para gestión de proyectos.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.exceptions import ConflictError, NotFoundError, ValidationError
from src.core.security import CurrentTenantId, CurrentUserId
from src.core.validation import sanitize_search_query
from src.modules.coherence.service import CoherenceService, get_coherence_service
from src.modules.documents.models import Document
from src.modules.projects.models import ProjectStatus, ProjectType
from src.modules.projects.schemas import (
    CoherenceScoreResponse,
    DocumentListResponse,
    DocumentPollingStatus,
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectErrorResponse,
    ProjectFilters,
    ProjectListResponse,
    ProjectStatsResponse,
    ProjectUpdateRequest,
)
from src.modules.projects.service import ProjectService

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
            "model": ProjectErrorResponse,
        },
        404: {
            "description": "Not Found - Project doesn't exist or access denied",
            "model": ProjectErrorResponse,
        },
    },
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
        422: {"description": "Validation error"},
    },
)
async def create_project(
    request: ProjectCreateRequest,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_session),
):
    """
    Crea nuevo proyecto para la organización del usuario autenticado.
    """
    try:
        project = await ProjectService.create_project(
            db=db, tenant_id=tenant_id, user_id=user_id, request=request
        )

        logger.info(
            "project_created_via_api",
            project_id=str(project.id),
            tenant_id=str(tenant_id),
            user_id=str(user_id),
        )

        return ProjectDetailResponse.model_validate(project)

    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


async def _list_projects_impl(
    tenant_id: CurrentTenantId,
    db: AsyncSession,
    page: int,
    page_size: int,
    search: str | None,
    status: ProjectStatus | None,
    project_type: ProjectType | None,
    min_coherence_score: int | None,
    max_coherence_score: int | None,
):
    """
    Implementación compartida para list_projects.
    """
    # Sanitizar búsqueda para prevenir SQL injection
    sanitized_search = sanitize_search_query(search) if search else None

    filters = ProjectFilters(
        search=sanitized_search,
        status=status,
        project_type=project_type,
        min_coherence_score=min_coherence_score,
        max_coherence_score=max_coherence_score,
    )

    response = await ProjectService.list_projects(
        db=db, tenant_id=tenant_id, page=page, page_size=page_size, filters=filters
    )

    return response


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
    responses={200: {"description": "Projects retrieved successfully"}},
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
    return await _list_projects_impl(
        tenant_id,
        db,
        page,
        page_size,
        search,
        status,
        project_type,
        min_coherence_score,
        max_coherence_score,
    )


@router.get(
    "/",
    response_model=ProjectListResponse,
    summary="List projects (with trailing slash)",
    description="Same as GET /projects but accepts trailing slash.",
    responses={200: {"description": "Projects retrieved successfully"}},
    include_in_schema=False,  # Hide from docs to avoid duplication
)
async def list_projects_slash(
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
    Lista proyectos con paginación y filtros (con trailing slash).
    """
    return await _list_projects_impl(
        tenant_id,
        db,
        page,
        page_size,
        search,
        status,
        project_type,
        min_coherence_score,
        max_coherence_score,
    )


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
    responses={200: {"description": "Statistics retrieved successfully"}},
)
async def get_project_stats(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_session)):
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
        404: {"description": "Project not found or access denied"},
    },
)
async def get_project(
    project_id: UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_session)
):
    """
    Obtiene detalles de un proyecto específico.
    """
    try:
        project = await ProjectService.get_project(
            db=db, project_id=project_id, tenant_id=tenant_id
        )

        return ProjectDetailResponse.model_validate(project)

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/{project_id}/documents",
    response_model=list[DocumentListResponse],
    summary="List documents for a project",
    description="""
    Retrieves a paginated list of all documents associated with a specific project.
    The list is ordered by creation date, with the most recent documents first.
    This endpoint is designed for polling document statuses after an async upload.
    """,
    tags=["Projects", "Documents"],
)
async def list_project_documents(
    project_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_session),
    skip: int = Query(0, ge=0, description="Number of documents to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of documents to return"),
):
    """
    Lists all documents for a given project, ensuring the user has access
    via their tenant and providing pagination.
    """
    def _normalize_status(status: object) -> DocumentPollingStatus:
        raw_value = status.value if hasattr(status, "value") else str(status or "").lower()
        raw_value = raw_value.lower()
        if raw_value in {"queued", "uploaded"}:
            return DocumentPollingStatus.QUEUED
        if raw_value in {"processing", "parsing"}:
            return DocumentPollingStatus.PROCESSING
        if raw_value == "parsed":
            return DocumentPollingStatus.PARSED
        if raw_value == "error":
            return DocumentPollingStatus.ERROR
        return DocumentPollingStatus.PROCESSING

    # 1. Security Check: Verify project exists and belongs to the user's tenant.
    try:
        await ProjectService.get_project(db=db, project_id=project_id, tenant_id=tenant_id)
    except NotFoundError:
        # Raise 404 if project doesn't exist or doesn't belong to the tenant.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # 2. Query Documents: Fetch the paginated list of documents.
    from sqlalchemy import func, select
    query = (
        select(
            Document.id,
            Document.filename,
            Document.upload_status,
            Document.parsing_error,
            Document.created_at,
            func.coalesce(Document.file_size_bytes, 0).label("file_size_bytes"),
        )
        .where(Document.project_id == project_id)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    rows = result.all()

    response_items: list[DocumentListResponse] = []
    for row in rows:
        normalized_status = _normalize_status(row.upload_status)
        response_items.append(
            DocumentListResponse(
                id=row.id,
                filename=row.filename,
                status=normalized_status,
                error_message=row.parsing_error
                if normalized_status == DocumentPollingStatus.ERROR
                else None,
                uploaded_at=row.created_at,
                file_size_bytes=row.file_size_bytes,
            )
        )
    return response_items


@router.get(
    "/{project_id}/coherence-score",
    response_model=CoherenceScoreResponse,
    summary="Get project coherence score and breakdown",
    description="""
    Returns the current coherence score for a project. This score reflects
    the consistency and completeness of the project's data across all linked
    documents and artifacts.

    - A **score** from 0-100 indicates the calculated coherence.
    - A **PENDING** status means the score is currently being calculated.
    - A **NOT_FOUND** status means the project exists but has no data to score.
    """,
    tags=["Projects", "Coherence"],
    responses={
        200: {"description": "Coherence score retrieved successfully."},
        404: {"description": "The project with this ID was not found."},
    },
)
async def get_project_coherence_score(
    project_id: UUID,
    coherence_service: CoherenceService = Depends(get_coherence_service),
):
    """
    Retrieves the latest coherence score for a specific project.

    This endpoint is designed to be consumed by UI widgets. It handles cases where
    a score has not yet been calculated by returning a 'PENDING' status, allowing
    the frontend to display an appropriate message.
    """
    # 1. Check if the project exists at all.
    if not coherence_service.project_exists(project_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    # 2. Try to get the latest score.
    score_data = coherence_service.get_latest_score_for_project(project_id)

    # 3. Handle the case where the project exists but has no score yet.
    if score_data is None:
        return CoherenceScoreResponse(
            project_id=project_id,
            score=None,
            status="PENDING",
            calculated_at=None,
            breakdown={"critical": 0, "high": 0, "medium": 0, "low": 0},
            top_drivers=[]
        )

    # 4. Handle the case where a score was found.
    return CoherenceScoreResponse(
        project_id=project_id,
        score=score_data.score,
        status="CALCULATED",
        calculated_at=score_data.calculated_at,
        breakdown=score_data.breakdown,
        top_drivers=score_data.top_drivers,
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
        422: {"description": "Validation error"},
    },
)
async def update_project(
    project_id: UUID,
    request: ProjectUpdateRequest,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_session),
):
    """
    Actualiza un proyecto existente.
    """
    try:
        project = await ProjectService.update_project(
            db=db, project_id=project_id, tenant_id=tenant_id, request=request
        )

        logger.info("project_updated_via_api", project_id=str(project_id), tenant_id=str(tenant_id))

        return ProjectDetailResponse.model_validate(project)

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.patch(
    "/{project_id}",
    response_model=ProjectDetailResponse,
    summary="Partially update project",
    description="""
    Partially updates an existing project. Only provided fields will be updated.
    This is the preferred method for partial modifications.
    """,
    responses={
        200: {"description": "Project updated successfully"},
        404: {"description": "Project not found or access denied"},
        409: {"description": "Project code conflict"},
        422: {"description": "Validation error"},
    },
)
async def patch_project(
    project_id: UUID,
    request: ProjectUpdateRequest,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_session),
):
    """
    Partially updates an existing project.
    """
    try:
        # The service's update_project method is designed to handle partial updates,
        # as it only modifies the fields present in the request model.
        project = await ProjectService.update_project(
            db=db, project_id=project_id, tenant_id=tenant_id, request=request
        )

        logger.info("project_patched_via_api", project_id=str(project_id), tenant_id=str(tenant_id))

        return ProjectDetailResponse.model_validate(project)

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


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
        404: {"description": "Project not found or access denied"},
    },
)
async def delete_project(
    project_id: UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_session)
):
    """
    Elimina un proyecto permanentemente.

    ADVERTENCIA: Esta acción no se puede deshacer.
    """
    try:
        await ProjectService.delete_project(db=db, project_id=project_id, tenant_id=tenant_id)

        logger.info("project_deleted_via_api", project_id=str(project_id), tenant_id=str(tenant_id))

        return None

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


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
        422: {"description": "Invalid status transition"},
    },
)
async def update_project_status(
    project_id: UUID,
    new_status: ProjectStatus,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_session),
):
    """
    Actualiza solo el estado de un proyecto.
    """
    try:
        # Obtener proyecto
        project = await ProjectService.get_project(
            db=db, project_id=project_id, tenant_id=tenant_id
        )

        # Validaciones de transición
        if new_status == ProjectStatus.ACTIVE:
            if not project.has_contract:
                raise ValidationError("Cannot activate project without contract document")

        # Actualizar estado
        request = ProjectUpdateRequest(status=new_status)
        updated_project = await ProjectService.update_project(
            db=db, project_id=project_id, tenant_id=tenant_id, request=request
        )

        logger.info(
            "project_status_updated",
            project_id=str(project_id),
            old_status=project.status.value,
            new_status=new_status.value,
        )

        return ProjectDetailResponse.model_validate(updated_project)

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


# ===========================================
# HEALTH CHECK
# ===========================================


@router.get(
    "/health",
    summary="Health check",
    description="Simple health check endpoint for projects service",
    include_in_schema=False,
)
async def health():
    """Health check para el servicio de proyectos."""
    return {"status": "ok", "service": "projects"}
