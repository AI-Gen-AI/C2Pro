"""V3 fenced ownership for HITL resume operations.

C2PRO P0b crash-safe HITL resume V3, sections 2-4.

Why fencing and not just a lease
--------------------------------
A lease alone cannot make a distributed resume safe. A worker can lose its
lease (GC pause, network partition, a stopped container that later resumes)
and keep computing with stale in-memory state. V2 had this hole: after a
takeover, the operation row looked the same to both workers, so the stale
one could still write.

V3 gives every attempt a monotonic ``fencing_token``. Ownership is proven,
not assumed: every durable writer re-reads the operation row inside ITS OWN
persistence transaction and refuses to write unless the operation still
names that exact attempt/owner/fence AND the lease is still valid. A stale
worker may therefore continue to compute indefinitely -- it simply cannot
persist anything.

Timing rules
------------
All ownership timing uses PostgreSQL ``clock_timestamp()``, never
application time and never ``now()``/``CURRENT_TIMESTAMP``. ``now()`` is
transaction-start time: inside a long transaction it never advances, so a
lease compared against it would look permanently fresh. Application time
would additionally make ownership depend on clock skew between workers.

Transaction rules
-----------------
Ownership only ever uses SHORT transactions. No session-scoped advisory
lock, and no database connection is held while LangGraph runs -- the graph
opens its own sessions, and holding one across it deadlocks (the request
cannot commit until the graph returns; the graph cannot proceed until the
request commits).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import text

logger = structlog.get_logger()

DEFAULT_LEASE_SECONDS = 120
MAX_FAILURES_BEFORE_OPERATOR = 5


class Phase(StrEnum):
    """Durable lifecycle of one resume operation."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    # N17's business effects are durable and operation-keyed.
    N17_DURABLE = "N17_DURABLE"
    # The graph reached a verified terminal checkpoint.
    GRAPH_COMPLETED = "GRAPH_COMPLETED"
    FINALIZED_APPROVED = "FINALIZED_APPROVED"
    FINALIZED_REJECTED = "FINALIZED_REJECTED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    # Bounded repeated failure or a corrupted invariant: never fabricate
    # success, never keep retrying blindly. A human must look.
    OPERATOR_REQUIRED = "OPERATOR_REQUIRED"


TERMINAL_PHASES = {
    Phase.FINALIZED_APPROVED,
    Phase.FINALIZED_REJECTED,
    Phase.OPERATOR_REQUIRED,
}


