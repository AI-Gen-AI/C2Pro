"""
C2Pro - Projects HTTP Router

Minimal implementation for TS-E2E-SEC-TNT-001 E2E tests.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

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
