"""HITL REST endpoints: review queue, approve, reject, escalate."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.core.security import CurrentTenantId, CurrentUserId, security_scheme
from src.modules.hitl.adapters.http.dependencies import (
    get_hitl_service,
    get_review_queue_repo,
)
from src.modules.hitl.adapters.http.schemas import (
    ApproveRequest,
    RejectRequest,
    ReviewItemResponse,
    ReviewQueueResponse,
    RouteForReviewRequest,
)
from src.modules.hitl.adapters.persistence.repository import (
    SqlAlchemyReviewQueueRepository,
)
from src.modules.hitl.application.ports import HumanInTheLoopService
from src.modules.hitl.domain.entities import ReviewStatus

logger = structlog.get_logger()

router = APIRouter(
    prefix="/hitl",
    tags=["HITL"],
    dependencies=[Depends(security_scheme)],
    responses={404: {"description": "Not found"}},
)


# -- Endpoints ----------------------------------------------------------------

@router.post(
    "/route",
    response_model=ReviewItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Route an item for HITL review",
)
async def route_for_review(
    payload: RouteForReviewRequest,
    _tenant_id: CurrentTenantId,
    service: HumanInTheLoopService = Depends(get_hitl_service),
) -> ReviewItemResponse:
    result_status = await service.route_for_review(
        item_id=payload.item_id,
        item_type=payload.item_type,
        confidence=payload.confidence,
        impact_level=payload.impact_level,
        item_data=payload.item_data,
    )
    item = await service.review_queue_repo.get_review_item(payload.item_id)
    if item is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Item was routed but not found.")
    logger.info(
        "hitl_item_routed",
        item_id=str(payload.item_id),
        status=result_status.value,
    )
    return ReviewItemResponse(
        item_id=item.item_id,
        item_type=item.item_type,
        current_status=item.current_status,
        confidence=item.confidence,
        impact_level=item.impact_level,
        approved_by=item.approved_by,
        approved_at=item.approved_at,
        sla_due_date=item.sla_due_date,
        created_at=item.created_at,
        item_data=item.item_data,
    )


@router.get(
    "/queue",
    response_model=ReviewQueueResponse,
    summary="List items in the review queue",
)
async def list_review_queue(
    _tenant_id: CurrentTenantId,
    status_filter: ReviewStatus | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    repo: SqlAlchemyReviewQueueRepository = Depends(get_review_queue_repo),
) -> ReviewQueueResponse:
    items = await repo.list_by_status(status=status_filter, skip=skip, limit=limit)
    return ReviewQueueResponse(
        items=[
            ReviewItemResponse(
                item_id=i.item_id,
                item_type=i.item_type,
                current_status=i.current_status,
                confidence=i.confidence,
                impact_level=i.impact_level,
                approved_by=i.approved_by,
                approved_at=i.approved_at,
                sla_due_date=i.sla_due_date,
                created_at=i.created_at,
                item_data=i.item_data,
            )
            for i in items
        ],
        total=len(items),
    )


@router.get(
    "/queue/{item_id}",
    response_model=ReviewItemResponse,
    summary="Get a single review item",
)
async def get_review_item(
    item_id: UUID,
    _tenant_id: CurrentTenantId,
    repo: SqlAlchemyReviewQueueRepository = Depends(get_review_queue_repo),
) -> ReviewItemResponse:
    item = await repo.get_review_item(item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Review item {item_id} not found.")
    return ReviewItemResponse(
        item_id=item.item_id,
        item_type=item.item_type,
        current_status=item.current_status,
        confidence=item.confidence,
        impact_level=item.impact_level,
        approved_by=item.approved_by,
        approved_at=item.approved_at,
        sla_due_date=item.sla_due_date,
        created_at=item.created_at,
        item_data=item.item_data,
    )


@router.post(
    "/queue/{item_id}/approve",
    response_model=ReviewItemResponse,
    summary="Approve a review item",
)
async def approve_item(
    item_id: UUID,
    payload: ApproveRequest,
    _tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    service: HumanInTheLoopService = Depends(get_hitl_service),
) -> ReviewItemResponse:
    try:
        item = await service.approve_item(
            item_id=item_id,
            reviewer_id=user_id,
            reviewer_name=payload.reviewer_name,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    logger.info("hitl_item_approved", item_id=str(item_id), reviewer=payload.reviewer_name)
    return ReviewItemResponse(
        item_id=item.item_id,
        item_type=item.item_type,
        current_status=item.current_status,
        confidence=item.confidence,
        impact_level=item.impact_level,
        approved_by=item.approved_by,
        approved_at=item.approved_at,
        sla_due_date=item.sla_due_date,
        created_at=item.created_at,
        item_data=item.item_data,
    )


@router.post(
    "/queue/{item_id}/reject",
    response_model=ReviewItemResponse,
    summary="Reject a review item",
)
async def reject_item(
    item_id: UUID,
    payload: RejectRequest,
    _tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    service: HumanInTheLoopService = Depends(get_hitl_service),
) -> ReviewItemResponse:
    item = await service.review_queue_repo.get_review_item(item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Review item {item_id} not found.")
    if item.current_status not in {
        ReviewStatus.PENDING_REVIEW_REQUIRED,
        ReviewStatus.PENDING_REVIEW_CONDITIONAL,
    }:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Item {item_id} cannot be rejected from status {item.current_status.value}.",
        )
    item.current_status = ReviewStatus.REJECTED
    item.approved_by = payload.reviewer_name
    item.approved_at = datetime.utcnow()
    item.metadata["rejection_reason"] = payload.reason
    await service.review_queue_repo.update_review_item(item)
    logger.info("hitl_item_rejected", item_id=str(item_id), reviewer=payload.reviewer_name)
    return ReviewItemResponse(
        item_id=item.item_id,
        item_type=item.item_type,
        current_status=item.current_status,
        confidence=item.confidence,
        impact_level=item.impact_level,
        approved_by=item.approved_by,
        approved_at=item.approved_at,
        sla_due_date=item.sla_due_date,
        created_at=item.created_at,
        item_data=item.item_data,
    )


@router.post(
    "/queue/{item_id}/release",
    response_model=ReviewItemResponse,
    summary="Release an approved item (mark as CLOSED)",
)
async def release_item(
    item_id: UUID,
    _tenant_id: CurrentTenantId,
    _user_id: CurrentUserId,
    service: HumanInTheLoopService = Depends(get_hitl_service),
) -> ReviewItemResponse:
    try:
        item = await service.release_item(item_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    logger.info("hitl_item_released", item_id=str(item_id))
    return ReviewItemResponse(
        item_id=item.item_id,
        item_type=item.item_type,
        current_status=item.current_status,
        confidence=item.confidence,
        impact_level=item.impact_level,
        approved_by=item.approved_by,
        approved_at=item.approved_at,
        sla_due_date=item.sla_due_date,
        created_at=item.created_at,
        item_data=item.item_data,
    )


@router.post(
    "/escalate",
    summary="Check SLAs and escalate overdue items",
)
async def check_and_escalate(
    _tenant_id: CurrentTenantId,
    service: HumanInTheLoopService = Depends(get_hitl_service),
) -> dict[str, Any]:
    results = await service.check_and_escalate_slas()
    return {
        "escalated_count": len(results),
        "items": [
            {
                "item_id": str(r.item_id),
                "is_overdue": r.is_overdue,
                "new_status": r.new_status.value,
                "message": r.message,
            }
            for r in results
        ],
    }
