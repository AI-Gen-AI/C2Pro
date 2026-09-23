"""
Use case for resuming LangGraph workflows after HITL approval/rejection.
Part of TASK-BCK-024: Implement HITL workflow resume mechanism after approval.
Part of TASK-BCK-031: Implement LangGraph checkpoint restoration for HITL resume workflow.
Refers to Suite ID: TS-BCK-032-001.
"""
from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

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
from src.modules.hitl.adapters.persistence.resume_operations import (
    DEFAULT_LEASE_SECONDS,
    ResumeAction,
    ResumeOperation,
    begin_or_recover,
    finalize,
    heartbeat,
    mark_failed,
    mark_graph_completed,
)
from src.modules.hitl.domain.entities import ReviewStatus
from src.modules.hitl.ports.review_queue_repository import IReviewQueueRepository

logger = structlog.get_logger()


def _as_uuid_or_none(value: Any) -> UUID | None:
    """Parse an analysis id defensively.

    The completion marker is evidence, not a foreign key: a state that
    carries an unparseable analysis id must not abort an otherwise healthy
    resume -- the phase transition itself is what recovery depends on.
    """
    if not value:
        return None
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        logger.warning("hitl_resume_unparseable_analysis_id", analysis_id=str(value))
        return None


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
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        fault: Any = None,
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
        # Optional injection point for the durable operation store's own
        # short-lived sessions (tests supply the test session factory).
        self._claim_session_factory = claim_session_factory
        self._lease_seconds = lease_seconds
        # Deterministic crash-point injection (tests only). Called with a
        # named checkpoint; raising from it simulates hard process loss at
        # that exact durability boundary.
        self._fault = fault

    async def _heartbeat_loop(self, operation: ResumeOperation) -> None:
        """Renew the lease while the graph runs.

        Without this, a genuinely healthy long-running resume would look
        abandoned once the TTL elapsed and could be taken over mid-flight.
        The lease therefore only expires when a worker actually stopped.
        """
        interval = max(1.0, self._lease_seconds / 3)
        while True:
            await asyncio.sleep(interval)
            try:
                await heartbeat(
                    operation=operation, session_factory=self._claim_session_factory
                )
            except Exception:  # noqa: BLE001 - never let telemetry kill a resume
                logger.warning(
                    "hitl_resume_heartbeat_failed",
                    operation_id=str(operation.id),
                    exc_info=True,
                )

    @staticmethod
    def _document_id_for(review_item: Any, resumed_state: dict[str, Any]) -> UUID | None:
        """The document this review gates.

        Metadata first (set by human_interrupt_node), then the resumed
        state. Finalization refuses to report success when an approval
        cannot resolve it, rather than silently skipping the ANALYZED
        transition and leaving Health unavailable.
        """
        raw = (review_item.metadata or {}).get("document_id") or (
            review_item.item_data or {}
        ).get("document_id")
        if not raw and isinstance(resumed_state, dict):
            raw = resumed_state.get("document_id")
        return UUID(str(raw)) if raw else None

    @staticmethod
    def _row_id_for(review_item: Any, review_id: UUID) -> UUID:
        """The review's TRUE row primary key.

        metadata["row_id"] is the persistent row identity threaded through
        the domain layer (item_id is a business key and is NOT unique across
        legacy duplicates -- see SqlAlchemyReviewQueueRepository._to_domain).
        The operation must address the exact row, never a sibling.
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

            # 6. Begin or RECOVER a durable resume operation.
            #
            # C2PRO P0b crash-safe resume: this decides what to do from
            # DURABLE state, not from a lease alone. The previous opaque
            # review_metadata claim could be orphaned forever by a hard
            # process death, and a naive TTL on it was unsafe: a worker can
            # die AFTER N17 committed but BEFORE the review was finalized,
            # so "expired" must never be read as "the graph never ran".
            row_id = self._row_id_for(review_item, review_id)
            tenant_id = self._tenant_id_for(review_item)
            operation, action = await begin_or_recover(
                review_row_id=row_id,
                tenant_id=tenant_id,
                checkpoint_id=restored.checkpoint_id,
                thread_id=thread_id,
                decision=request.decision.value,
                lease_seconds=self._lease_seconds,
                session_factory=self._claim_session_factory,
            )

            if action is ResumeAction.BUSY or operation is None:
                record_hitl_resume_error("already_claimed")
                raise ValueError(self._ERR_ALREADY_CLAIMED.format(review_id=review_id))

            status_message = (
                "resumed" if request.decision == WorkflowDecision.APPROVE else "rejected"
            )

            if action is ResumeAction.ALREADY_COMPLETED:
                # Everything durable already landed (e.g. the process died
                # after finalization but before the HTTP response). Idempotent
                # replay: touch nothing, report the same outcome.
                record_hitl_resume_attempt(decision, "already_completed")
                record_hitl_resume_latency(decision, time.perf_counter() - start_time)
                return ResumeWorkflowResponse(
                    review_id=review_id,
                    status=status_message,
                    message=f"Workflow {status_message} (already completed; idempotent replay).",
                )

            resumed_state: dict[str, Any] = {}
            if action is ResumeAction.FINALIZE_ONLY:
                # Durable evidence says this operation already crossed N17.
                # Finalize WITHOUT touching the graph -- replaying it here is
                # exactly the post-N17/pre-finalization split brain.
                logger.warning(
                    "hitl_resume_recovering_after_graph_completion",
                    review_id=str(review_id),
                    operation_id=str(operation.id),
                    analysis_id=str(operation.analysis_id) if operation.analysis_id else None,
                )
                resumed_state = {
                    "analysis_id": str(operation.analysis_id) if operation.analysis_id else None
                }
            else:
                # 7. Resume the EXACT interrupted checkpoint (TASK-BCK-031).
                graph_app = self._get_graph_app()
                heartbeat_task = asyncio.create_task(self._heartbeat_loop(operation))
                try:
                    logger.info(
                        "resuming_workflow",
                        review_id=str(review_id),
                        thread_id=thread_id,
                        checkpoint_id=restored.checkpoint_id,
                        decision=decision,
                        operation_id=str(operation.id),
                        attempt=operation.attempts,
                    )

                    # Command(resume=...) is the supported interrupt-resume
                    # primitive for the installed langgraph 1.2.10 -- verified
                    # empirically against a real compiled graph and a real
                    # AsyncPostgresSaver. The previous
                    # `aupdate_state(...)` + `ainvoke(None, ...)` pattern did
                    # NOT resume: it re-entered human_interrupt_node from the
                    # top, hit interrupt() again, and returned another
                    # __interrupt__ without ever reaching N17.
                    #
                    # idempotency_key rides along so N17 itself is fenced: a
                    # replay of THIS operation adopts the analysis already
                    # committed instead of persisting a second one.
                    resumed_state = await graph_app.ainvoke(
                        Command(
                            resume={
                                "decision": request.decision.value,
                                "feedback": request.feedback,
                                "idempotency_key": operation.idempotency_key,
                            }
                        ),
                        resume_config,
                    )

                    if self._fault is not None:
                        await self._fault("after_graph_before_completion_marker")

                    # A resume that did not actually consume the interrupt is
                    # a FAILURE, not a success. LangGraph reports that by
                    # handing back another __interrupt__ (and a wrong/stale
                    # checkpoint silently returns without running anything at
                    # all), so an unchecked call looks identical to a real
                    # completion.
                    self._assert_interrupt_consumed(
                        resumed_state, review_id=review_id, thread_id=thread_id
                    )
                    if request.decision == WorkflowDecision.APPROVE:
                        self._assert_downstream_completed(
                            resumed_state, review_id=review_id, thread_id=thread_id
                        )

                    # Durable completion marker: written BEFORE finalization
                    # so a crash in between recovers as FINALIZE_ONLY.
                    analysis_id_raw = (resumed_state or {}).get("analysis_id")
                    await mark_graph_completed(
                        operation=operation,
                        analysis_id=_as_uuid_or_none(analysis_id_raw),
                        session_factory=self._claim_session_factory,
                    )

                    if self._fault is not None:
                        await self._fault("after_completion_marker_before_finalize")

                    logger.info(
                        "workflow_resumed",
                        review_id=str(review_id),
                        thread_id=thread_id,
                        status=status_message,
                        analysis_id=analysis_id_raw,
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
                    # The decision is NOT recorded on a failed resume. Mark
                    # the operation retryable -- but only while it is still
                    # CLAIMED, so a GRAPH_COMPLETED marker survives and a
                    # retry finalizes instead of replaying N17.
                    await mark_failed(
                        operation=operation,
                        error=str(e),
                        session_factory=self._claim_session_factory,
                    )
                    raise
                finally:
                    heartbeat_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await heartbeat_task

            # 8. Finalize: review + document + operation in ONE transaction.
            #
            # A clean success response now means EVERY durable state landed.
            # The old code updated the review, then best-effort updated the
            # document while swallowing its exceptions -- so an approval could
            # report success while the document never became ANALYZED and
            # Health stayed unavailable.
            await finalize(
                operation=operation,
                review_row_id=row_id,
                tenant_id=tenant_id,
                status=(
                    ReviewStatus.APPROVED.value
                    if request.decision == WorkflowDecision.APPROVE
                    else ReviewStatus.REJECTED.value
                ),
                approved_by=request.approved_by,
                feedback=request.feedback,
                checkpoint_id=restored.checkpoint_id,
                document_id=self._document_id_for(review_item, resumed_state),
                mark_document_analyzed=request.decision == WorkflowDecision.APPROVE,
                session_factory=self._claim_session_factory,
                fault=self._fault,
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
