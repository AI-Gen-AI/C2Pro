"""HITL REST endpoints: review queue, approve, reject, escalate."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.core.observability.monitoring import record_hitl_decision
from src.core.security import CurrentTenantId, CurrentUserId, security_scheme
from src.modules.hitl.adapters.http.dependencies import (
    get_hitl_service,
    get_resume_workflow_use_case,  # TASK-BCK-024
    get_review_queue_repo,
)
from src.modules.hitl.adapters.http.schemas import (
    ApproveRequest,
    RejectRequest,
    ResumeWorkflowRequest,  # TASK-BCK-024
    ResumeWorkflowResponse,  # TASK-BCK-024
    ReviewItemResponse,
    ReviewQueueResponse,
    RouteForReviewRequest,
)
from src.modules.hitl.adapters.persistence.repository import (
    SqlAlchemyReviewQueueRepository,
)
from src.modules.hitl.application.ports import HumanInTheLoopService
from src.modules.hitl.application.resume_workflow_use_case import (  # TASK-BCK-024
    ResumeWorkflowUseCase,
    WorkflowDecision,
)
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
    _user_id: CurrentUserId,
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
    item.approved_at = datetime.now(UTC)
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


# TASK-BCK-024: Resume workflow after HITL approval/rejection
@router.post(
    "/resume/{review_id}",
    operation_id="resumeHitlWorkflow",
    response_model=ResumeWorkflowResponse,
    status_code=status.HTTP_200_OK,
    summary="Resume workflow after HITL approval/rejection",
    description="""
    Resume a LangGraph workflow after HITL review decision.

    This endpoint handles both approval and rejection decisions from human reviewers:

    - **Approve**: The workflow resumes from the interrupt point with the approved status.
      Human feedback is injected into the workflow state and execution continues.

    - **Reject**: The workflow terminates gracefully. The rejection reason is stored
      for audit purposes but no further workflow steps are executed.

    **Prerequisites**:
    - Review item must exist and be in `PENDING_REVIEW_REQUIRED` or `PENDING_REVIEW_CONDITIONAL` status
    - Review item must have a valid `checkpoint_id` and `thread_id` from the interrupted workflow

    **Metrics**: This endpoint emits Prometheus metrics for monitoring:
    - `c2pro_hitl_resume_total` - Total resume attempts by decision and status
    - `c2pro_hitl_resume_latency_seconds` - Resume operation latency
    - `c2pro_hitl_resume_errors_total` - Errors by type
    """,
    responses={
        200: {
            "description": "Workflow resume operation completed successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "approved": {
                            "summary": "Workflow resumed after approval",
                            "value": {
                                "review_id": "45cc5455-8770-4949-9fb2-9a9426851c20",
                                "status": "resumed",
                                "message": "Workflow resumed with feedback: Approved by PM reviewer",
                            },
                        },
                        "rejected": {
                            "summary": "Workflow terminated after rejection",
                            "value": {
                                "review_id": "45cc5455-8770-4949-9fb2-9a9426851c20",
                                "status": "rejected",
                                "message": "Workflow rejected with feedback: Rejected - requires legal review",
                            },
                        },
                    }
                }
            },
        },
        400: {"description": "Invalid request - review item not pending or missing checkpoint data"},
        404: {"description": "Review item not found"},
        422: {"description": "Validation error - invalid decision value or feedback too long"},
    },
    tags=["HITL", "Workflow"],
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "examples": {
                        "approve": {
                            "summary": "Approve and resume workflow",
                            "value": {
                                "decision": "approve",
                                "feedback": "Approved by PM reviewer",
                            },
                        },
                        "reject": {
                            "summary": "Reject and terminate workflow",
                            "value": {
                                "decision": "reject",
                                "feedback": "Rejected - legal clause is ambiguous",
                            },
                        },
                    }
                }
            },
        }
    },
)
async def resume_workflow(
    review_id: UUID,
    payload: ResumeWorkflowRequest,
    tenant_id: CurrentTenantId,
    use_case: ResumeWorkflowUseCase = Depends(get_resume_workflow_use_case),
) -> ResumeWorkflowResponse:
    """
    Resume a LangGraph workflow after HITL review decision.

    Handles both approval (resumes workflow) and rejection (terminates workflow).
    Updates review item status and injects decision into workflow state.

    Args:
        review_id: ID of the review item to resume
        payload: Decision (approve/reject) and feedback

    Returns:
        ResumeWorkflowResponse with status and message

    Raises:
        HTTPException 404: Review item not found
        HTTPException 400: Review item not in pending status or missing checkpoint
    """
    try:
        # Convert string decision to enum
        decision = WorkflowDecision(payload.decision)

        # Create use case request
        from src.modules.hitl.application.resume_workflow_use_case import (
            ResumeWorkflowRequest as UseCaseRequest,
        )
        request = UseCaseRequest(decision=decision, feedback=payload.feedback)

        # Execute use case
        result = await use_case.execute(review_id=review_id, request=request)

        # TASK-BCK-032: update tenant-scoped approval-rate gauge + audit log
        record_hitl_decision(str(tenant_id), payload.decision)

        logger.info(
            "workflow_resumed",
            review_id=str(review_id),
            tenant_id=str(tenant_id),
            decision=payload.decision,
            status=result.status,
        )

        return result

    except ValueError as exc:
        error_msg = str(exc)
        if "not found" in error_msg:
            raise HTTPException(status.HTTP_404_NOT_FOUND, error_msg)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error_msg)
