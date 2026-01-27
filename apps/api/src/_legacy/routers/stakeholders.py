from __future__ import annotations

# LEGACY: replaced by src.stakeholders.adapters.http.router; kept for reference during migration.

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.approval import ApprovalStatus
from src.core.database import get_session
from src.core.security import CurrentTenantId, CurrentUserId
from src.modules.documents.models import Clause
from src.modules.projects.service import ProjectService
from src.modules.stakeholders.models import (
    InterestLevel,
    PowerLevel,
    Stakeholder,
    StakeholderQuadrant,
)
from src.modules.stakeholders.schemas import (
    StakeholderCreateRequest,
    StakeholderResponseOut,
    StakeholderUpdateRequest,
)

logger = structlog.get_logger()

router = APIRouter(
    prefix="/stakeholders",
    tags=["Stakeholders"],
    responses={404: {"description": "Not Found"}},
)


@router.get(
    "/projects/{project_id}",
    response_model=list[StakeholderResponseOut],
    summary="List stakeholders for a project",
)
async def list_project_stakeholders(
    project_id: UUID,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    quadrant: StakeholderQuadrant | None = None,
    db: AsyncSession = Depends(get_session),
) -> list[StakeholderResponseOut]:
    await ProjectService.get_project(db=db, project_id=project_id, tenant_id=tenant_id)

    query = select(Stakeholder).where(Stakeholder.project_id == project_id)
    if quadrant:
        query = query.where(Stakeholder.quadrant == quadrant)

    result = await db.execute(query)
    stakeholders = list(result.scalars().all())
    return [_to_response(stakeholder) for stakeholder in stakeholders]


@router.post(
    "/projects/{project_id}",
    response_model=StakeholderResponseOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create stakeholder manually",
)
async def create_project_stakeholder(
    project_id: UUID,
    payload: StakeholderCreateRequest,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_session),
) -> StakeholderResponseOut:
    await ProjectService.get_project(db=db, project_id=project_id, tenant_id=tenant_id)

    if payload.stakeholder_metadata is not None and not isinstance(
        payload.stakeholder_metadata, dict
    ):
        raise HTTPException(status_code=400, detail="stakeholder_metadata must be a dict")

    if payload.source_clause_id:
        clause = await db.scalar(select(Clause).where(Clause.id == payload.source_clause_id))
        if clause is None:
            raise HTTPException(status_code=400, detail="source_clause_id not found")

    metadata = dict(payload.stakeholder_metadata or {})
    if payload.type:
        metadata["type"] = payload.type

    power_score = payload.power_score
    interest_score = payload.interest_score
    power_level, interest_level, quadrant = _derive_levels_and_quadrant(
        power_score, interest_score
    )

    if power_score is not None:
        metadata["power_score"] = power_score
    if interest_score is not None:
        metadata["interest_score"] = interest_score

    stakeholder = Stakeholder(
        project_id=project_id,
        name=payload.name,
        role=payload.role,
        organization=payload.company,
        email=payload.email,
        phone=payload.phone,
        department=payload.department,
        source_clause_id=payload.source_clause_id,
        power_level=power_level,
        interest_level=interest_level,
        quadrant=quadrant,
        stakeholder_metadata=metadata,
        approval_status=ApprovalStatus.APPROVED,
        reviewed_by=user_id,
        reviewed_at=datetime.utcnow(),
        review_comment=payload.feedback_comment,
    )
    db.add(stakeholder)
    await db.commit()
    await db.refresh(stakeholder)

    logger.info(
        "stakeholder_created",
        project_id=str(project_id),
        stakeholder_id=str(stakeholder.id),
        user_id=str(user_id),
    )
    return _to_response(stakeholder)


