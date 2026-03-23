"""
HTTP adapter (FastAPI router) for RACI endpoints.
"""
from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.repositories import (
    get_project_repository as get_core_project_repository,
    get_wbs_repository as get_core_wbs_repository,
)
from src.core.security import CurrentTenantId, CurrentUserId
from src.procurement.ports.wbs_repository import IWBSRepository
from src.projects.ports.project_repository import ProjectRepository
from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)
from src.stakeholders.application.dtos import (
    RaciAssignmentUpsertRequest,
    RaciAssignmentUpsertResponse,
    RaciMatrixViewResponse,
)
from src.stakeholders.application.get_raci_matrix_use_case import GetRaciMatrixUseCase
from src.stakeholders.application.upsert_raci_assignment_use_case import (
    UpsertRaciAssignmentUseCase,
)

logger = structlog.get_logger()

router = APIRouter(
    prefix="",
    tags=["RACI"],
    responses={404: {"description": "Not Found"}},
)

# Global RACI router — mounted before project-scoped router to avoid route conflicts
raci_global_router = APIRouter(
    prefix="",
    tags=["RACI"],
    responses={404: {"description": "Not Found"}},
)

router.include_router(raci_global_router)

def get_stakeholder_repository(
    db: AsyncSession = Depends(get_session),
) -> SqlAlchemyStakeholderRepository:
    return SqlAlchemyStakeholderRepository(session=db)

def get_wbs_repository(
    repository: IWBSRepository = Depends(get_core_wbs_repository),
) -> IWBSRepository:
    return repository

def get_project_repository(
    repository: ProjectRepository = Depends(get_core_project_repository),
) -> ProjectRepository:
    return repository

def get_matrix_use_case(
    stakeholder_repo: SqlAlchemyStakeholderRepository = Depends(get_stakeholder_repository),
    wbs_repo: IWBSRepository = Depends(get_wbs_repository),
    project_repo: ProjectRepository = Depends(get_project_repository),
) -> GetRaciMatrixUseCase:
    return GetRaciMatrixUseCase(
        stakeholder_repository=stakeholder_repo,
        wbs_repository=wbs_repo,
        project_repository=project_repo,
    )

def get_upsert_use_case(
    stakeholder_repo: SqlAlchemyStakeholderRepository = Depends(get_stakeholder_repository),
    wbs_repo: IWBSRepository = Depends(get_wbs_repository),
) -> UpsertRaciAssignmentUseCase:
    return UpsertRaciAssignmentUseCase(
        stakeholder_repository=stakeholder_repo,
        wbs_repository=wbs_repo,
    )


@raci_global_router.get(
    "/raci",
    response_model=RaciMatrixViewResponse,
    summary="Get global RACI matrix across all projects",
)
async def get_global_raci_matrix(
    tenant_id: CurrentTenantId,
    _user_id: CurrentUserId,
    use_case: GetRaciMatrixUseCase = Depends(get_matrix_use_case),
    project_repo: ProjectRepository = Depends(get_project_repository),
) -> RaciMatrixViewResponse:
    from src.stakeholders.application.dtos import RaciMatrixTaskRow
    all_projects = await project_repo.list(tenant_id=tenant_id)
    all_rows: list[RaciMatrixTaskRow] = []
    for project in all_projects:
        try:
            matrix = await use_case.execute(project_id=project.id, tenant_id=tenant_id)
            for row in matrix.matrix:
                all_rows.append(row)
        except ValueError:
            continue
    return RaciMatrixViewResponse(matrix=all_rows)


@router.get(
    "/projects/{project_id}/raci",
    response_model=RaciMatrixViewResponse,
    summary="Get RACI matrix view",
)
async def get_project_raci_matrix(
    project_id: UUID,
    tenant_id: CurrentTenantId,
    _user_id: CurrentUserId,
    use_case: GetRaciMatrixUseCase = Depends(get_matrix_use_case),
) -> RaciMatrixViewResponse:
    try:
        return await use_case.execute(project_id=project_id, tenant_id=tenant_id)
    except ValueError as exc:
        if str(exc) == "project_not_found":
            raise HTTPException(status_code=404, detail="Project not found")
        raise


@router.put(
    "/assignments",
    response_model=RaciAssignmentUpsertResponse,
    summary="Create or update a single RACI assignment",
)
async def upsert_raci_assignment(
    payload: RaciAssignmentUpsertRequest,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    use_case: UpsertRaciAssignmentUseCase = Depends(get_upsert_use_case),
) -> RaciAssignmentUpsertResponse:
    try:
        return await use_case.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            payload=payload,
        )
    except ValueError as exc:
        reason = str(exc)
        if reason == "task_not_found":
            raise HTTPException(status_code=404, detail="Task not found")
        if reason == "stakeholder_not_found":
            raise HTTPException(status_code=404, detail="Stakeholder not found")
        if reason == "stakeholder_project_mismatch":
            raise HTTPException(
                status_code=400,
                detail="Stakeholder and task must belong to the same project",
            )
        if reason == "accountable_exists":
            raise HTTPException(
                status_code=400, detail="Only one ACCOUNTABLE is allowed per task"
            )
        if reason == "role_required":
            raise HTTPException(status_code=400, detail="role is required")
        if reason == "invalid_role":
            raise HTTPException(status_code=400, detail="Invalid RACI role")
        raise