class AttemptOutcome(StrEnum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    ABANDONED = "ABANDONED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class Ownership:
    """Proof that this process owns this operation right now.

    Carried into the graph and re-verified inside every durable write.
    """

    operation_id: UUID
    attempt_id: UUID
    owner_token: UUID
    fencing_token: int
    decision_revision: int
    tenant_id: UUID
    review_row_id: UUID
    decision: str
    phase: Phase
    source_checkpoint_id: str | None
    terminal_checkpoint_id: str | None
    analysis_id: UUID | None
    project_id: UUID | None
    document_id: UUID | None
    failure_count: int

    def as_graph_provenance(self) -> dict[str, str]:
        """The provenance every descendant checkpoint must carry."""
        return {
            "operation_id": str(self.operation_id),
            "attempt_id": str(self.attempt_id),
            "owner_token": str(self.owner_token),
            "fencing_token": str(self.fencing_token),
            "decision_revision": str(self.decision_revision),
        }


def decision_hash(decision: str, feedback: str) -> str:
    """Stable identity of WHAT was decided, for revision detection."""
    return hashlib.sha256(f"{decision}\x00{feedback}".encode()).hexdigest()


class OwnershipError(RuntimeError):
    """The caller does not (or no longer) owns this operation."""


class OperatorRequired(RuntimeError):
    """State needs a human; never retried automatically, never faked."""


# ── SQL ──────────────────────────────────────────────────────────────────────
# Every statement below is a compare-and-set: the WHERE clause names the
# exact state the caller believes it is transitioning FROM.

_UPSERT_OPERATION_SQL = text(
    """
    INSERT INTO resume_operations (
        id, tenant_id, review_row_id, project_id, document_id, thread_id,
        source_checkpoint_id, fencing_token, decision_revision, decision,
        decision_hash, reviewer, phase, failure_count, operation_metadata,
        created_at, updated_at
    )
    VALUES (
        cast(:id as uuid), cast(:tenant_id as uuid), cast(:review_row_id as uuid),
        cast(:project_id as uuid), cast(:document_id as uuid), cast(:thread_id as text),
        cast(:source_checkpoint_id as text), 0, 1, cast(:decision as text),
        cast(:decision_hash as text), cast(:reviewer as text), 'PENDING', 0, '{}'::jsonb,
        clock_timestamp(), clock_timestamp()
    )
    ON CONFLICT (review_row_id) DO NOTHING
    RETURNING id
    """
)

_LOAD_OPERATION_SQL = text(
    """
    SELECT id, tenant_id, review_row_id, project_id, document_id, thread_id,
           source_checkpoint_id, terminal_checkpoint_id, current_attempt_id,
           owner_token, fencing_token, decision_revision, decision,
           decision_hash, reviewer, phase, analysis_id, failure_count,
           (lease_expires_at IS NULL OR lease_expires_at <= clock_timestamp())
               AS lease_expired
      FROM resume_operations
     WHERE review_row_id = cast(:review_row_id as uuid)
       AND tenant_id = cast(:tenant_id as uuid)
    """
)

# Acquire (or take over) ownership. Succeeds only when the operation is
# genuinely acquirable: never owned, lease genuinely expired per
# clock_timestamp(), or explicitly retryable. Bumping the fence here is what
# invalidates any previous owner still running.
_ACQUIRE_SQL = text(
    """
    UPDATE resume_operations
       SET current_attempt_id = cast(:attempt_id as uuid),
           owner_token = cast(:owner_token as uuid),
           fencing_token = fencing_token + 1,
           decision_revision = decision_revision + cast(:revision_bump as integer),
           decision = cast(:decision as text),
           decision_hash = cast(:decision_hash as text),
           reviewer = coalesce(cast(:reviewer as text), reviewer),
           -- Taking ownership must not erase durable progress. A takeover
           -- of an operation whose N17 already committed, or which already
           -- reached a verified terminal checkpoint, inherits that phase;
           -- resetting it to RUNNING would tell the new owner "the graph
           -- never ran" and make it replay N17. Only a not-yet-durable
           -- attempt starts over as RUNNING.
           phase = CASE
                     WHEN phase IN ('N17_DURABLE', 'GRAPH_COMPLETED') THEN phase
                     ELSE 'RUNNING'
                   END,
           lease_expires_at = clock_timestamp()
                              + make_interval(secs => cast(:lease_seconds as double precision)),
           heartbeat_at = clock_timestamp(),
           updated_at = clock_timestamp()
     WHERE id = cast(:operation_id as uuid)
       AND tenant_id = cast(:tenant_id as uuid)
       AND phase NOT IN ('FINALIZED_APPROVED', 'FINALIZED_REJECTED', 'OPERATOR_REQUIRED')
       AND (
             owner_token IS NULL
             OR lease_expires_at IS NULL
             OR lease_expires_at <= clock_timestamp()
             OR phase = 'FAILED_RETRYABLE'
             OR cast(:force_revision as boolean)
           )
    RETURNING id, current_attempt_id, owner_token, fencing_token, decision_revision,
              decision, phase, source_checkpoint_id, terminal_checkpoint_id,
              analysis_id, project_id, document_id, review_row_id, tenant_id,
              failure_count
    """
)

_SUPERSEDE_PRIOR_ATTEMPTS_SQL = text(
    """
    UPDATE resume_operation_attempts
       SET outcome = 'SUPERSEDED', ended_at = clock_timestamp(),
           reason = coalesce(reason, cast(:reason as text))
     WHERE operation_id = cast(:operation_id as uuid)
       AND outcome = 'ACTIVE'
       AND fencing_token < cast(:fencing_token as bigint)
    """
)

_INSERT_ATTEMPT_SQL = text(
    """
    INSERT INTO resume_operation_attempts (
        id, tenant_id, operation_id, owner_token, fencing_token,
        decision_revision, decision, decision_hash, reviewer,
        source_checkpoint_id, outcome, started_at
    )
    VALUES (
        cast(:id as uuid), cast(:tenant_id as uuid), cast(:operation_id as uuid),
        cast(:owner_token as uuid), cast(:fencing_token as bigint),
        cast(:decision_revision as integer), cast(:decision as text),
        cast(:decision_hash as text), cast(:reviewer as text),
        cast(:source_checkpoint_id as text), 'ACTIVE', clock_timestamp()
    )
    """
)

# Heartbeat is itself fenced: a superseded owner cannot resurrect its lease.
_HEARTBEAT_SQL = text(
    """
    UPDATE resume_operations
       SET lease_expires_at = clock_timestamp()
                              + make_interval(secs => cast(:lease_seconds as double precision)),
           heartbeat_at = clock_timestamp(),
           updated_at = clock_timestamp()
     WHERE id = cast(:operation_id as uuid)
       AND current_attempt_id = cast(:attempt_id as uuid)
       AND owner_token = cast(:owner_token as uuid)
       AND fencing_token = cast(:fencing_token as bigint)
       AND phase NOT IN ('FINALIZED_APPROVED', 'FINALIZED_REJECTED', 'OPERATOR_REQUIRED')
    RETURNING id
    """
)

# The authority check every durable writer performs INSIDE its own
# transaction, with FOR UPDATE so the row cannot change under it.
_VERIFY_OWNERSHIP_FOR_UPDATE_SQL = text(
    """
    SELECT id, phase, analysis_id, fencing_token, decision_revision,
           current_attempt_id, owner_token, project_id, document_id,
           review_row_id, terminal_checkpoint_id,
           (lease_expires_at IS NOT NULL AND lease_expires_at > clock_timestamp())
               AS lease_valid
      FROM resume_operations
     WHERE id = cast(:operation_id as uuid)
       AND tenant_id = cast(:tenant_id as uuid)
     FOR UPDATE
    """
)

_SET_PHASE_SQL = text(
    """
    UPDATE resume_operations
       SET phase = cast(:phase as text), updated_at = clock_timestamp()
     WHERE id = cast(:operation_id as uuid)
       AND current_attempt_id = cast(:attempt_id as uuid)
       AND fencing_token = cast(:fencing_token as bigint)
    RETURNING id
    """
)

# Releasing a failed attempt must NEVER destroy durable evidence.
#
# Once N17 has committed (N17_DURABLE) or a verified terminal checkpoint has
# been recorded (GRAPH_COMPLETED), those facts are true regardless of what
# killed the worker afterwards. Overwriting them with FAILED_RETRYABLE would
# tell recovery "the graph never ran" about a run that DID persist, and the
# retry would replay N17 -- reintroducing exactly the post-N17 split brain
# this design exists to prevent. So the phase is preserved for those two
# states and only the ownership (lease/owner) is released; the error and the
# backoff are still recorded, and OPERATOR_REQUIRED still wins on
# exhaustion, since that is a halt, not a loss of evidence.
_RECORD_FAILURE_SQL = text(
    """
    UPDATE resume_operations
       SET phase = CASE
                     WHEN failure_count + 1 >= cast(:max_failures as integer)
                       THEN 'OPERATOR_REQUIRED'
                     WHEN phase IN ('N17_DURABLE', 'GRAPH_COMPLETED')
                       THEN phase
                     ELSE 'FAILED_RETRYABLE'
                   END,
           failure_count = failure_count + 1,
           last_error = cast(:error as text),
           owner_token = NULL,
           lease_expires_at = NULL,
           next_attempt_at = clock_timestamp()
                             + make_interval(secs => least(
                                   cast(:base_backoff as double precision)
                                       * power(2, failure_count),
                                   3600)),
           updated_at = clock_timestamp()
     WHERE id = cast(:operation_id as uuid)
       AND current_attempt_id = cast(:attempt_id as uuid)
       AND fencing_token = cast(:fencing_token as bigint)
       AND phase NOT IN ('FINALIZED_APPROVED', 'FINALIZED_REJECTED')
    RETURNING phase, failure_count
    """
)

_CLOSE_ATTEMPT_SQL = text(
    """
    UPDATE resume_operation_attempts
       SET outcome = cast(:outcome as text),
           reason = cast(:reason as text),
           terminal_checkpoint_id = coalesce(
               cast(:terminal_checkpoint_id as text), terminal_checkpoint_id),
           ended_at = clock_timestamp()
     WHERE id = cast(:attempt_id as uuid)
    """
)


async def acquire(
    *,
    review_row_id: UUID,
    tenant_id: UUID,
    project_id: UUID | None,
    document_id: UUID | None,
    thread_id: str | None,
    source_checkpoint_id: str | None,
    decision: str,
    feedback: str,
    reviewer: str | None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    session_factory: Any = None,
) -> tuple[Ownership | None, Phase, str | None]:
    """Acquire fenced ownership, or explain why not.

    Returns (ownership, phase, reason). ``ownership`` is None when the
    caller may not run: another owner holds a live lease, the operation is
    already finalized, or it needs an operator.
    """
    new_hash = decision_hash(decision, feedback)

    async with _session(session_factory, tenant_id) as session:
        await session.execute(
            _UPSERT_OPERATION_SQL,
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "review_row_id": str(review_row_id),
                "project_id": str(project_id) if project_id else None,
                "document_id": str(document_id) if document_id else None,
                "thread_id": thread_id,
                "source_checkpoint_id": source_checkpoint_id,
                "decision": decision,
                "decision_hash": new_hash,
                "reviewer": reviewer,
            },
        )
        row = (
            await session.execute(
                _LOAD_OPERATION_SQL,
                {"review_row_id": str(review_row_id), "tenant_id": str(tenant_id)},
            )
        ).first()
        if row is None:
            return None, Phase.PENDING, "not_visible_for_tenant"

        phase = Phase(row.phase)
        if phase is Phase.OPERATOR_REQUIRED:
            return None, phase, "operator_required"
        if phase in {Phase.FINALIZED_APPROVED, Phase.FINALIZED_REJECTED}:
            return None, phase, "already_finalized"

        # A changed decision is a NEW revision -- but only before the
        # business effect is durable. Afterwards the decision is immutable.
        decision_changed = row.decision_hash is not None and row.decision_hash != new_hash
        if decision_changed and phase in {Phase.N17_DURABLE, Phase.GRAPH_COMPLETED}:
            return None, phase, "decision_immutable_after_n17"

        if not row.lease_expired and not decision_changed and row.owner_token is not None:
            return None, phase, "lease_held_by_other_owner"

        attempt_id, owner_token = uuid4(), uuid4()
        acquired = (
            await session.execute(
                _ACQUIRE_SQL,
                {
                    "operation_id": str(row.id),
                    "tenant_id": str(tenant_id),
                    "attempt_id": str(attempt_id),
                    "owner_token": str(owner_token),
                    "revision_bump": 1 if decision_changed else 0,
                    "decision": decision,
                    "decision_hash": new_hash,
                    "reviewer": reviewer,
                    "lease_seconds": lease_seconds,
                    "force_revision": decision_changed,
                },
            )
        ).first()
        if acquired is None:
            # Lost the race to a concurrent acquirer.
            return None, phase, "lost_acquire_race"

        # Everything from a lower fence is now historical and unusable.
        await session.execute(
            _SUPERSEDE_PRIOR_ATTEMPTS_SQL,
            {
                "operation_id": str(row.id),
                "fencing_token": int(acquired.fencing_token),
                "reason": "superseded_by_new_attempt",
            },
        )
        await session.execute(
            _INSERT_ATTEMPT_SQL,
            {
                "id": str(attempt_id),
                "tenant_id": str(tenant_id),
                "operation_id": str(row.id),
                "owner_token": str(owner_token),
                "fencing_token": int(acquired.fencing_token),
                "decision_revision": int(acquired.decision_revision),
                "decision": decision,
                "decision_hash": new_hash,
                "reviewer": reviewer,
                "source_checkpoint_id": row.source_checkpoint_id or source_checkpoint_id,
            },
        )

        ownership = Ownership(
            operation_id=_uuid(acquired.id),
            attempt_id=attempt_id,
            owner_token=owner_token,
            fencing_token=int(acquired.fencing_token),
            decision_revision=int(acquired.decision_revision),
            tenant_id=tenant_id,
            review_row_id=review_row_id,
            decision=decision,
            phase=Phase(acquired.phase),
            source_checkpoint_id=acquired.source_checkpoint_id or source_checkpoint_id,
            terminal_checkpoint_id=acquired.terminal_checkpoint_id,
            analysis_id=_uuid_or_none(acquired.analysis_id),
            project_id=_uuid_or_none(acquired.project_id),
            document_id=_uuid_or_none(acquired.document_id),
            failure_count=int(acquired.failure_count),
        )

    logger.info(
        "hitl_resume_ownership_acquired",
        operation_id=str(ownership.operation_id),
        attempt_id=str(ownership.attempt_id),
        fencing_token=ownership.fencing_token,
        decision_revision=ownership.decision_revision,
        prior_phase=phase.value,
        decision_changed=decision_changed,
    )
    return ownership, Phase(ownership.phase), None


