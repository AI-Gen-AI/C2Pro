"""TS-P0D-REPORT-003 - Current State Report API.

The report is generated on request from authoritative domain reads. It is not
stored; ``content_fingerprint`` lets two reports be compared for sameness.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.analysis.application.project_source_evidence import read_project_source_evidence
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
from src.reporting.application.build_journey_export import (
    BuildJourneyExportUseCase,
    JourneyExportSources,
    SqlAlchemyJourneyExportSources,
)
from src.reporting.application.ports import CurrentStateSources
from src.reporting.domain.current_state_report import CurrentStateReport, ProjectIdentity

PROJECT_NOT_FOUND_DETAIL: Final[str] = "Project not found"

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


async def get_journey_export_sources(
    current_user: Annotated[User, Depends(get_current_user)],
) -> AsyncGenerator[JourneyExportSources, None]:
    async with get_session_with_tenant(current_user.tenant_id) as session:
        yield SqlAlchemyJourneyExportSources(session)


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=PROJECT_NOT_FOUND_DETAIL)

    response.headers["Cache-Control"] = "no-store"
    identity = ProjectIdentity(
        id=project.id,
        name=project.name,
        code=project.code,
        status=getattr(project.status, "value", project.status),
    )
    return await BuildCurrentStateReportUseCase(sources).execute(identity, tenant_id)




@router.get(
    "/{project_id}/reports/source-evidence",
    summary="Get original budget and schedule observations for an owned project",
    responses={
        404: {"description": "Project not found or not in caller tenant"},
        503: {"description": "Original source evidence is not available"},
    },
)
async def get_project_source_evidence(
    project_id: UUID,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    projects: Annotated[ProjectRepository, Depends(get_project_repository)],
) -> dict[str, object]:
    """Return canonical XLSX observations, never procurement-BOM authority.

    No source SQL runs unless project ownership is proven. A missing migration
    is UNAVAILABLE (503), not an invented zero budget or empty schedule.
    """
    tenant_id = require_tenant_id(current_user.tenant_id)
    project = await projects.get_by_id(project_id, tenant_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=PROJECT_NOT_FOUND_DETAIL)

    response.headers["Cache-Control"] = "no-store"
    try:
        evidence = await read_project_source_evidence(
            tenant_id=tenant_id, project_id=project_id,
        )
    except Exception:
        # Do not return SQL traces, table names, credentials or foreign-tenant IDs.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Original source observations are not available for this project",
        ) from None

    return evidence


@router.get(
    "/{project_id}/reports/journey.xlsx",
    summary="Get Journey V1 Excel Export Report",
    response_class=Response,
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}
            },
            "description": "Excel workbook with Summary, Findings, and Gaps & References sheets",
        },
        404: {"description": "Project not found or belongs to another tenant"},
    },
)
async def get_journey_excel_report(
    project_id: UUID,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    projects: Annotated[ProjectRepository, Depends(get_project_repository)],
    sources: Annotated[JourneyExportSources, Depends(get_journey_export_sources)],
) -> Response:
    """Return Journey V1 Excel spreadsheet (journey.xlsx).

    Multi-tenant isolation: project belonging to another tenant returns 404.
    Values are derived exclusively from read models.
    """
    tenant_id = require_tenant_id(current_user.tenant_id)
    project = await projects.get_by_id(project_id, tenant_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=PROJECT_NOT_FOUND_DETAIL)

    response.headers["Cache-Control"] = "no-store"
    use_case = BuildJourneyExportUseCase(sources=sources)
    excel_bytes = await use_case.execute(project_id=project_id, tenant_id=tenant_id)

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="journey-{project_id}.xlsx"',
            "Cache-Control": "no-store",
        },
    )


__all__ = [
    "get_current_state_report",
    "get_current_state_sources",
    "get_journey_excel_report",
    "get_journey_export_sources",
    "get_project_repository",
    "get_project_source_evidence",
    "router",
]
