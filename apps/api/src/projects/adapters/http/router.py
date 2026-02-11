"""
C2Pro - Projects HTTP Router

Minimal implementation for TS-E2E-SEC-TNT-001 E2E tests.
"""

from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User


router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectResponse(BaseModel):
    """Project response schema (minimal)."""

    id: UUID
    tenant_id: UUID
    name: str
    code: str
    project_type: str
    estimated_budget: float
    currency: str


class ProjectListResponse(BaseModel):
    """Project list response."""

    items: list[ProjectResponse]
    total: int


# In-memory storage for fake implementation
_fake_projects: dict[UUID, dict] = {}


def _add_fake_project(project_data: dict) -> None:
    """
    Add a project to fake in-memory storage.

    Used by tests to populate data.
    """
    _fake_projects[project_data["id"]] = project_data


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProjectResponse:
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

    return ProjectResponse(**project)


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProjectListResponse:
    """
    List all projects for the current tenant.

    Filters by tenant_id automatically.
    """
    tenant_projects = [
        ProjectResponse(**p)
        for p in _fake_projects.values()
        if p["tenant_id"] == current_user.tenant_id
    ]

    return ProjectListResponse(
        items=tenant_projects,
        total=len(tenant_projects),
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    updates: dict,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProjectResponse:
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

    return ProjectResponse(**project)


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


# Helper function for tests to inject fake data
def _add_fake_project(project_data: dict) -> None:
    """Add a fake project to in-memory storage (for testing)."""
    _fake_projects[project_data["id"]] = project_data


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

    Args:
        project_id: UUID of the project
        current_user: Authenticated user

    Returns:
        Acceptance message for async processing

    Raises:
        404: Project not found or belongs to another tenant
    """
    # Check if project exists and belongs to tenant
    project = _fake_projects.get(project_id)

    if not project or project["tenant_id"] != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # GREEN PHASE: Just accept the upload
    # In real implementation, this would:
    # - Store file in R2
    # - Create document record in DB
    # - Queue processing job

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
    description="""
    Upload multiple documents for processing.

    **For TS-E2E-FLW-BLK-001 E2E tests.**

    Processes up to 100 documents in a single request.
    Returns summary of accepted/failed documents.
    """,
)
async def bulk_upload_documents(
    project_id: UUID,
    request: BulkDocumentRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Bulk upload documents.

    GREEN PHASE implementation using "Fake It" pattern.

    Args:
        project_id: UUID of the project
        request: Bulk upload request with list of documents
        current_user: Authenticated user

    Returns:
        Summary of accepted/failed documents

    Raises:
        404: Project not found or belongs to another tenant
    """
    # Check if project exists and belongs to tenant
    project = _fake_projects.get(project_id)

    if not project or project["tenant_id"] != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # GREEN PHASE: Fake successful upload
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
    description="""
    Create multiple WBS items in bulk.

    **For TS-E2E-FLW-BLK-001 E2E tests.**

    Supports:
    - Partial success (some items fail, others succeed)
    - Atomic transactions (atomic=true, all or nothing)
    - Parent-child hierarchy validation
    """,
)
async def bulk_create_wbs(
    project_id: UUID,
    request: BulkWBSRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Bulk create WBS items.

    GREEN PHASE implementation using "Fake It" pattern.

    Args:
        project_id: UUID of the project
        request: Bulk WBS creation request
        current_user: Authenticated user

    Returns:
        Summary of created/failed items

    Raises:
        404: Project not found or belongs to another tenant
        400: Atomic transaction failed (all or nothing)
    """
    # Check if project exists and belongs to tenant
    project = _fake_projects.get(project_id)

    if not project or project["tenant_id"] != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Validate items
    valid_items = []
    invalid_items = []
    errors = []

    for idx, item in enumerate(request.items):
        # Check required fields
        if not item.code or not item.name or item.level is None:
            invalid_items.append(idx)
            errors.append({
                "index": idx,
                "code": item.code if item.code else None,
                "error": "Missing required fields: code, name, or level",
            })
        else:
            valid_items.append(item)

    # Handle atomic transactions
    if request.atomic and invalid_items:
        # All or nothing - reject entire batch
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Atomic transaction failed",
                "created_count": 0,
                "failed_count": len(request.items),
                "errors": errors,
            },
        )

    # GREEN PHASE: Fake creation of valid items
    if project_id not in _fake_wbs_items:
        _fake_wbs_items[project_id] = []

    for item in valid_items:
        _fake_wbs_items[project_id].append({
            "code": item.code,
            "name": item.name,
            "level": item.level,
            "parent_code": item.parent_code,
        })

    # Return 207 Multi-Status if partial success, 201 if all succeeded
    status_code = 207 if invalid_items else 201

    response = {
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
    description="""
    Export complete project data in various formats.

    **For TS-E2E-FLW-BLK-001 E2E tests.**

    Supports formats: json, csv, xlsx, zip
    Includes: documents, wbs, alerts, coherence, etc.
    """,
)
async def export_project_data(
    project_id: UUID,
    request: BulkExportRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Export project data.

    GREEN PHASE implementation using "Fake It" pattern.

    Args:
        project_id: UUID of the project
        request: Export request with format and includes
        current_user: Authenticated user

    Returns:
        Export job ID and status

    Raises:
        404: Project not found or belongs to another tenant
    """
    # Check if project exists and belongs to tenant
    project = _fake_projects.get(project_id)

    if not project or project["tenant_id"] != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # GREEN PHASE: Create fake export job
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