async def load(
    *, review_row_id: UUID, tenant_id: UUID, session_factory: Any = None
) -> Any:
    async with _session(session_factory, tenant_id) as session:
        return (
            await session.execute(
                _LOAD_OPERATION_SQL,
                {"review_row_id": str(review_row_id), "tenant_id": str(tenant_id)},
            )
        ).first()


async def renew(
    *, ownership: Ownership, lease_seconds: int, session_factory: Any = None
) -> bool:
    async with _session(session_factory, ownership.tenant_id) as session:
        row = (
            await session.execute(
                _HEARTBEAT_SQL,
                {
                    "operation_id": str(ownership.operation_id),
                    "attempt_id": str(ownership.attempt_id),
                    "owner_token": str(ownership.owner_token),
                    "fencing_token": ownership.fencing_token,
                    "lease_seconds": lease_seconds,
                },
            )
        ).first()
    return row is not None


async def verify_in_transaction(session: Any, ownership: Ownership) -> Any:
    """Authority check for a durable writer, INSIDE its own transaction.

    Takes FOR UPDATE so the operation row cannot change while the write
    proceeds, and raises rather than returning a soft signal: a caller that
    forgets to check a boolean would silently become the stale writer this
    whole design exists to stop.
    """
    row = (
        await session.execute(
            _VERIFY_OWNERSHIP_FOR_UPDATE_SQL,
            {
                "operation_id": str(ownership.operation_id),
                "tenant_id": str(ownership.tenant_id),
            },
        )
    ).first()
    if row is None:
        raise OwnershipError(f"Resume operation {ownership.operation_id} not visible")
    if (
        _uuid_or_none(row.current_attempt_id) != ownership.attempt_id
        or _uuid_or_none(row.owner_token) != ownership.owner_token
        or int(row.fencing_token) != ownership.fencing_token
    ):
        raise OwnershipError(
            f"Fenced out: operation {ownership.operation_id} is now at fence "
            f"{row.fencing_token} (attempt {row.current_attempt_id}); this worker "
            f"holds fence {ownership.fencing_token}"
        )
    if not row.lease_valid:
        raise OwnershipError(
            f"Lease expired for operation {ownership.operation_id}; this worker "
            "no longer has authority to persist"
        )
    return row


