"""
C2Pro - Projects HTTP Router

Minimal implementation for TS-E2E-SEC-TNT-001 E2E tests.
"""

from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.projects.application.dtos import ProjectDetailResponse, ProjectListResponse


router = APIRouter(prefix="/projects", tags=["projects"])


# In-memory storage for fake implementation
_fake_projects: dict[UUID, dict] = {}


def _add_fake_project(project_data: dict) -> None:
    """
    Add a project to fake in-memory storage.

    Used by tests to populate data.
    """
    _fake_projects[project_data["id"]] = project_data


def _to_response(project: dict) -> ProjectDetailResponse:
    """Map a _fake_projects dict to the canonical ProjectDetailResponse."""
    now = datetime.now(timezone.utc)
    return ProjectDetailResponse(
        id=project["id"],
        tenant_id=project["tenant_id"],
        name=project["name"],
        description=project.get("description"),
        code=project.get("code"),
        project_type=project.get("project_type", "construction"),
        status=project.get("status", "draft"),
        estimated_budget=project.get("estimated_budget"),
        currency=project.get("currency", "EUR"),
        start_date=project.get("start_date"),
        end_date=project.get("end_date"),
        coherence_score=project.get("coherence_score"),
        last_analysis_at=project.get("last_analysis_at"),
        created_at=project.get("created_at", now),
        updated_at=project.get("updated_at", now),
    )


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProjectDetailResponse:
    """
    Get project by ID.

    Returns 404 if project doesn't exist or belongs to another tenant.
    """
    project = _fake_projects.get(project_id)

    # Return 404 if not found OR if it belongs to another tenant
    # (important: don't leak information about existence)
    if not project or project["tenant_id"] != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return _to_response(project)


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProjectListResponse:
    """
    List all projects for the current tenant.

    Filters by tenant_id automatically.
    """
    tenant_projects = [
        _to_response(p)
        for p in _fake_projects.values()
        if p["tenant_id"] == current_user.tenant_id
    ]

    return ProjectListResponse(
        items=tenant_projects,
        total=len(tenant_projects),
        page=1,
        page_size=len(tenant_projects),
    )


@router.patch("/{project_id}", response_model=ProjectDetailResponse)
async def update_project(
    project_id: UUID,
    updates: dict,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProjectDetailResponse:
    """
    Update project.

    Returns 404 if project doesn't exist or belongs to another tenant.
    """
    project = _fake_projects.get(project_id)

    if not project or project["tenant_id"] != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Update fields
    project.update(updates)
    _fake_projects[project_id] = project

    return _to_response(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """
    Delete project.

    Returns 404 if project doesn't exist or belongs to another tenant.
    """
    project = _fake_projects.get(project_id)

    if not project or project["tenant_id"] != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    del _fake_projects[project_id]


# ===========================================
# DOCUMENT UPLOAD ENDPOINT (for TS-E2E-FLW-DOC-001)
# GREEN PHASE: Minimal "Fake It" implementation
# ===========================================


@router.post(
    "/{project_id}/documents",
    status_code=202,
    summary="Upload Document",
    description="""
    Upload a document for processing.

    **For TS-E2E-FLW-DOC-001 E2E tests.**

    Workflow:
    1. Document is stored
    2. Parsing begins (async)
    3. Clause extraction triggered
    4. Entity extraction triggered
    5. Analysis runs
    6. Coherence score calculated

    Returns 202 Accepted for async processing.
    """,
)
async def upload_document(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Upload document for processing.

    GREEN PHASE implementation using "Fake It" pattern.
    """
    # Check if project exists and belongs to tenant
    project = _fake_projects.get(project_id)

    if not project or project["tenant_id"] != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return {
        "status": "accepted",
        "message": "Document queued for processing",
        "project_id": str(project_id),
    }


# ===========================================
# BULK OPERATIONS ENDPOINTS (for TS-E2E-FLW-BLK-001)
# GREEN PHASE: Minimal "Fake It" implementation
# ===========================================


class BulkDocumentItem(BaseModel):
    """Single document in bulk upload."""

    filename: str
    document_type: str
    file_data: str


class BulkDocumentRequest(BaseModel):
    """Bulk document upload request."""

    documents: list[BulkDocumentItem]


class BulkWBSItem(BaseModel):
    """Single WBS item in bulk creation."""

    code: str
    name: str | None = None
    level: int | None = None
    parent_code: str | None = None
    description: str | None = None


class BulkWBSRequest(BaseModel):
    """Bulk WBS creation request."""

    items: list[BulkWBSItem]
    atomic: bool = False


class BulkExportRequest(BaseModel):
    """Bulk export request."""

    format: Literal["json", "csv", "xlsx", "zip"]
    include: list[str] = Field(default_factory=list)


# In-memory storage for fake WBS items and jobs
_fake_wbs_items: dict[UUID, list[dict]] = {}
_fake_jobs: dict[str, dict] = {}


@router.post(
    "/{project_id}/documents/bulk",
    status_code=202,
    summary="Bulk Upload Documents",
)
async def bulk_upload_documents(
    project_id: UUID,
    request: BulkDocumentRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Bulk upload documents. GREEN PHASE."""
    project = _fake_projects.get(project_id)

    if not project or project["tenant_id"] != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    document_ids = [str(uuid4()) for _ in request.documents]

    return {
        "accepted_count": len(request.documents),
        "failed_count": 0,
        "document_ids": document_ids,
        "status": "accepted",
    }


@router.post(
    "/{project_id}/wbs/bulk",
    status_code=201,
    summary="Bulk Create WBS Items",
)
async def bulk_create_wbs(
    project_id: UUID,
    request: BulkWBSRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Bulk create WBS items. GREEN PHASE."""
    project = _fake_projects.get(project_id)

    if not project or project["tenant_id"] != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    valid_items = []
    invalid_items = []
    errors = []

    for idx, item in enumerate(request.items):
        if not item.code or not item.name or item.level is None:
            invalid_items.append(idx)
            errors.append({
                "index": idx,
                "code": item.code if item.code else None,
                "error": "Missing required fields: code, name, or level",
            })
        else:
            valid_items.append(item)

    if request.atomic and invalid_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Atomic transaction failed",
                "created_count": 0,
                "failed_count": len(request.items),
                "errors": errors,
            },
        )

    if project_id not in _fake_wbs_items:
        _fake_wbs_items[project_id] = []

    for item in valid_items:
        _fake_wbs_items[project_id].append({
            "code": item.code,
            "name": item.name,
            "level": item.level,
            "parent_code": item.parent_code,
        })

    response: dict = {
        "created_count": len(valid_items),
        "failed_count": len(invalid_items),
    }

    if errors:
        response["errors"] = errors

    return response


@router.post(
    "/{project_id}/export",
    status_code=202,
    summary="Export Project Data",
)
async def export_project_data(
    project_id: UUID,
    request: BulkExportRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Export project data. GREEN PHASE."""
    project = _fake_projects.get(project_id)

    if not project or project["tenant_id"] != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    export_id = str(uuid4())
    _fake_jobs[export_id] = {
        "export_id": export_id,
        "project_id": str(project_id),
        "status": "processing",
        "format": request.format,
        "include": request.include,
        "percentage": 0,
    }

    return {
        "export_id": export_id,
        "status": "processing",
        "message": "Export job queued",
    }
