"""
Use case for resuming LangGraph workflows after HITL approval/rejection.
Part of TASK-BCK-024: Implement HITL workflow resume mechanism after approval.
Part of TASK-BCK-031: Implement LangGraph checkpoint restoration for HITL resume workflow.
Refers to Suite ID: TS-BCK-032-001.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import structlog
from langgraph.types import Command

if TYPE_CHECKING:
    from src.modules.hitl.adapters.checkpoint_service import CheckpointService

from src.core.observability.monitoring import (
    record_hitl_checkpoint_load_error,
    record_hitl_resume_attempt,
    record_hitl_resume_error,
    record_hitl_resume_latency,
    record_hitl_workflow_resume_error,
)
from src.modules.hitl.adapters.persistence.resume_claim import (
    claim_resume,
    release_resume_claim,
)
from src.modules.hitl.domain.entities import ReviewStatus
from src.modules.hitl.ports.review_queue_repository import IReviewQueueRepository

logger = structlog.get_logger()


class WorkflowDecision(StrEnum):
    """Decision for workflow resumption."""
    APPROVE = "approve"
    REJECT = "reject"


@dataclass(frozen=True)
class ResumeWorkflowRequest:
    """Request to resume a workflow after HITL review."""
    decision: WorkflowDecision
    feedback: str
    # C2PRO P0b HITL approve/resume hotfix: the authenticated reviewer's
    # display name, when the caller has one (e.g. the /queue/{item_id}/approve
    # route, which requires a signed-in user). Optional and defaulted so the
    # pre-existing /resume/{review_id} route (which has no user identity
    # today) keeps working unchanged.
    approved_by: str | None = None


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
    _ERR_ALREADY_CLAIMED = (
        "Review item {review_id} is already being resumed by another request"
    )
    _ERR_INTERRUPT_NOT_CONSUMED = (
        "Resume did not consume the human interrupt for review {review_id} "
        "(thread {thread_id}); the workflow did not advance"
    )
    _ERR_DOWNSTREAM_INCOMPLETE = (
        "Resume of review {review_id} (thread {thread_id}) did not reach durable "
        "persistence; no analysis was produced"
    )
    _ERR_NOT_PENDING = "Review item {review_id} is not in pending status (current: {status})"
    _ERR_MISSING_THREAD_ID = "Review item {review_id} missing thread_id for workflow resumption"
    _ERR_ALREADY_PROCESSED = "Review item {review_id} already processed (status: {status})"
    _ERR_CHECKPOINT_NOT_FOUND = "Checkpoint not found for thread_id {thread_id}"

    def __init__(
        self,
        review_queue_repo: IReviewQueueRepository,
        checkpoint_service: CheckpointService | None = None,
        graph_app: Any = None,
        claim_session_factory: Any = None,
    ) -> None:
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
        # Optional injection point for the exactly-once claim's own
        # short-lived session (tests supply the test session factory).
        self._claim_session_factory = claim_session_factory

    # -- exactly-once / atomicity helpers ------------------------------------

    @staticmethod
    def _row_id_for(review_item: Any, review_id: UUID) -> UUID:
        """The review's TRUE row primary key.

        metadata["row_id"] is the persistent row identity threaded through
        the domain layer (item_id is a business key and is NOT unique across
        legacy duplicates -- see SqlAlchemyReviewQueueRepository._to_domain).
        The claim must address the exact row, never a sibling.
        """
        row_id_raw = (review_item.metadata or {}).get("row_id")
        return UUID(str(row_id_raw)) if row_id_raw else review_id

    def _tenant_id_for(self, review_item: Any) -> UUID:
        """Tenant that owns this review.

        Prefers the row's own metadata, but falls back to the repository's
        tenant scope: legacy rows created before thread/checkpoint tracking
        existed often carry no tenant_id in metadata (exactly why
        _persist_real_checkpoint_id backfills it). The repository is already
        tenant-scoped and the review was resolved THROUGH that scope, so it
        is an authoritative -- and equally isolated -- source.
        """
        tenant_raw = (review_item.metadata or {}).get("tenant_id")
        if tenant_raw:
            return UUID(str(tenant_raw))
        repo_tenant = getattr(self.review_queue_repo, "tenant_id", None)
        if repo_tenant:
            return UUID(str(repo_tenant))
        raise ValueError(
            "Review item has no resolvable tenant; cannot claim a resume safely."
        )

    def _assert_interrupt_consumed(
        self, resumed_state: Any, *, review_id: UUID, thread_id: str
    ) -> None:
        """A resume that returns another __interrupt__ did not advance.

        LangGraph signals "still interrupted" by returning __interrupt__ in
        the result rather than raising, so this must be checked explicitly
        or a non-resume is indistinguishable from a completion.
        """
        if isinstance(resumed_state, dict) and "__interrupt__" in resumed_state:
            raise RuntimeError(
                self._ERR_INTERRUPT_NOT_CONSUMED.format(
                    review_id=review_id, thread_id=thread_id
                )
            )

    def _assert_downstream_completed(
        self, resumed_state: Any, *, review_id: UUID, thread_id: str
    ) -> None:
        """An approval must have reached durable persistence (N17).

        A stale/wrong checkpoint resolves to a no-op that returns WITHOUT
        running anything and without raising, so the absence of an
        analysis_id is the honest signal that nothing was persisted.
        """
        if not isinstance(resumed_state, dict) or not resumed_state.get("analysis_id"):
            raise RuntimeError(
                self._ERR_DOWNSTREAM_INCOMPLETE.format(
                    review_id=review_id, thread_id=thread_id
                )
            )

    def _get_checkpoint_service(self) -> CheckpointService:
        """Get or create checkpoint service lazily."""
        if self._checkpoint_service is None:
            from src.analysis.adapters.graph.workflow import get_graph_app
            from src.modules.hitl.adapters.checkpoint_service import CheckpointService

            _gga: Any = get_graph_app
            graph_app = _gga()
            checkpointer = getattr(graph_app, "checkpointer", None)
            if checkpointer is None:
                raise RuntimeError("Graph app has no checkpointer configured")
            self._checkpoint_service = CheckpointService(checkpointer)
        return self._checkpoint_service

    def _get_graph_app(self) -> Any:
        """Get graph app lazily."""
        if self._graph_app is None:
            from src.analysis.adapters.graph.workflow import get_graph_app

            _gga: Any = get_graph_app
            self._graph_app = _gga()
        return self._graph_app

    async def _mark_document_analyzed_after_resume(
        self,
        *,
        review_id: UUID,
        review_item: Any,
        resumed_state: Any,
    ) -> None:
        """Transition the document to ANALYZED once the resumed graph
        actually persisted an analysis (N17 ran to completion).

        Best-effort and isolated in its own session: a failure here must
        never undo the HITL decision that was already recorded, and must
        never mark a document ANALYZED when the resumed run did not
        genuinely persist an analysis (e.g. it re-paused, or N17 itself
        degraded -- see save_to_db_node's own best-effort persistence).
        """
        if not isinstance(resumed_state, dict):
            return
        analysis_id = resumed_state.get("analysis_id")
        if not analysis_id:
            return

        document_id_raw = review_item.metadata.get("document_id")
        tenant_id_raw = review_item.metadata.get("tenant_id")
        if not document_id_raw or not tenant_id_raw:
            logger.warning(
                "resume_document_status_update_skipped_missing_ids",
                review_id=str(review_id),
            )
            return

        try:
            from src.core.database import get_raw_session
            from src.documents.adapters.persistence.sqlalchemy_document_repository import (
                SqlAlchemyDocumentRepository,
            )
            from src.documents.domain.models import DocumentStatus

            async with get_raw_session() as session:
                document_repo = SqlAlchemyDocumentRepository(session)
                await document_repo.update_status(
                    UUID(str(tenant_id_raw)),
                    UUID(str(document_id_raw)),
                    DocumentStatus.ANALYZED,
                )
                await session.commit()

            logger.info(
                "resume_document_marked_analyzed",
                review_id=str(review_id),
                document_id=str(document_id_raw),
                analysis_id=str(analysis_id),
            )
        except Exception:
            logger.warning(
                "resume_document_status_update_failed",
                review_id=str(review_id),
                document_id=str(document_id_raw),
                exc_info=True,
            )

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

            # 3. Validate checkpoint tracking fields exist.
            # thread_id is the authoritative, hard-required resume key --
            # CheckpointService.load_checkpoint keys its query on thread_id
            # alone. checkpoint_id, when present, pins the exact interrupted
            # checkpoint (captured for real via LangGraph's own aget_state in
            # run_orchestration -- never fabricated); when absent it is NOT
            # fatal, since load_checkpoint falls back to the latest
            # checkpoint for the thread, which for a freshly-interrupted
            # thread IS the interrupt point (C2PRO P0b HITL resume hotfix).
            checkpoint_id = review_item.metadata.get("checkpoint_id")
            thread_id = review_item.metadata.get("thread_id")

            if not thread_id:
                record_hitl_checkpoint_load_error("missing_thread")
                record_hitl_resume_error("missing_thread")
                raise ValueError(self._ERR_MISSING_THREAD_ID.format(review_id=review_id))
            if not checkpoint_id:
                logger.warning(
                    "resuming_without_explicit_checkpoint_id",
                    review_id=str(review_id),
                    thread_id=thread_id,
                )

            # 4. Load checkpoint from PostgreSQL (TASK-BCK-031)
            logger.info(
                "loading_checkpoint",
                review_id=str(review_id),
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
            )

            checkpoint_service = self._get_checkpoint_service()
            restored = await checkpoint_service.restore_checkpoint(
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
            )

            if not restored:
                record_hitl_checkpoint_load_error("checkpoint_not_found")
                record_hitl_resume_error("checkpoint_not_found")
                record_hitl_checkpoint_load_error("not_found")
                raise ValueError(self._ERR_CHECKPOINT_NOT_FOUND.format(thread_id=thread_id))

            # The checkpointer's OWN config is the authoritative resume
            # identity (thread_id + checkpoint_ns + checkpoint_id). Never
            # rebuild it from thread_id alone -- see CheckpointRestore.
            resume_config = restored.config

            # 5. Extract state purely for observability/audit. The graph
            # itself resumes from the checkpoint LangGraph already holds; we
            # deliberately do NOT push a whole rebuilt state back into it.
            restored_state = checkpoint_service.extract_state(restored.checkpoint)

            logger.info(
                "resume_prepared",
                review_id=str(review_id),
                decision=request.decision.value,
                checkpoint_id=restored.checkpoint_id,
                feedback_length=len(request.feedback),
                restored_state_keys=sorted(restored_state.keys()),
            )

            # 6. Claim this review for exactly ONE resume attempt.
            #
            # C2PRO P0b true-resume hotfix (exactly-once): this MUST happen
            # before any graph work, and it deliberately does not mutate
            # current_status. Reproduced defect: two approve calls -- whether
            # sequential or concurrent -- each drove the graph to completion,
            # running N17 twice and persisting two analyses and two
            # graph.completed events. The claim commits in its own short
            # transaction (see resume_claim) so it is immediately visible to
            # other API workers and holds no lock across the graph run.
            claim_token = str(uuid4())
            claimed = await claim_resume(
                row_id=self._row_id_for(review_item, review_id),
                tenant_id=self._tenant_id_for(review_item),
                checkpoint_id=restored.checkpoint_id,
                token=claim_token,
                claimed_at=datetime.now(UTC).isoformat(),
                session_factory=self._claim_session_factory,
            )
            if not claimed:
                record_hitl_resume_error("already_claimed")
                raise ValueError(self._ERR_ALREADY_CLAIMED.format(review_id=review_id))

            # 7. Resume the EXACT interrupted checkpoint (TASK-BCK-031).
            graph_app = self._get_graph_app()
            status_message = "resumed" if request.decision == WorkflowDecision.APPROVE else "rejected"

            try:
                logger.info(
                    "resuming_workflow",
                    review_id=str(review_id),
                    thread_id=thread_id,
                    checkpoint_id=restored.checkpoint_id,
                    decision=decision,
                )

                # Command(resume=...) is the supported interrupt-resume
                # primitive for the installed langgraph 1.2.10 -- verified
                # empirically against a real compiled graph and a real
                # AsyncPostgresSaver. The previous
                # `aupdate_state(...)` + `ainvoke(None, ...)` pattern did NOT
                # resume: it re-entered human_interrupt_node from the top,
                # hit interrupt() again, and returned another __interrupt__
                # without ever reaching N17 -- exactly the production
                # symptom (decision recorded, no analysis, document stuck at
                # parsed_pending_analysis).
                resumed_state = await graph_app.ainvoke(
                    Command(
                        resume={
                            "decision": request.decision.value,
                            "feedback": request.feedback,
                        }
                    ),
                    resume_config,
                )

                # A resume that did not actually consume the interrupt is a
                # FAILURE, not a success. LangGraph reports that by handing
                # back another __interrupt__ (and a wrong/stale checkpoint
                # silently returns without running anything at all), so an
                # unchecked call would look identical to a real completion.
                self._assert_interrupt_consumed(
                    resumed_state, review_id=review_id, thread_id=thread_id
                )

                if request.decision == WorkflowDecision.APPROVE:
                    self._assert_downstream_completed(
                        resumed_state, review_id=review_id, thread_id=thread_id
                    )

                logger.info(
                    "workflow_resumed",
                    review_id=str(review_id),
                    thread_id=thread_id,
                    status=status_message,
                    analysis_id=(resumed_state or {}).get("analysis_id"),
                )

            except Exception as e:
                logger.error(
                    "workflow_resumption_failed",
                    review_id=str(review_id),
                    thread_id=thread_id,
                    error=str(e),
                    exc_info=True,
                )
                record_hitl_resume_error("workflow_error")
                record_hitl_workflow_resume_error(decision)
                # C2PRO P0b true-resume hotfix (atomicity): the decision is
                # NOT recorded on a failed resume. Previously the review was
                # flipped to APPROVED before the graph ran and graph failures
                # were swallowed, so the system claimed a successful approval
                # while N17 had never executed. Release the claim so the
                # review stays genuinely pending and retryable, and let the
                # caller surface a truthful error.
                await release_resume_claim(
                    row_id=self._row_id_for(review_item, review_id),
                    tenant_id=self._tenant_id_for(review_item),
                    token=claim_token,
                    session_factory=self._claim_session_factory,
                )
                raise

            # 8. Durable completion reached -- only NOW record the decision.
            if request.decision == WorkflowDecision.APPROVE:
                review_item.current_status = ReviewStatus.APPROVED
            else:
                review_item.current_status = ReviewStatus.REJECTED
            review_item.approved_at = datetime.now(UTC)
            if request.approved_by:
                review_item.approved_by = request.approved_by
            review_item.metadata["review_decision"] = request.feedback
            review_item.metadata["resume_checkpoint_id"] = restored.checkpoint_id
            await self.review_queue_repo.update_review_item(review_item)

            if request.decision == WorkflowDecision.APPROVE:
                # Resuming to completion runs N17 (save_to_db), which persists
                # the analysis -- but N17 never touches Document.upload_status
                # (that transition normally happens in _run_document_analysis,
                # a code path this resume never goes through). Without this an
                # approved, fully-analyzed document stayed
                # parsed_pending_analysis forever and Health/Evidence never
                # became readable.
                await self._mark_document_analyzed_after_resume(
                    review_id=review_id,
                    review_item=review_item,
                    resumed_state=resumed_state,
                )

            # Record success metrics + audit event
            duration = time.perf_counter() - start_time
            record_hitl_resume_attempt(decision, status_message)
            record_hitl_resume_latency(decision, duration)

            logger.info(
                "hitl_decision_recorded",
                review_id=str(review_id),
                thread_id=thread_id,
                decision=decision,
                status=status_message,
                latency_seconds=round(duration, 4),
                feedback_length=len(request.feedback),
            )

            return ResumeWorkflowResponse(
                review_id=review_id,
                status=status_message,
                message=f"Workflow {status_message} with feedback: {request.feedback[:100]}",
            )

        except ValueError:
            duration = time.perf_counter() - start_time
            record_hitl_resume_latency(decision, duration)
            raise