async def set_phase(
    *, ownership: Ownership, phase: Phase, session: Any = None, session_factory: Any = None
) -> bool:
    params = {
        "operation_id": str(ownership.operation_id),
        "attempt_id": str(ownership.attempt_id),
        "fencing_token": ownership.fencing_token,
        "phase": phase.value,
    }
    if session is not None:
        return (await session.execute(_SET_PHASE_SQL, params)).first() is not None
    async with _session(session_factory, ownership.tenant_id) as own_session:
        return (await own_session.execute(_SET_PHASE_SQL, params)).first() is not None


async def record_failure(
    *,
    ownership: Ownership,
    error: str,
    base_backoff_seconds: float = 30.0,
    max_failures: int = MAX_FAILURES_BEFORE_OPERATOR,
    session_factory: Any = None,
) -> Phase | None:
    """Release ownership for retry, with bounded backoff.

    Never touches a phase that already carries durable business truth, and
    escalates to OPERATOR_REQUIRED rather than retrying forever.
    """
    async with _session(session_factory, ownership.tenant_id) as session:
        row = (
            await session.execute(
                _RECORD_FAILURE_SQL,
                {
                    "operation_id": str(ownership.operation_id),
                    "attempt_id": str(ownership.attempt_id),
                    "fencing_token": ownership.fencing_token,
                    "error": error[:2000],
                    "max_failures": max_failures,
                    "base_backoff": base_backoff_seconds,
                },
            )
        ).first()
        await session.execute(
            _CLOSE_ATTEMPT_SQL,
            {
                "attempt_id": str(ownership.attempt_id),
                "outcome": AttemptOutcome.FAILED.value,
                "reason": error[:2000],
                "terminal_checkpoint_id": None,
            },
        )
    return Phase(row.phase) if row is not None else None


