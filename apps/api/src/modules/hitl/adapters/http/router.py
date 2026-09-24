"""HITL REST endpoints: review queue, approve, reject, escalate."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
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
    ResumeWorkflowRequest as UseCaseResumeRequest,
)
from src.modules.hitl.application.resume_workflow_use_case import (
    ResumeWorkflowUseCase,
    WorkflowDecision,
)
from src.modules.hitl.domain.entities import ReviewItem, ReviewStatus
from src.temporal.application.project_snapshot_trigger import (
    record_project_event_and_enqueue_snapshot,
)
from src.temporal.domain.project_snapshot import SnapshotTrigger

logger = structlog.get_logger()

router = APIRouter(
    prefix="/hitl",
    tags=["HITL"],
    dependencies=[Depends(security_scheme)],
    responses={404: {"description": "Not found"}},
)


async def _record_hitl_correction_snapshot(
    *,
    item_id: UUID,
    item_data: dict[str, Any],
    metadata: dict[str, Any],
    tenant_id: CurrentTenantId,
    decision: ReviewStatus,
    reviewer: str | None,
) -> None:
    """Record a project-scoped human decision and enqueue its temporal snapshot."""
    project_id_raw = metadata.get("project_id") or item_data.get("project_id")
    if project_id_raw is None:
        logger.info("hitl_correction_snapshot_skipped_no_project", item_id=str(item_id))
        return

    try:
        project_id = UUID(str(project_id_raw))
    except (TypeError, ValueError):
        logger.warning(
            "hitl_correction_snapshot_skipped_invalid_project",
            item_id=str(item_id),
            project_id=project_id_raw,
        )
        return

    try:
        await record_project_event_and_enqueue_snapshot(
            project_id=project_id,
            tenant_id=tenant_id,
            event_type="hitl.correction",
            payload={
                "review_item_id": str(item_id),
                "decision": decision.value,
                "reviewer": reviewer,
            },
            trigger=SnapshotTrigger.HITL_CORRECTION,
            actor=reviewer,
        )
    except Exception:  # noqa: BLE001 - a temporal trigger must not block a reviewed decision.
        logger.warning(
            "hitl_correction_snapshot_trigger_failed",
            item_id=str(item_id),
            tenant_id=str(tenant_id),
            exc_info=True,
        )


def _to_review_item_response(item: ReviewItem) -> ReviewItemResponse:
    row_id_raw = item.metadata.get("row_id")
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
        row_id=UUID(str(row_id_raw)) if row_id_raw else None,
        resumable=bool(item.metadata.get("thread_id")),
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
    return _to_review_item_response(item)


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
    project_id: UUID | None = Query(None, description="Filter by project"),
    repo: SqlAlchemyReviewQueueRepository = Depends(get_review_queue_repo),
) -> ReviewQueueResponse:
    items = await repo.list_by_status(
        status=status_filter,
        skip=skip,
        limit=limit,
        project_id=project_id,
    )
    total = await repo.count_by_status(
        status=status_filter,
        project_id=project_id,
    )
    return ReviewQueueResponse(
        items=[_to_review_item_response(i) for i in items],
        total=total,
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
    return _to_review_item_response(item)


async def _approve_and_resume_workflow(
    *,
    item_id: UUID,
    reviewer_name: str,
    resume_use_case: ResumeWorkflowUseCase,
    row_id: str | None = None,
) -> ReviewItem:
    """Approve a graph-gated review (one carrying a real thread_id) by
    resuming its actual LangGraph workflow -- C2PRO P0b HITL approve/resume
    hotfix.

    Production evidence: POST /queue/{item_id}/approve returned 200 and the
    row flipped to APPROVED, but ResumeWorkflowUseCase was never invoked --
    no analyses row, no graph.completed, document stuck at
    parsed_pending_analysis, Health never readable. approve_item() only
    ever flipped a status flag; it has no notion of a workflow to resume.

    Raises HTTPException(502) on a genuine resume failure -- see the
    "_with_errors" branch below -- so the caller never reports a workflow
    resume as if it were a clean success. The review's APPROVED status is
    NOT rolled back on that path: ResumeWorkflowUseCase durably records the
    human decision before attempting resume, by design, so a mechanical
    resume failure never erases an audit trail entry. The explicit 502
    tells the caller the workflow itself did not resume and needs
    operator/retry attention.
    """
    try:
        result = await resume_use_case.execute(
            review_id=item_id,
            request=UseCaseResumeRequest(
                decision=WorkflowDecision.APPROVE,
                feedback="",
                approved_by=reviewer_name,
            ),
        )
    except ValueError as exc:
        error_msg = str(exc)
        if "not found" in error_msg:
            raise HTTPException(status.HTTP_404_NOT_FOUND, error_msg) from exc
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error_msg) from exc
    except Exception as exc:  # noqa: BLE001
        # C2PRO P0b true-resume hotfix: a genuine resume failure now RAISES
        # out of the use case instead of being swallowed into a
        # "_with_errors" status, because the decision is no longer recorded
        # before the workflow has actually completed. Keep the explicit 502
        # contract so the caller still learns the workflow did not resume --
        # but note the review now deliberately stays PENDING and retryable,
        # instead of the previous false "APPROVED yet nothing ran".
        logger.error(
            "hitl_approve_resume_failed",
            item_id=str(item_id),
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Resuming the analysis workflow failed; the review is unchanged: {exc}",
        ) from exc

    if result.status.endswith("_with_errors"):
        logger.error(
            "hitl_approve_resume_failed",
            item_id=str(item_id),
            resume_status=result.status,
            message=result.message,
        )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Review approved, but resuming the analysis workflow failed: {result.message}",
        )

    # C2PRO P0b legacy canonical-selection hotfix: re-fetch by the EXACT
    # row primary key the caller already resolved (existing.metadata
    # ["row_id"] at the call site), not by item_id again. Once resume
    # flips this row to APPROVED, it can now tie on status with an older
    # historical row that shares item_id and was already APPROVED --
    # re-resolving by the ambiguous business key can then silently return
    # that OTHER row's data instead of the one this request just acted on.
    lookup_id = UUID(row_id) if row_id else item_id
    item = await resume_use_case.review_queue_repo.get_review_item(lookup_id)
    if item is None:  # pragma: no cover - execute() above already confirmed the row exists
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Review item {item_id} not found.")
    return item


@router.post(
    "/queue/{item_id}/approve",
    response_model=ReviewItemResponse,
    summary="Approve a review item",
)
async def approve_item(
    item_id: UUID,
    _payload: ApproveRequest,
    _tenant_id: CurrentTenantId,
    current_user: Annotated[User, Depends(get_current_user)],
    service: HumanInTheLoopService = Depends(get_hitl_service),
    resume_use_case: ResumeWorkflowUseCase = Depends(get_resume_workflow_use_case),
) -> ReviewItemResponse:
    # SECURITY (EPIC-OPS-DOCFLOW Stream C): reviewer identity is bound to the
    # authenticated session, never to client-supplied values — otherwise any
    # authenticated user could forge a review as another user. ApproveRequest
    # carries no reviewer fields by design.
    existing = await service.review_queue_repo.get_review_item(item_id)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Review item {item_id} not found.")

    if existing.metadata.get("thread_id"):
        # Graph-gated review (analysis_critique): approval must resume the
        # SAME LangGraph thread/checkpoint this review was created from.
        #
        # C2PRO #649: no hitl.correction is appended here. The V3
        # finalization commits it atomically with the decision, keyed by
        # resume_operation_id, so this response -- which is ALSO what every
        # idempotent replay (double click, lost-response retry) returns --
        # must never add another one.
        item = await _approve_and_resume_workflow(
            item_id=item_id,
            reviewer_name=current_user.full_name,
            resume_use_case=resume_use_case,
            row_id=existing.metadata.get("row_id"),
        )
    else:
        try:
            item = await service.approve_item(
                item_id=item_id,
                reviewer_id=current_user.id,
                reviewer_name=current_user.full_name,
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

        # Non-graph review: approve_item() refuses anything not pending, so
        # reaching this line means THIS request made the decision.
        await _record_hitl_correction_snapshot(
            item_id=item.item_id,
            item_data=item.item_data,
            metadata=item.metadata,
            tenant_id=_tenant_id,
            decision=item.current_status,
            reviewer=item.approved_by,
        )
    logger.info("hitl_item_approved", item_id=str(item_id), reviewer=current_user.full_name)
    return _to_review_item_response(item)


@router.post(
    "/queue/{item_id}/reject",
    response_model=ReviewItemResponse,
    summary="Reject a review item",
)
async def reject_item(
    item_id: UUID,
    payload: RejectRequest,
    _tenant_id: CurrentTenantId,
    current_user: Annotated[User, Depends(get_current_user)],
    service: HumanInTheLoopService = Depends(get_hitl_service),
    resume_use_case: ResumeWorkflowUseCase = Depends(get_resume_workflow_use_case),
) -> ReviewItemResponse:
    existing = await service.review_queue_repo.get_review_item(item_id)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Review item {item_id} not found.")

    if existing.metadata.get("thread_id"):
        # Graph-gated review: rejection must also terminate the SAME
        # LangGraph thread/checkpoint (state.workflow_terminated), not just
        # flip a status flag, for the same reason approval must resume it.
        try:
            await resume_use_case.execute(
                review_id=item_id,
                request=UseCaseResumeRequest(
                    decision=WorkflowDecision.REJECT,
                    feedback=payload.reason,
                    approved_by=current_user.full_name,
                ),
            )
        except ValueError as exc:
            error_msg = str(exc)
            if "not found" in error_msg:
                raise HTTPException(status.HTTP_404_NOT_FOUND, error_msg) from exc
            raise HTTPException(status.HTTP_400_BAD_REQUEST, error_msg) from exc
        # C2PRO P0b legacy canonical-selection hotfix: re-fetch by the same
        # row primary key `existing` was already resolved to, not item_id
        # again -- see _approve_and_resume_workflow's matching comment for
        # why re-resolving by item_id after the status flip can return a
        # different, historical row sharing this item_id.
        existing_row_id = existing.metadata.get("row_id")
        lookup_id = UUID(existing_row_id) if existing_row_id else item_id
        item = await service.review_queue_repo.get_review_item(lookup_id)
        if item is None:  # pragma: no cover - execute() above already confirmed the row exists
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Review item {item_id} not found.")
        item.metadata["rejection_reason"] = payload.reason
        await service.review_queue_repo.update_review_item(item)
    else:
        if existing.current_status not in {
            ReviewStatus.PENDING_REVIEW_REQUIRED,
            ReviewStatus.PENDING_REVIEW_CONDITIONAL,
        }:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Item {item_id} cannot be rejected from status {existing.current_status.value}.",
            )
        item = existing
        item.current_status = ReviewStatus.REJECTED
        # SECURITY (EPIC-OPS-DOCFLOW Stream C): reviewer identity is bound to
        # the authenticated session, never to client-supplied values —
        # otherwise any authenticated user could forge a rejection as
        # another user.
        item.approved_by = current_user.full_name
        item.approved_at = datetime.now(UTC)
        item.metadata["rejection_reason"] = payload.reason
        await service.review_queue_repo.update_review_item(item)

        # Non-graph review only; graph-gated rejections record their single
        # hitl.correction inside the V3 finalization (C2PRO #649).
        await _record_hitl_correction_snapshot(
            item_id=item.item_id,
            item_data=item.item_data,
            metadata=item.metadata,
            tenant_id=_tenant_id,
            decision=item.current_status,
            reviewer=item.approved_by,
        )
    logger.info("hitl_item_rejected", item_id=str(item_id), reviewer=current_user.full_name)
    return _to_review_item_response(item)


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
    return _to_review_item_response(item)


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
        400: {
            "description": "Invalid request - review item not pending or missing checkpoint data"
        },
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

        return ResumeWorkflowResponse(
            review_id=result.review_id,
            status=result.status,
            message=result.message,
        )

    except ValueError as exc:
        error_msg = str(exc)
        if "not found" in error_msg:
            raise HTTPException(status.HTTP_404_NOT_FOUND, error_msg)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error_msg)
