from __future__ import annotations

# LEGACY: replaced by src.stakeholders.adapters.http.approvals_router.

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.approval import ApprovalStatus
from src.core.database import get_session
from src.core.security import CurrentTenantId, CurrentUserId
from src.modules.analysis.models import Alert
from src.stakeholders.adapters.persistence.models import StakeholderORM

logger = structlog.get_logger()

router = APIRouter(
    prefix="/approvals",
    tags=["Approvals"],
    responses={404: {"description": "Not Found"}},
)


class ApprovalReview(BaseModel):
    status: ApprovalStatus
    correction_data: dict[str, Any] | None = None
    feedback_comment: str | None = None


class ApprovalResponse(BaseModel):
    resource_type: str
    resource_id: UUID
    status: ApprovalStatus


RESOURCE_MAP = {
    "stakeholders": "stakeholders",
    "risks": "alerts",
}


@router.patch(
    "/{resource_type}/{resource_id}",
    response_model=ApprovalResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve, reject, or correct AI-generated resources",
)
async def review_resource(
    resource_type: str,
    resource_id: UUID,
    payload: ApprovalReview,
    _tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_session),
) -> ApprovalResponse:
    resource_type = resource_type.lower()
    if resource_type not in RESOURCE_MAP:
        raise HTTPException(status_code=400, detail="Unsupported resource type")

    if resource_type == "stakeholders":
        record = await _get_stakeholder(db, resource_id)
        original_snapshot = _snapshot_record(record)
        _apply_corrections(record, payload.correction_data, _stakeholder_fields())
    else:
        record = await _get_alert(db, resource_id)
        original_snapshot = _snapshot_record(record)
        _apply_corrections(record, payload.correction_data, _alert_fields())

    record.approval_status = _normalize_status(payload.status, payload.correction_data)
    record.reviewed_by = user_id
    record.reviewed_at = datetime.utcnow()
    record.review_comment = payload.feedback_comment

    await db.commit()

    if payload.status in {ApprovalStatus.REJECTED, ApprovalStatus.CORRECTED}:
        logger.info(
            "ai_feedback_recorded",
            resource_type=resource_type,
            resource_id=str(resource_id),
            user_id=str(user_id),
            tenant_id=str(_tenant_id),
            original_ai_output=original_snapshot,
            human_correction=payload.correction_data,
            feedback_comment=payload.feedback_comment,
        )

    return ApprovalResponse(
        resource_type=resource_type,
        resource_id=resource_id,
        status=record.approval_status,
    )


async def _get_stakeholder(db: AsyncSession, stakeholder_id: UUID) -> StakeholderORM:
    result = await db.get(StakeholderORM, stakeholder_id)
    if not result:
        raise HTTPException(status_code=404, detail="Stakeholder not found")
    return result


async def _get_alert(db: AsyncSession, alert_id: UUID) -> Alert:
    result = await db.get(Alert, alert_id)
    if not result:
        raise HTTPException(status_code=404, detail="Risk not found")
    return result


def _apply_corrections(record: Any, corrections: dict[str, Any] | None, allowed: set[str]) -> bool:
    if not corrections:
        return False
    updated = False
    for key, value in corrections.items():
        if key not in allowed:
            continue
        if hasattr(record, key):
            setattr(record, key, value)
            updated = True
    return updated


def _normalize_status(status: ApprovalStatus, corrections: dict[str, Any] | None) -> ApprovalStatus:
    if status == ApprovalStatus.REJECTED:
        return ApprovalStatus.REJECTED
    if corrections:
        return ApprovalStatus.CORRECTED
    if status == ApprovalStatus.CORRECTED:
        return ApprovalStatus.CORRECTED
    if status == ApprovalStatus.APPROVED:
        return ApprovalStatus.APPROVED
    return ApprovalStatus.PENDING


def _stakeholder_fields() -> set[str]:
    return {
        "name",
        "role",
        "organization",
        "department",
        "email",
        "phone",
        "power_level",
        "interest_level",
        "quadrant",
        "stakeholder_metadata",
    }


def _alert_fields() -> set[str]:
    return {
        "title",
        "description",
        "recommendation",
        "severity",
        "category",
        "impact_level",
        "alert_metadata",
    }


def _snapshot_record(record: Any) -> dict[str, Any]:
    snapshot = {}
    for field in _stakeholder_fields() | _alert_fields():
        if hasattr(record, field):
            snapshot[field] = getattr(record, field)
    return snapshot