async def close_attempt(
    *,
    ownership: Ownership,
    outcome: AttemptOutcome,
    reason: str | None = None,
    terminal_checkpoint_id: str | None = None,
    session: Any = None,
    session_factory: Any = None,
) -> None:
    params = {
        "attempt_id": str(ownership.attempt_id),
        "outcome": outcome.value,
        "reason": reason,
        "terminal_checkpoint_id": terminal_checkpoint_id,
    }
    if session is not None:
        await session.execute(_CLOSE_ATTEMPT_SQL, params)
        return
    async with _session(session_factory, ownership.tenant_id) as own_session:
        await own_session.execute(_CLOSE_ATTEMPT_SQL, params)


def _uuid(value: Any) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _uuid_or_none(value: Any) -> UUID | None:
    return None if value is None else _uuid(value)


def _session(session_factory: Any, tenant_id: UUID) -> Any:
    if session_factory is not None:
        return session_factory(tenant_id)
    from src.core.database import get_session_with_tenant

    return get_session_with_tenant(tenant_id)


# ── terminal marker (V3 section 9) ───────────────────────────────────────────

_MARK_TERMINAL_SQL = text(
    """
    UPDATE resume_operations
       SET phase = 'GRAPH_COMPLETED',
           terminal_checkpoint_id = cast(:terminal_checkpoint_id as text),
           updated_at = clock_timestamp()
     WHERE id = cast(:operation_id as uuid)
       AND current_attempt_id = cast(:attempt_id as uuid)
       AND owner_token = cast(:owner_token as uuid)
       AND fencing_token = cast(:fencing_token as bigint)
       AND phase = 'N17_DURABLE'
    RETURNING id, project_id, analysis_id
    """
)


