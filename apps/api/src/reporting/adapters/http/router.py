"""TS-P0D-REPORT-003 - Current State Report API.

The report is generated on request from authoritative domain reads. It is not
stored; ``content_fingerprint`` lets two reports be compared for sameness.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_session_with_tenant
from src.core.tenants.types import require_tenant_id
from src.projects.adapters.persistence.project_repository import SQLAlchemyProjectRepository
from src.projects.ports.project_repository import ProjectRepository
from src.reporting.adapters.sources.sqlalchemy_current_state_sources import (
    SqlAlchemyCurrentStateSources,
)
from src.reporting.application.build_current_state_report import BuildCurrentStateReportUseCase
from src.reporting.application.ports import CurrentStateSources
from src.reporting.domain.current_state_report import CurrentStateReport, ProjectIdentity

router = APIRouter(prefix="/projects", tags=["project-reports"])


async def get_project_repository(
    current_user: Annotated[User, Depends(get_current_user)],
) -> AsyncGenerator[ProjectRepository, None]:
    async with get_session_with_tenant(current_user.tenant_id) as session:
        yield SQLAlchemyProjectRepository(session)


def get_current_state_sources(
    current_user: Annotated[User, Depends(get_current_user)],
) -> CurrentStateSources:
    return SqlAlchemyCurrentStateSources(current_user=current_user)


@router.get(
    "/{project_id}/reports/current-state",
    response_model=CurrentStateReport,
    summary="Get the current state report for a project",
    responses={
        404: {
            "description": (
                "Project not found, or it belongs to another tenant. The two are "
                "deliberately indistinguishable."
            )
        }
    },
)
async def get_current_state_report(
    project_id: UUID,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    projects: Annotated[ProjectRepository, Depends(get_project_repository)],
    sources: Annotated[CurrentStateSources, Depends(get_current_state_sources)],
) -> CurrentStateReport:
    """Project the current state of a project the caller owns.

    No domain source is read until project ownership is confirmed, so a foreign
    or unknown project id costs nothing and reveals nothing.
    """

    tenant_id = require_tenant_id(current_user.tenant_id)
    project = await projects.get_by_id(project_id, tenant_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    response.headers["Cache-Control"] = "no-store"
    identity = ProjectIdentity(
        id=project.id,
        name=project.name,
        code=project.code,
        status=getattr(project.status, "value", project.status),
    )
    return await BuildCurrentStateReportUseCase(sources).execute(identity, tenant_id)


__all__ = ["get_current_state_report", "get_current_state_sources", "get_project_repository", "router"]
