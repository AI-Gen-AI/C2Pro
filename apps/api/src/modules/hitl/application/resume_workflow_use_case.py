"""
Use case for resuming LangGraph workflows after HITL approval/rejection.
Part of TASK-BCK-024: Implement HITL workflow resume mechanism after approval.
Part of TASK-BCK-031: Implement LangGraph checkpoint restoration for HITL resume workflow.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID

import structlog

from src.core.observability.monitoring import (
    record_hitl_resume_attempt,
    record_hitl_resume_error,
    record_hitl_resume_latency,
)
from src.modules.hitl.domain.entities import ReviewStatus
from src.modules.hitl.ports.review_queue_repository import IReviewQueueRepository

logger = structlog.get_logger()


class WorkflowDecision(str, Enum):
    """Decision for workflow resumption."""
    APPROVE = "approve"
    REJECT = "reject"


@dataclass(frozen=True)
class ResumeWorkflowRequest:
    """Request to resume a workflow after HITL review."""
    decision: WorkflowDecision
    feedback: str


@dataclass(frozen=True)
class ResumeWorkflowResponse:
    """Response from workflow resumption."""
    review_id: UUID
    status: str  # "resumed", "approved", "rejected", "terminated"
    message: str


class ResumeWorkflowUseCase:
    """
    Handles resumption of LangGraph workflows after HITL approval/rejection.

    Flow:
    1. Load review item by ID
    2. Validate review item is in pending status
    3. Load LangGraph checkpoint from PostgreSQL (TASK-BCK-031)
    4. Update review item status and decision
    5. Inject approval/rejection into state.human_feedback (TASK-BCK-031)
    6. Resume workflow from human_interrupt_node or terminate (TASK-BCK-031)
    7. Return response
    """

    _ERR_NOT_FOUND = "Review item {review_id} not found"
    _ERR_NOT_PENDING = "Review item {review_id} is not in pending status (current: {status})"
    _ERR_MISSING_CHECKPOINT = "Review item {review_id} missing checkpoint_id for workflow resumption"
    _ERR_MISSING_THREAD_ID = "Review item {review_id} missing thread_id for workflow resumption"
    _ERR_ALREADY_PROCESSED = "Review item {review_id} already processed (status: {status})"
    _ERR_CHECKPOINT_NOT_FOUND = "Checkpoint not found for thread_id {thread_id}"

    def __init__(
        self,
        review_queue_repo: IReviewQueueRepository,
        checkpoint_service=None,
        graph_app=None,
    ):
        """
        Initialize use case with dependencies.

        Args:
            review_queue_repo: Repository for review items
            checkpoint_service: Service for loading checkpoints (optional, created if None)
            graph_app: LangGraph compiled graph app (optional, loaded if None)
        """
        self.review_queue_repo = review_queue_repo
        self._checkpoint_service = checkpoint_service
        self._graph_app = graph_app

    def _get_checkpoint_service(self):
        """Get or create checkpoint service lazily."""
        if self._checkpoint_service is None:
            from src.analysis.adapters.graph.workflow import get_graph_app
            from src.modules.hitl.adapters.checkpoint_service import CheckpointService

            graph_app = get_graph_app()
            checkpointer = getattr(graph_app, "checkpointer", None)
            if checkpointer is None:
                raise RuntimeError("Graph app has no checkpointer configured")
            self._checkpoint_service = CheckpointService(checkpointer)
        return self._checkpoint_service

    def _get_graph_app(self):
        """Get graph app lazily."""
        if self._graph_app is None:
            from src.analysis.adapters.graph.workflow import get_graph_app

            self._graph_app = get_graph_app()
        return self._graph_app

    async def execute(
        self,
        review_id: UUID,
        request: ResumeWorkflowRequest,
    ) -> ResumeWorkflowResponse:
        """
        Resume workflow with approval or rejection decision.

        Args:
            review_id: ID of the review item to resume
            request: Resume request with decision and feedback

        Returns:
            ResumeWorkflowResponse with status and message

        Raises:
            ValueError: If review item not found, not pending, or missing checkpoint
        """
        start_time = time.perf_counter()
        decision = request.decision.value
        status = "unknown"

        try:
            # 1. Load review item
            review_item = await self.review_queue_repo.get_review_item(review_id)
            if not review_item:
                record_hitl_resume_error("not_found")
                raise ValueError(self._ERR_NOT_FOUND.format(review_id=review_id))

            # 2. Validate review item is in pending status
            pending_statuses = {
                ReviewStatus.PENDING_REVIEW_REQUIRED,
                ReviewStatus.PENDING_REVIEW_CONDITIONAL,
            }
            if review_item.current_status not in pending_statuses:
                # Check if already processed (idempotency)
                if review_item.current_status in {ReviewStatus.APPROVED, ReviewStatus.REJECTED}:
                    status = "already_processed"
                    record_hitl_resume_attempt(decision, status)
                    duration = time.perf_counter() - start_time
                    record_hitl_resume_latency(decision, duration)
                    return ResumeWorkflowResponse(
                        review_id=review_id,
                        status=review_item.current_status.value,
                        message=self._ERR_ALREADY_PROCESSED.format(
                            review_id=review_id,
                            status=review_item.current_status.value
                        ),
                    )
                record_hitl_resume_error("not_pending")
                raise ValueError(
                    self._ERR_NOT_PENDING.format(
                        review_id=review_id,
                        status=review_item.current_status.value
                    )
                )

            # 3. Validate checkpoint tracking fields exist
            checkpoint_id = review_item.metadata.get("checkpoint_id")
            thread_id = review_item.metadata.get("thread_id")

            if not checkpoint_id:
                record_hitl_resume_error("missing_checkpoint")
                raise ValueError(self._ERR_MISSING_CHECKPOINT.format(review_id=review_id))
            if not thread_id:
                record_hitl_resume_error("missing_thread")
                raise ValueError(self._ERR_MISSING_THREAD_ID.format(review_id=review_id))

            # 4. Load checkpoint from PostgreSQL (TASK-BCK-031)
            logger.info(
                "loading_checkpoint",
                review_id=str(review_id),
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
            )

            checkpoint_service = self._get_checkpoint_service()
            checkpoint = await checkpoint_service.load_checkpoint(
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
            )

            if not checkpoint:
                record_hitl_resume_error("checkpoint_not_found")
                raise ValueError(self._ERR_CHECKPOINT_NOT_FOUND.format(thread_id=thread_id))

            # 5. Extract and update state with human feedback (TASK-BCK-031)
            state = checkpoint_service.extract_state(checkpoint)

            # Inject human decision into state
            state["human_feedback"] = request.feedback
            state["human_approval_required"] = False
            state["human_decision"] = request.decision.value

            logger.info(
                "state_updated",
                review_id=str(review_id),
                decision=request.decision.value,
                feedback_length=len(request.feedback),
            )

            # 6. Update review item based on decision
            if request.decision == WorkflowDecision.APPROVE:
                review_item.current_status = ReviewStatus.APPROVED
                review_item.approved_at = datetime.now(UTC)
                status_message = "resumed"
            else:  # REJECT
                review_item.current_status = ReviewStatus.REJECTED
                status_message = "rejected"

            # Store feedback/reason in review_decision field
            review_item.metadata["review_decision"] = request.feedback

            # Save updated review item
            await self.review_queue_repo.update_review_item(review_item)

            # 7. Resume or terminate workflow (TASK-BCK-031)
            graph_app = self._get_graph_app()
            config = {"configurable": {"thread_id": thread_id}}

            try:
                if request.decision == WorkflowDecision.APPROVE:
                    # Resume workflow with updated state
                    logger.info(
                        "resuming_workflow",
                        review_id=str(review_id),
                        thread_id=thread_id,
                    )

                    # Use update_state to inject the modified state back into the checkpoint
                    # This will resume from the interrupt point (human_interrupt_node)
                    await graph_app.aupdate_state(config, state)

                    logger.info(
                        "workflow_resumed",
                        review_id=str(review_id),
                        thread_id=thread_id,
                        status=status_message,
                    )

                else:  # REJECT
                    # For rejection, we update state but don't resume - the workflow ends
                    # The state is updated to reflect the rejection for audit purposes
                    logger.info(
                        "workflow_terminated",
                        review_id=str(review_id),
                        thread_id=thread_id,
                        reason=request.feedback[:100],
                    )

                    # Update state with rejection info (for audit trail)
                    state["workflow_terminated"] = True
                    state["termination_reason"] = request.feedback
                    await graph_app.aupdate_state(config, state)

            except Exception as e:
                logger.error(
                    "workflow_resumption_failed",
                    review_id=str(review_id),
                    thread_id=thread_id,
                    error=str(e),
                    exc_info=True,
                )
                record_hitl_resume_error("workflow_error")
                # Don't fail the entire operation if workflow resumption fails
                # The review item is already updated, so the decision is recorded
                status_message = f"{status_message}_with_errors"

            # Record success metrics
            duration = time.perf_counter() - start_time
            record_hitl_resume_attempt(decision, status_message)
            record_hitl_resume_latency(decision, duration)

            return ResumeWorkflowResponse(
                review_id=review_id,
                status=status_message,
                message=f"Workflow {status_message} with feedback: {request.feedback[:100]}",
            )

        except ValueError:
            duration = time.perf_counter() - start_time
            record_hitl_resume_latency(decision, duration)
            raise