async def mark_graph_completed(
    *,
    ownership: Ownership,
    terminal_checkpoint_id: str,
    document_id: str | None = None,
    session_factory: Any = None,
) -> bool:
    """Record that the graph reached a VERIFIED terminal checkpoint.

    C2PRO P0b crash-safe HITL resume V3, section 9. One short fenced
    transaction: it locks the operation, re-verifies that this exact
    attempt/owner/fence still owns it, appends ``graph.completed`` carrying
    operation+attempt provenance, stores the terminal checkpoint identity
    and advances N17_DURABLE -> GRAPH_COMPLETED, then commits once.

    A stale or superseded attempt cannot pass the CAS, so it can never emit
    ``graph.completed`` -- and the partial unique index on
    (resume_operation_id, event_type) makes a duplicate impossible even if
    two callers raced past everything else.
    """
    from datetime import UTC, datetime
    from uuid import uuid4 as _uuid4

    from src.analysis.application.persist_resume_analysis import GRAPH_COMPLETED_EVENT
    from src.temporal.adapters.persistence.models import ProjectEventORM

    async with _session(session_factory, ownership.tenant_id) as session:
        # Serialise against any concurrent finalizer/reconciler first.
        await verify_in_transaction(session, ownership)
        row = (
            await session.execute(
                _MARK_TERMINAL_SQL,
                {
                    "operation_id": str(ownership.operation_id),
                    "attempt_id": str(ownership.attempt_id),
                    "owner_token": str(ownership.owner_token),
                    "fencing_token": ownership.fencing_token,
                    "terminal_checkpoint_id": terminal_checkpoint_id,
                },
            )
        ).first()
        if row is None:
            # Not in N17_DURABLE, or no longer ours: emit nothing.
            return False

        now = datetime.now(UTC).replace(tzinfo=None)
        session.add(
            ProjectEventORM(
                event_id=_uuid4(),
                project_id=row.project_id,
                tenant_id=ownership.tenant_id,
                event_type=GRAPH_COMPLETED_EVENT,
                payload={
                    "analysis_id": str(row.analysis_id) if row.analysis_id else None,
                    "document_id": document_id,
                    "resume_operation_id": str(ownership.operation_id),
                    "resume_attempt_id": str(ownership.attempt_id),
                    "terminal_checkpoint_id": terminal_checkpoint_id,
                },
                actor="analysis_graph",
                evidence_refs=[],
                occurred_at=now,
                created_at=now,
                resume_operation_id=ownership.operation_id,
                resume_attempt_id=ownership.attempt_id,
            )
        )
        await session.flush()

    logger.info(
        "hitl_resume_graph_completed",
        operation_id=str(ownership.operation_id),
        attempt_id=str(ownership.attempt_id),
        terminal_checkpoint_id=terminal_checkpoint_id,
    )
    return True


