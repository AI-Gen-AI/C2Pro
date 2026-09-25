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
from src.modules.hitl.adapters.persistence.resume_ownership import (
    DEFAULT_LEASE_SECONDS,
    FinalizedCorrection,
    Ownership,
    Phase,
    acquire,
    finalize_v3,
    mark_graph_completed,
    record_failure,
    renew,
)
from src.modules.hitl.adapters.persistence.resume_recovery import (
    RecoveryOutcome as RecoveryOutcome,
)
from src.modules.hitl.adapters.persistence.resume_recovery import (
    ResumeRecoveryRequest as ResumeRecoveryRequest,
)
from src.modules.hitl.adapters.persistence.resume_recovery import (
    acquire_for_reconciliation,
)
from src.modules.hitl.domain.entities import ReviewItem, ReviewStatus
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

    _DESCENDANT_SCAN_LIMIT = 50

    _ERR_NOT_FOUND = "Review item {review_id} not found"
    _ERR_ALREADY_CLAIMED = (
        "Review item {review_id} is already being resumed by another request"
    )
    _ERR_OPERATOR_REQUIRED = (
        "Review item {review_id} needs operator intervention and will not be "
        "resumed automatically"
    )
    _ERR_NOT_TERMINAL = (
        "Resume of review {review_id} (thread {thread_id}) did not reach a terminal "
        "graph state; refusing to report completion"
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

    async def _heartbeat_loop(self, ownership: Ownership) -> None:
        """Renew the lease while the graph runs.

        Without this, a genuinely healthy long-running resume would look
        abandoned once the TTL elapsed and could be taken over mid-flight.
        The lease therefore only expires when a worker actually stopped.

        Renewal is fenced like every other write: it only renews while this
        attempt is still the current one, so a worker that was taken over
        cannot resurrect its own lease.
        """
        interval = max(1.0, self._lease_seconds / 3)
        while True:
            await asyncio.sleep(interval)
            try:
                await renew(
                    ownership=ownership,
                    lease_seconds=self._lease_seconds,
                    session_factory=self._claim_session_factory,
                )
            except Exception:  # noqa: BLE001 - never let telemetry kill a resume
                logger.warning(
                    "hitl_resume_heartbeat_failed",
                    operation_id=str(ownership.operation_id),
                    attempt_id=str(ownership.attempt_id),
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


    @staticmethod
    def _enqueue_correction_snapshot(correction: FinalizedCorrection, tenant_id: UUID) -> None:
        """Fire-and-forget the snapshot for a committed correction event.

        Fail-open like every other projection trigger: the decision and its
        audit event are already durable, and the daily snapshot job still
        provides eventual coverage.
        """
        from src.core.tenants.types import require_tenant_id
        from src.temporal.application import project_snapshot_trigger
        from src.temporal.domain.project_snapshot import SnapshotTrigger

        try:
            project_snapshot_trigger.enqueue_project_snapshot(
                project_id=correction.project_id,
                tenant_id=require_tenant_id(tenant_id),
                trigger=SnapshotTrigger.HITL_CORRECTION,
                source_event_id=correction.event_id,
            )
        except Exception:  # noqa: BLE001 - never fail a recorded decision
            logger.warning(
                "hitl_correction_snapshot_enqueue_failed",
                event_id=str(correction.event_id),
                project_id=str(correction.project_id),
                exc_info=True,
            )

    @staticmethod
    def _project_id_for(review_item: Any) -> UUID | None:
        """The project this review belongs to (evidence, not a key)."""
        raw = (review_item.metadata or {}).get("project_id") or (
            review_item.item_data or {}
        ).get("project_id")
        return UUID(str(raw)) if raw else None

    async def _attempt_resume_config(
        self,
        *,
        checkpoint_service: CheckpointService,
        graph_app: Any,
        ownership: Ownership,
        thread_id: str,
        restored: Any,
    ) -> dict[str, Any]:
        """The exact checkpoint THIS ATTEMPT is entitled to resume from.

        Three selections are wrong here, and each corrupts the run in a
        different way:

        * latest-by-thread -- adopts whatever the last writer left, which
          after a partial crashed attempt is a half-advanced state that no
          longer contains the interrupt.
        * operation-only -- matches descendants of a SUPERSEDED attempt
          (same operation, older fence), so a takeover would silently
          continue the dead worker's in-flight state.
        * a superseded attempt's descendant after a decision change --
          resuming those would apply the OLD decision.

        So: prefer a descendant written by this exact attempt (an in-process
        retry of the same attempt legitimately continues where it left off),
        identified by the provenance the attempt itself stamped into state.
        Otherwise restart from ``source_checkpoint_id`` -- the IMMUTABLE
        original human-interrupt checkpoint recorded when the operation was
        first created, which is the only checkpoint a takeover may adopt.
        """
        descendant = await self._attempt_descendant_config(
            checkpoint_service=checkpoint_service,
            ownership=ownership,
            thread_id=thread_id,
        )
        if descendant is not None:
            logger.info(
                "hitl_resume_continuing_own_attempt",
                operation_id=str(ownership.operation_id),
                attempt_id=str(ownership.attempt_id),
                checkpoint_id=descendant["configurable"].get("checkpoint_id"),
            )
            return descendant

        source_id = ownership.source_checkpoint_id
        if source_id and source_id != restored.checkpoint_id:
            # A takeover after a superseded attempt advanced the thread:
            # `restored` is the LATEST checkpoint, which is not ours. Pin
            # the operation's immutable interrupt checkpoint instead.
            logger.info(
                "hitl_resume_restarting_from_source_checkpoint",
                operation_id=str(ownership.operation_id),
                attempt_id=str(ownership.attempt_id),
                source_checkpoint_id=source_id,
                latest_checkpoint_id=restored.checkpoint_id,
            )
            config = dict(restored.config)
            configurable = dict(config.get("configurable") or {})
            configurable["checkpoint_id"] = source_id
            configurable.setdefault("thread_id", thread_id)
            config["configurable"] = configurable
            return config

        # Otherwise this attempt starts from the immutable interrupt
        # checkpoint -- via a FORK, never the checkpoint itself. See
        # _fork_for_attempt: re-resuming a checkpoint replays the FIRST
        # attempt's resume payload.
        base: dict[str, Any] = restored.config
        return await self._fork_for_attempt(
            graph_app=graph_app, base=base, ownership=ownership
        )

    async def _fork_for_attempt(
        self, *, graph_app: Any, base: dict[str, Any], ownership: Ownership
    ) -> dict[str, Any]:
        """Give this attempt its OWN checkpoint to resume from.

        LangGraph stores a `Command(resume=...)` payload as a `__resume__`
        write against the checkpoint being resumed, and a SECOND resume of
        that same checkpoint re-delivers the FIRST payload -- verified
        empirically against langgraph 1.2.10 + AsyncPostgresSaver.

        That is fatal for a takeover: the new attempt would run with the
        SUPERSEDED attempt's provenance, be fenced out at N17 (its fence is
        stale), fail, be retried, and be fenced out again -- a livelock in
        which the operation can never complete. Recovery is not optional
        here, so the payload must be the new attempt's own.

        Forking writes a CHILD of the interrupt checkpoint, so the original
        stays immutable (it remains the audit record of what the human saw
        and the only checkpoint takeovers restart from), while this attempt
        gets a lineage with no prior resume write. The fork carries the
        attempt's provenance, which is also what lets a later retry of THIS
        attempt recognise its own descendants.
        """
        aupdate_state = getattr(graph_app, "aupdate_state", None)
        if aupdate_state is None:
            return base
        try:
            fork = await aupdate_state(
                base, {"resume_provenance": ownership.as_graph_provenance()}
            )
        except Exception:  # noqa: BLE001
            # Fail open to the base checkpoint: for a FIRST attempt (no
            # prior resume write) that is still correct, and a takeover
            # that cannot fork is caught by the fence at N17 rather than
            # being allowed to write.
            logger.warning(
                "hitl_resume_attempt_fork_failed",
                operation_id=str(ownership.operation_id),
                attempt_id=str(ownership.attempt_id),
                exc_info=True,
            )
            return base
        # A fork is only usable if it actually came back as a config naming a
        # checkpoint. Anything else (None, a stub) is treated as "could not
        # fork" rather than trusted: passing it to ainvoke would resume the
        # WRONG thing, which is far worse than resuming the base checkpoint,
        # where a stale attempt is still stopped by the fence at N17.
        fork_checkpoint_id = (
            (fork.get("configurable") or {}).get("checkpoint_id")
            if isinstance(fork, dict)
            else None
        )
        if not fork_checkpoint_id:
            logger.warning(
                "hitl_resume_attempt_fork_unusable",
                operation_id=str(ownership.operation_id),
                attempt_id=str(ownership.attempt_id),
                returned=type(fork).__name__,
            )
            return base
        logger.info(
            "hitl_resume_attempt_forked",
            operation_id=str(ownership.operation_id),
            attempt_id=str(ownership.attempt_id),
            fencing_token=ownership.fencing_token,
            from_checkpoint_id=(base.get("configurable") or {}).get("checkpoint_id"),
            fork_checkpoint_id=fork_checkpoint_id,
        )
        forked: dict[str, Any] = fork
        return forked

    async def _attempt_descendant_config(
        self,
        *,
        checkpoint_service: CheckpointService,
        ownership: Ownership,
        thread_id: str,
    ) -> dict[str, Any] | None:
        """Newest checkpoint stamped with EXACTLY this attempt's provenance.

        All four fields must match. operation_id alone would match a
        superseded attempt; adding attempt_id/fencing_token/decision_revision
        makes "belongs to this attempt" unambiguous even when a takeover
        reuses the operation and even when the decision changed.
        """
        checkpointer = getattr(checkpoint_service, "checkpointer", None)
        alist = getattr(checkpointer, "alist", None)
        if alist is None:
            return None

        expected = ownership.as_graph_provenance()
        try:
            # alist yields newest-first, so the first match is the furthest
            # this attempt got.
            async for tup in alist(
                {"configurable": {"thread_id": thread_id}},
                limit=self._DESCENDANT_SCAN_LIMIT,
            ):
                values = (tup.checkpoint or {}).get("channel_values") or {}
                got = values.get("resume_provenance") or {}
                if not got:
                    continue
                if all(str(got.get(k)) == str(v) for k, v in expected.items()):
                    config = dict(tup.config)
                    configurable = dict(config.get("configurable") or {})
                    configurable["checkpoint_id"] = (tup.checkpoint or {}).get("id")
                    config["configurable"] = configurable
                    return config
        except Exception:  # noqa: BLE001 - selection falls back to the source
            logger.warning(
                "hitl_resume_descendant_scan_failed",
                operation_id=str(ownership.operation_id),
                exc_info=True,
            )
        return None

    async def _verified_terminal_checkpoint(
        self, *, graph_app: Any, config: dict[str, Any]
    ) -> str | None:
        """Checkpoint id of a VERIFIED graph END, or None.

        `ainvoke` returning normally is NOT evidence that the graph
        finished: it also returns when the run stopped at another interrupt,
        and a no-op resume of a stale checkpoint returns having executed
        nothing. The authority is LangGraph's own state: `next` empty means
        no task remains to run, i.e. END was reached.

        Returning None here is what keeps `graph.completed` truthful -- the
        caller refuses to report completion rather than emitting an event
        that recovery would later trust.
        """
        aget_state = getattr(graph_app, "aget_state", None)
        if aget_state is None:
            return None
        # Read the THREAD's latest state, not the pinned resume checkpoint:
        # the run advanced past it.
        configurable = dict(config.get("configurable") or {})
        configurable.pop("checkpoint_id", None)
        try:
            state = await aget_state({"configurable": configurable})
        except Exception:  # noqa: BLE001
            logger.warning("hitl_resume_terminal_state_unreadable", exc_info=True)
            return None
        if state is None:
            return None
        if getattr(state, "next", None):
            return None
        if getattr(state, "tasks", None):
            # Pending tasks (including an interrupt) mean the graph is still
            # mid-run even though `next` may be empty for this snapshot.
            return None
        return ((getattr(state, "config", None) or {}).get("configurable") or {}).get(
            "checkpoint_id"
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

            # `restored` carries the checkpointer's OWN config (thread_id +
            # checkpoint_ns + checkpoint_id), the authoritative resume
            # identity -- never rebuild one from thread_id alone (see
            # CheckpointRestore). WHICH checkpoint this attempt may resume
            # from is decided later by _attempt_resume_config, once
            # ownership is known.

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

            # 6. Acquire FENCED V3 ownership (sections 2-4).
            #
            # Decided from durable state, never from a lease alone: a worker
            # can die AFTER N17 committed but BEFORE finalization, so
            # "expired" must never be read as "the graph never ran". Every
            # attempt carries a monotonic fencing token that each durable
            # writer re-verifies inside its own transaction, so a worker
            # that lost its lease may keep computing but can never persist.
            row_id = self._row_id_for(review_item, review_id)
            tenant_id = self._tenant_id_for(review_item)
            document_id = self._document_id_for(review_item, {})
            project_id = self._project_id_for(review_item)

            ownership, phase, refusal = await acquire(
                review_row_id=row_id,
                tenant_id=tenant_id,
                project_id=project_id,
                document_id=document_id,
                thread_id=thread_id,
                source_checkpoint_id=restored.checkpoint_id,
                decision=request.decision.value,
                feedback=request.feedback,
                reviewer=request.approved_by,
                lease_seconds=self._lease_seconds,
                session_factory=self._claim_session_factory,
            )

            status_message = (
                "resumed" if request.decision == WorkflowDecision.APPROVE else "rejected"
            )

            if ownership is None:
                # The reason is the only thing that distinguishes "someone
                # else is working on it" from "this needs a human", so it is
                # logged rather than collapsed into the HTTP message.
                logger.info(
                    "hitl_resume_not_acquired",
                    review_id=str(review_id),
                    phase=phase.value if phase is not None else None,
                    reason=refusal,
                )
                if phase in {Phase.FINALIZED_APPROVED, Phase.FINALIZED_REJECTED}:
                    # Everything durable already landed (e.g. the process
                    # died after finalization but before the HTTP response).
                    # Idempotent replay: touch nothing, report the outcome.
                    record_hitl_resume_attempt(decision, "already_completed")
                    record_hitl_resume_latency(decision, time.perf_counter() - start_time)
                    return ResumeWorkflowResponse(
                        review_id=review_id,
                        status=status_message,
                        message=(
                            f"Workflow {status_message} (already completed; "
                            "idempotent replay)."
                        ),
                    )
                if phase is Phase.OPERATOR_REQUIRED:
                    record_hitl_resume_error("operator_required")
                    raise ValueError(self._ERR_OPERATOR_REQUIRED.format(review_id=review_id))
                record_hitl_resume_error("already_claimed")
                raise ValueError(self._ERR_ALREADY_CLAIMED.format(review_id=review_id))

            return await self._execute_owned(
                ownership=ownership, review_item=review_item, review_id=review_id,
                request=request, thread_id=thread_id, checkpoint_service=checkpoint_service,
                restored=restored, start_time=start_time, document_id=document_id,
            )
        except ValueError:
            duration = time.perf_counter() - start_time
            record_hitl_resume_latency(decision, duration)
            raise

    async def recover(self, expected: ResumeRecoveryRequest) -> RecoveryOutcome:
        """Complete a durable human decision, never create or revise one."""
        if getattr(self.review_queue_repo, "tenant_id", None) != expected.tenant_id:
            return RecoveryOutcome.NOT_VISIBLE
        claim = await acquire_for_reconciliation(
            expected, lease_seconds=self._lease_seconds,
            session_factory=self._claim_session_factory,
        )
        if claim.outcome is not RecoveryOutcome.ACQUIRED:
            return claim.outcome
        assert claim.ownership is not None and claim.review is not None
        assert claim.feedback is not None and claim.thread_id is not None
        await self._execute_owned(
            ownership=claim.ownership, review_item=claim.review,
            review_id=expected.review_row_id,
            request=ResumeWorkflowRequest(
                WorkflowDecision(claim.ownership.decision), claim.feedback, claim.reviewer,
            ),
            thread_id=claim.thread_id, checkpoint_service=self._get_checkpoint_service(),
            start_time=time.perf_counter(), document_id=claim.ownership.document_id,
        )
        return RecoveryOutcome.RECOVERED

    async def _execute_owned(
        self, *, ownership: Ownership, review_item: ReviewItem, review_id: UUID,
        request: ResumeWorkflowRequest, thread_id: str, checkpoint_service: Any,
        start_time: float, document_id: UUID | None, restored: Any = None,
    ) -> ResumeWorkflowResponse:
        """The shared V3 executor, entered only AFTER acquisition commits."""
        phase = ownership.phase
        row_id, tenant_id = ownership.review_row_id, ownership.tenant_id
        decision = request.decision.value
        status_message = "resumed" if request.decision == WorkflowDecision.APPROVE else "rejected"
        resumed_state: dict[str, Any] = {}
        terminal_checkpoint_id: str | None = None
        correction: FinalizedCorrection | None = None
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(ownership))
        try:
            if restored is None and phase is not Phase.GRAPH_COMPLETED:
                restored = await checkpoint_service.restore_checkpoint(
                    thread_id=thread_id, checkpoint_id=ownership.source_checkpoint_id,
                )
                if restored is None:
                    raise ValueError(self._ERR_CHECKPOINT_NOT_FOUND.format(thread_id=thread_id))
            if phase is Phase.GRAPH_COMPLETED:
                # Durable evidence says this operation already reached a
                # verified terminal checkpoint. Finalize only -- replaying
                # the graph here is the post-N17 split brain.
                logger.warning(
                    "hitl_resume_recovering_at_graph_completed",
                    review_id=str(review_id),
                    operation_id=str(ownership.operation_id),
                )
            else:
                # 7. Resume the checkpoint this ATTEMPT is entitled to.
                #
                # A takeover restarts from the IMMUTABLE original
                # human-interrupt checkpoint; it must never adopt a
                # superseded attempt's descendants (section 5).
                graph_app = self._get_graph_app()
                resume_config = await self._attempt_resume_config(
                    checkpoint_service=checkpoint_service,
                    graph_app=graph_app,
                    ownership=ownership,
                    thread_id=thread_id,
                    restored=restored,
                )
                logger.info(
                    "resuming_workflow",
                    review_id=str(review_id),
                    thread_id=thread_id,
                    checkpoint_id=restored.checkpoint_id,
                    decision=decision,
                    operation_id=str(ownership.operation_id),
                    attempt_id=str(ownership.attempt_id),
                    fencing_token=ownership.fencing_token,
                )

                # Command(resume=...) is the supported interrupt-resume
                # primitive for langgraph 1.2.10 (verified empirically).
                # The attempt's provenance rides along so every
                # descendant checkpoint, and N17's own write, belong to
                # exactly this attempt.
                resumed_state = await graph_app.ainvoke(
                    Command(
                        resume={
                            "decision": request.decision.value,
                            "feedback": request.feedback,
                            "resume_provenance": ownership.as_graph_provenance(),
                        }
                    ),
                    resume_config,
                )

                if self._fault is not None:
                    await self._fault("after_graph_before_terminal_marker")

                # A resume that did not consume the interrupt did not
                # advance: LangGraph reports that by returning another
                # __interrupt__ rather than raising, and a wrong/stale
                # checkpoint silently returns having run nothing.
                self._assert_interrupt_consumed(
                    resumed_state, review_id=review_id, thread_id=thread_id
                )
                if request.decision == WorkflowDecision.APPROVE:
                    self._assert_downstream_completed(
                        resumed_state, review_id=review_id, thread_id=thread_id
                    )

                # 9. Terminal marker -- ONLY after a verified graph END.
                terminal_checkpoint_id = await self._verified_terminal_checkpoint(
                    graph_app=graph_app, config=resume_config
                )
                if request.decision == WorkflowDecision.APPROVE:
                    if terminal_checkpoint_id is None:
                        raise RuntimeError(
                            self._ERR_NOT_TERMINAL.format(
                                review_id=review_id, thread_id=thread_id
                            )
                        )
                    await mark_graph_completed(
                        ownership=ownership,
                        terminal_checkpoint_id=terminal_checkpoint_id,
                        document_id=str(document_id) if document_id else None,
                        session_factory=self._claim_session_factory,
                    )

                if self._fault is not None:
                    await self._fault("after_terminal_marker_before_finalize")

                logger.info(
                    "workflow_resumed",
                    review_id=str(review_id),
                    thread_id=thread_id,
                    status=status_message,
                    analysis_id=(resumed_state or {}).get("analysis_id"),
                    terminal_checkpoint_id=terminal_checkpoint_id,
                )

            # 10. Finalize: review + document + operation, ONE fenced
            # transaction. A clean success now means every durable state
            # exists -- the old best-effort document update could report
            # success while Health stayed unavailable.
            correction = await finalize_v3(
                ownership=ownership,
                review_row_id=row_id,
                approved=request.decision == WorkflowDecision.APPROVE,
                approved_by=request.approved_by,
                feedback=request.feedback,
                document_id=document_id,
                review_item_id=review_item.item_id,
                session_factory=self._claim_session_factory,
                fault=self._fault,
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
            # The decision is NOT recorded on failure. Releasing the
            # attempt never destroys durable evidence: a recorded
            # N17_DURABLE/GRAPH_COMPLETED phase survives, so a retry
            # finalizes instead of replaying N17.
            await record_failure(
                ownership=ownership,
                error=str(e),
                session_factory=self._claim_session_factory,
            )
            raise
        finally:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task

        # C2PRO #649: the decision's hitl.correction committed WITH the
        # finalization; only its snapshot projection is triggered here,
        # after commit, and only by the call that actually finalized --
        # a replay returns above and never reaches this line.
        if correction is not None:
            self._enqueue_correction_snapshot(correction, tenant_id)

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
