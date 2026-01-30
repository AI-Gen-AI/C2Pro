"""
HTTP adapter (FastAPI router) for approval workflow.

Transitional location under stakeholders until a dedicated approvals module exists.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.core.approval import ApprovalStatus
from src.core.database import get_session
from src.core.security import CurrentTenantId, CurrentUserId
from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)
from src.stakeholders.application.review_stakeholder_approval_use_case import (
    ReviewStakeholderApprovalUseCase,
)

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
}

def get_repository(
    db=Depends(get_session),
) -> SqlAlchemyStakeholderRepository:
    return SqlAlchemyStakeholderRepository(session=db)

def get_review_use_case(
    repo: SqlAlchemyStakeholderRepository = Depends(get_repository),
) -> ReviewStakeholderApprovalUseCase:
    return ReviewStakeholderApprovalUseCase(repository=repo)


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
    use_case: ReviewStakeholderApprovalUseCase = Depends(get_review_use_case),
) -> ApprovalResponse:
    resource_type = resource_type.lower()
    if resource_type not in RESOURCE_MAP:
        raise HTTPException(status_code=400, detail="Unsupported resource type")

    if resource_type == "stakeholders":
        try:
            record, original_snapshot = await use_case.execute(
                stakeholder_id=resource_id,
                status=payload.status,
                correction_data=payload.correction_data,
                feedback_comment=payload.feedback_comment,
                user_id=user_id,
            )
        except ValueError:
            raise HTTPException(status_code=404, detail="Stakeholder not found")
    else:
        raise HTTPException(status_code=400, detail="Unsupported resource type")

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