# ── finalization (V3 section 10) ─────────────────────────────────────────────

_FINALIZE_REVIEW_SQL = text(
    """
    UPDATE review_items
       SET current_status = cast(:status as reviewstatus),
           approved_at = now(),
           approved_by = coalesce(cast(:approved_by as text), approved_by),
           review_decision = cast(:feedback as text),
           review_metadata = coalesce(review_metadata, '{}'::jsonb)
                             || jsonb_build_object(
                                    'resume_operation_id', cast(:operation_id as text),
                                    'resume_attempt_id', cast(:attempt_id as text),
                                    'terminal_checkpoint_id', cast(:terminal as text)
                                )
                             - 'resume_claim'
     WHERE id = cast(:review_row_id as uuid)
       AND tenant_id = cast(:tenant_id as uuid)
    RETURNING id
    """
)

_FINALIZE_DOCUMENT_SQL = text(
    """
    UPDATE documents
       SET upload_status = 'analyzed'
     WHERE id = cast(:document_id as uuid)
       AND tenant_id = cast(:tenant_id as uuid)
    RETURNING id
    """
)

_FINALIZE_OPERATION_SQL = text(
    """
    UPDATE resume_operations
       SET phase = cast(:phase as text), updated_at = clock_timestamp()
     WHERE id = cast(:operation_id as uuid)
       AND current_attempt_id = cast(:attempt_id as uuid)
       AND fencing_token = cast(:fencing_token as bigint)
    RETURNING id
    """
)


HITL_CORRECTION_EVENT = "hitl.correction"


@dataclass(frozen=True)
class FinalizedCorrection:
    """The durable ``hitl.correction`` a finalization committed.

    Returned so the caller can enqueue its snapshot AFTER commit -- the
    projection trigger stays outside the business transaction, exactly like
    ``analysis.persisted`` / ``graph.completed``.
    """

    event_id: UUID
    project_id: UUID