@router.patch(
    "/{stakeholder_id}",
    response_model=StakeholderResponseOut,
    summary="Update stakeholder",
)
async def update_stakeholder(
    stakeholder_id: UUID,
    payload: StakeholderUpdateRequest,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_session),
) -> StakeholderResponseOut:
    if payload.stakeholder_metadata is not None and not isinstance(
        payload.stakeholder_metadata, dict
    ):
        raise HTTPException(status_code=400, detail="stakeholder_metadata must be a dict")

    stakeholder = await db.scalar(select(Stakeholder).where(Stakeholder.id == stakeholder_id))
    if stakeholder is None:
        raise HTTPException(status_code=404, detail="Stakeholder not found")

    if payload.source_clause_id:
        clause = await db.scalar(select(Clause).where(Clause.id == payload.source_clause_id))
        if clause is None:
            raise HTTPException(status_code=400, detail="source_clause_id not found")

    if payload.name is not None:
        stakeholder.name = payload.name
    if payload.role is not None:
        stakeholder.role = payload.role
    if payload.company is not None:
        stakeholder.organization = payload.company
    if payload.department is not None:
        stakeholder.department = payload.department
    if payload.email is not None:
        stakeholder.email = payload.email
    if payload.phone is not None:
        stakeholder.phone = payload.phone
    if payload.source_clause_id is not None:
        stakeholder.source_clause_id = payload.source_clause_id

    metadata = dict(stakeholder.stakeholder_metadata or {})
    if payload.stakeholder_metadata is not None:
        metadata.update(payload.stakeholder_metadata)
    if payload.type is not None:
        metadata["type"] = payload.type

    power_score = payload.power_score
    interest_score = payload.interest_score
    if power_score is not None:
        metadata["power_score"] = power_score
    if interest_score is not None:
        metadata["interest_score"] = interest_score

    if power_score is not None or interest_score is not None:
        current_power = power_score if power_score is not None else _score_from_metadata(
            metadata, "power_score", stakeholder.power_level
        )
        current_interest = (
            interest_score
            if interest_score is not None
            else _score_from_metadata(metadata, "interest_score", stakeholder.interest_level)
        )
        power_level, interest_level, quadrant = _derive_levels_and_quadrant(
            current_power, current_interest
        )
        stakeholder.power_level = power_level
        stakeholder.interest_level = interest_level
        stakeholder.quadrant = quadrant

    stakeholder.stakeholder_metadata = metadata

    if payload.feedback_comment is not None:
        stakeholder.review_comment = payload.feedback_comment
        stakeholder.reviewed_by = user_id
        stakeholder.reviewed_at = datetime.utcnow()
        stakeholder.approval_status = ApprovalStatus.CORRECTED

    await db.commit()
    await db.refresh(stakeholder)
    return _to_response(stakeholder)


@router.delete(
    "/{stakeholder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete stakeholder",
)
async def delete_stakeholder(
    stakeholder_id: UUID,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_session),
) -> None:
    stakeholder = await db.scalar(select(Stakeholder).where(Stakeholder.id == stakeholder_id))
    if stakeholder is None:
        raise HTTPException(status_code=404, detail="Stakeholder not found")

    await db.delete(stakeholder)
    await db.commit()
    return None


def _score_from_metadata(metadata: dict[str, Any], key: str, level: PowerLevel | InterestLevel) -> int:
    value = metadata.get(key)
    if isinstance(value, int):
        return max(1, min(value, 10))
    if level == PowerLevel.HIGH or level == InterestLevel.HIGH:
        return 9
    if level == PowerLevel.LOW or level == InterestLevel.LOW:
        return 2
    return 5


def _derive_levels_and_quadrant(
    power_score: int | None,
    interest_score: int | None,
) -> tuple[PowerLevel, InterestLevel, StakeholderQuadrant | None]:
    power_level = _score_to_power_level(power_score)
    interest_level = _score_to_interest_level(interest_score)
    if power_score is None and interest_score is None:
        return power_level, interest_level, None
    quadrant = _quadrant_from_scores(
        power_score or _level_default(power_level),
        interest_score or _level_default(interest_level),
    )
    return power_level, interest_level, quadrant


def _level_default(level: PowerLevel | InterestLevel) -> int:
    if level == PowerLevel.HIGH or level == InterestLevel.HIGH:
        return 9
    if level == PowerLevel.LOW or level == InterestLevel.LOW:
        return 2
    return 5


def _score_to_power_level(score: int | None) -> PowerLevel:
    if score is None:
        return PowerLevel.MEDIUM
    if score >= 8:
        return PowerLevel.HIGH
    if score <= 4:
        return PowerLevel.LOW
    return PowerLevel.MEDIUM


def _score_to_interest_level(score: int | None) -> InterestLevel:
    if score is None:
        return InterestLevel.MEDIUM
    if score >= 8:
        return InterestLevel.HIGH
    if score <= 4:
        return InterestLevel.LOW
    return InterestLevel.MEDIUM


def _quadrant_from_scores(power_score: int, interest_score: int) -> StakeholderQuadrant:
    high_power = power_score >= 8
    high_interest = interest_score >= 8
    low_power = power_score <= 4
    low_interest = interest_score <= 4

    if high_power and high_interest:
        return StakeholderQuadrant.KEY_PLAYER
    if high_power and low_interest:
        return StakeholderQuadrant.KEEP_SATISFIED
    if low_power and high_interest:
        return StakeholderQuadrant.KEEP_INFORMED
    return StakeholderQuadrant.MONITOR


def _to_response(stakeholder: Stakeholder) -> StakeholderResponseOut:
    return StakeholderResponseOut(
        id=stakeholder.id,
        project_id=stakeholder.project_id,
        name=stakeholder.name,
        role=stakeholder.role,
        company=stakeholder.organization,
        department=stakeholder.department,
        email=stakeholder.email,
        phone=stakeholder.phone,
        power_level=stakeholder.power_level,
        interest_level=stakeholder.interest_level,
        quadrant=stakeholder.quadrant,
        source_clause_id=stakeholder.source_clause_id,
        power_score=_score_from_metadata(
            stakeholder.stakeholder_metadata or {}, "power_score", stakeholder.power_level
        ),
        interest_score=_score_from_metadata(
            stakeholder.stakeholder_metadata or {},
            "interest_score",
            stakeholder.interest_level,
        ),
    )
