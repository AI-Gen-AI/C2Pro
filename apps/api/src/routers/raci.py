from __future__ import annotations

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.security import CurrentTenantId, CurrentUserId
from src.modules.projects.service import ProjectService
from src.modules.stakeholders.models import RACIRole, Stakeholder, StakeholderWBSRaci, WBSItem
from src.modules.stakeholders.schemas import (
    RaciAssignmentUpsertRequest,
    RaciAssignmentUpsertResponse,
    RaciMatrixAssignment,
    RaciMatrixTaskRow,
    RaciMatrixViewResponse,
)

logger = structlog.get_logger()

ROLE_LABELS = {
    RACIRole.RESPONSIBLE: "RESPONSIBLE",
    RACIRole.ACCOUNTABLE: "ACCOUNTABLE",
    RACIRole.CONSULTED: "CONSULTED",
    RACIRole.INFORMED: "INFORMED",
}

ROLE_VALUES = {
    "R": RACIRole.RESPONSIBLE,
    "A": RACIRole.ACCOUNTABLE,
    "C": RACIRole.CONSULTED,
    "I": RACIRole.INFORMED,
    "RESPONSIBLE": RACIRole.RESPONSIBLE,
    "ACCOUNTABLE": RACIRole.ACCOUNTABLE,
    "CONSULTED": RACIRole.CONSULTED,
    "INFORMED": RACIRole.INFORMED,
}

router = APIRouter(
    prefix="",
    tags=["RACI"],
    responses={404: {"description": "Not Found"}},
)


def _role_from_label(role: str) -> RACIRole:
    if not role or not role.strip():
        raise HTTPException(status_code=400, detail="role is required")
    normalized = role.strip().upper()
    raci_role = ROLE_VALUES.get(normalized)
    if raci_role is None:
        raise HTTPException(status_code=400, detail="Invalid RACI role")
    return raci_role


def _role_to_label(role: RACIRole) -> str:
    return ROLE_LABELS.get(role, role.value)


@router.get(
    "/projects/{project_id}/raci",
    response_model=RaciMatrixViewResponse,
    summary="Get RACI matrix view",
)
async def get_project_raci_matrix(
    project_id: UUID,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_session),
) -> RaciMatrixViewResponse:
    await ProjectService.get_project(db=db, project_id=project_id, tenant_id=tenant_id)

    wbs_result = await db.execute(
        select(WBSItem).where(WBSItem.project_id == project_id).order_by(WBSItem.wbs_code)
    )
    wbs_items = list(wbs_result.scalars().all())
    if not wbs_items:
        return RaciMatrixViewResponse(matrix=[])

    raci_result = await db.execute(
        select(StakeholderWBSRaci).where(StakeholderWBSRaci.project_id == project_id)
    )
    raci_rows = list(raci_result.scalars().all())

    assignments_by_task: dict[UUID, list[RaciMatrixAssignment]] = {}
    for row in raci_rows:
        assignments_by_task.setdefault(row.wbs_item_id, []).append(
            RaciMatrixAssignment(
                stakeholder_id=row.stakeholder_id,
                role=_role_to_label(row.raci_role),
                is_verified=row.is_verified,
            )
        )

    matrix = [
        RaciMatrixTaskRow(
            task_id=item.id,
            task_name=item.name,
            assignments=assignments_by_task.get(item.id, []),
        )
        for item in wbs_items
    ]

    return RaciMatrixViewResponse(matrix=matrix)


@router.put(
    "/assignments",
    response_model=RaciAssignmentUpsertResponse,
    summary="Create or update a single RACI assignment",
)
async def upsert_raci_assignment(
    payload: RaciAssignmentUpsertRequest,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_session),
) -> RaciAssignmentUpsertResponse:
    raci_role = _role_from_label(payload.role)

    wbs_item = await db.scalar(select(WBSItem).where(WBSItem.id == payload.task_id))
    if wbs_item is None:
        raise HTTPException(status_code=404, detail="Task not found")

    await ProjectService.get_project(db=db, project_id=wbs_item.project_id, tenant_id=tenant_id)

    stakeholder = await db.scalar(
        select(Stakeholder).where(Stakeholder.id == payload.stakeholder_id)
    )
    if stakeholder is None:
        raise HTTPException(status_code=404, detail="Stakeholder not found")

    if stakeholder.project_id != wbs_item.project_id:
        raise HTTPException(
            status_code=400,
            detail="Stakeholder and task must belong to the same project",
        )

    if raci_role == RACIRole.ACCOUNTABLE:
        existing_accountable = await db.scalar(
            select(StakeholderWBSRaci).where(
                StakeholderWBSRaci.wbs_item_id == wbs_item.id,
                StakeholderWBSRaci.raci_role == RACIRole.ACCOUNTABLE,
                StakeholderWBSRaci.stakeholder_id != stakeholder.id,
            )
        )
        if existing_accountable is not None:
            raise HTTPException(
                status_code=400, detail="Only one ACCOUNTABLE is allowed per task"
            )

    assignment = await db.scalar(
        select(StakeholderWBSRaci).where(
            StakeholderWBSRaci.wbs_item_id == wbs_item.id,
            StakeholderWBSRaci.stakeholder_id == stakeholder.id,
        )
    )

    if assignment is None:
        assignment = StakeholderWBSRaci(
            project_id=wbs_item.project_id,
            stakeholder_id=stakeholder.id,
            wbs_item_id=wbs_item.id,
            raci_role=raci_role,
        )
        db.add(assignment)
    else:
        assignment.raci_role = raci_role

    assignment.generated_automatically = False
    assignment.manually_verified = True
    assignment.verified_by = user_id
    assignment.verified_at = datetime.utcnow()

    await db.commit()
    await db.refresh(assignment)

    return RaciAssignmentUpsertResponse(
        task_id=wbs_item.id,
        stakeholder_id=stakeholder.id,
        role=_role_to_label(assignment.raci_role),
        is_verified=assignment.is_verified,
    )