async def finalize_v3(
    *,
    ownership: Ownership,
    review_row_id: UUID,
    approved: bool,
    approved_by: str | None,
    feedback: str,
    document_id: UUID | None,
    review_item_id: UUID | None = None,
    session_factory: Any = None,
    fault: Any = None,
) -> FinalizedCorrection | None:
    """Commit the whole post-graph outcome in ONE fenced transaction.

    Approval additionally requires GRAPH_COMPLETED and an operation-keyed
    analysis: a clean success response must mean the graph truly finished
    AND the analysis is durable AND the review is decided AND the document
    is ANALYZED. Anything less rolls everything back and stays recoverable,
    which is what removes the old best-effort document update's ability to
    report a false success.

    C2PRO #649: the human decision's ``hitl.correction`` audit event is
    appended in this SAME transaction, keyed by ``resume_operation_id``.
    One operation exists per exact review row and finalizes at most once
    (the fenced CAS above), so the partial unique index on
    (resume_operation_id, event_type) makes "one effective final decision
    -> one correction" a database fact. Idempotent replays, double clicks
    and lost-response retries never reach this point, so they cannot append
    a second one; a genuinely new final decision is a new review row, hence
    a new operation, hence its own event.
    """
    async with _session(session_factory, ownership.tenant_id) as session:
        row = await verify_in_transaction(session, ownership)
        phase = Phase(row.phase)

        if approved:
            if phase is not Phase.GRAPH_COMPLETED:
                raise OwnershipError(
                    f"Cannot finalize approval: operation {ownership.operation_id} is "
                    f"in {phase.value}, not GRAPH_COMPLETED"
                )
            if row.analysis_id is None:
                raise OwnershipError(
                    f"Cannot finalize approval: operation {ownership.operation_id} has "
                    "no operation-keyed analysis"
                )
            if document_id is None:
                raise OwnershipError(
                    "Cannot finalize approval without a document to mark ANALYZED; "
                    "refusing to report success"
                )

        review = (
            await session.execute(
                _FINALIZE_REVIEW_SQL,
                {
                    "review_row_id": str(review_row_id),
                    "tenant_id": str(ownership.tenant_id),
                    "status": "APPROVED" if approved else "REJECTED",
                    "approved_by": approved_by,
                    "feedback": feedback,
                    "operation_id": str(ownership.operation_id),
                    "attempt_id": str(ownership.attempt_id),
                    "terminal": row.terminal_checkpoint_id,
                },
            )
        ).first()
        if review is None:
            raise RuntimeError(
                f"Finalization could not update review row {review_row_id}; nothing committed."
            )

        if approved:
            if fault is not None:
                await fault("document")
            document = (
                await session.execute(
                    _FINALIZE_DOCUMENT_SQL,
                    {
                        "document_id": str(document_id),
                        "tenant_id": str(ownership.tenant_id),
                    },
                )
            ).first()
            if document is None:
                raise RuntimeError(
                    f"Finalization could not mark document {document_id} ANALYZED; "
                    "nothing committed."
                )

        finalized = (
            await session.execute(
                _FINALIZE_OPERATION_SQL,
                {
                    "operation_id": str(ownership.operation_id),
                    "attempt_id": str(ownership.attempt_id),
                    "fencing_token": ownership.fencing_token,
                    "phase": (
                        Phase.FINALIZED_APPROVED.value
                        if approved
                        else Phase.FINALIZED_REJECTED.value
                    ),
                },
            )
        ).first()
        if finalized is None:
            raise RuntimeError(
                f"Finalization could not close operation {ownership.operation_id}; "
                "nothing committed."
            )

        await session.execute(
            _CLOSE_ATTEMPT_SQL,
            {
                "attempt_id": str(ownership.attempt_id),
                "outcome": AttemptOutcome.COMPLETED.value,
                "reason": None,
                "terminal_checkpoint_id": row.terminal_checkpoint_id,
            },
        )

        correction = _append_correction_event(
            session,
            ownership=ownership,
            project_id=_uuid_or_none(row.project_id),
            review_row_id=review_row_id,
            review_item_id=review_item_id,
            decision_revision=int(row.decision_revision),
            approved=approved,
            reviewer=approved_by,
        )
        await session.flush()

    logger.info(
        "hitl_resume_finalized_v3",
        operation_id=str(ownership.operation_id),
        approved=approved,
        correction_event_id=str(correction.event_id) if correction else None,
    )
    return correction


def _append_correction_event(
    session: Any,
    *,
    ownership: Ownership,
    project_id: UUID | None,
    review_row_id: UUID,
    review_item_id: UUID | None,
    decision_revision: int,
    approved: bool,
    reviewer: str | None,
) -> FinalizedCorrection | None:
    """Stage the final decision's audit event on the finalizing session.

    A review with no project has no project timeline to correct -- the same
    skip the router has always applied -- so nothing is emitted for it.
    """
    if project_id is None:
        logger.info(
            "hitl_correction_skipped_no_project",
            operation_id=str(ownership.operation_id),
        )
        return None

    from datetime import UTC, datetime

    from src.temporal.adapters.persistence.models import ProjectEventORM

    decision = "APPROVED" if approved else "REJECTED"
    event_id = uuid4()
    now = datetime.now(UTC).replace(tzinfo=None)
    session.add(
        ProjectEventORM(
            event_id=event_id,
            project_id=project_id,
            tenant_id=ownership.tenant_id,
            event_type=HITL_CORRECTION_EVENT,
            payload={
                "review_item_id": str(review_item_id or review_row_id),
                "review_row_id": str(review_row_id),
                "decision": decision,
                "reviewer": reviewer,
                "resume_operation_id": str(ownership.operation_id),
                "resume_attempt_id": str(ownership.attempt_id),
                "decision_revision": decision_revision,
            },
            actor=reviewer,
            evidence_refs=[],
            occurred_at=now,
            created_at=now,
            resume_operation_id=ownership.operation_id,
            resume_attempt_id=ownership.attempt_id,
        )
    )
    return FinalizedCorrection(event_id=event_id, project_id=project_id)
