"""Durable, crash-recoverable state for one HITL workflow resume.

C2PRO P0b crash-safe HITL resume recovery.

The problem this replaces
-------------------------
The previous design committed an opaque ``resume_claim`` blob into
review_items.review_metadata before running the graph. It serialised
concurrent callers correctly, but it had no recovery story: if the worker
died after the claim and before the exception handler released it, the claim
stayed set forever and every later approval failed `already_claimed`. Worse,
a naive TTL on such a claim is actively dangerous -- a process can die AFTER
N17 durably committed the analysis but BEFORE the review was finalized, so
blindly re-running the graph on expiry risks a second N17.

The model
---------
One row per (review row, checkpoint) -- a UNIQUE index, with ``''`` rather
than NULL for a thread-only resume, because NULLs are distinct in a unique
index and would silently permit competing operations. The row is a small
state machine:

    CLAIMED           -- someone is (or was) running the graph
    GRAPH_COMPLETED   -- the graph durably crossed N17; analysis_id recorded
    FINALIZED         -- review + document + operation all durably committed
    FAILED_RETRYABLE  -- an attempt failed; safe to retry

Recovery reads the PHASE FIRST, never the lease alone:

* FINALIZED        -> return already-completed; touch nothing.
* GRAPH_COMPLETED  -> finalize only; the graph is NOT replayed.
* CLAIMED + live lease    -> another worker is healthy; refuse (concurrency).
* CLAIMED + expired lease -> take over and retry the graph. Safe even if the
  previous worker actually got further than we can see, because N17 is
  fenced by a stable idempotency key (see ``idempotency_key``).
* FAILED_RETRYABLE -> retry.

Every transition is a single atomic UPDATE guarded by the phase and/or token
it expects to find (compare-and-set), and each runs in its own short
transaction. That separation is mandatory, not stylistic: the HITL request
is one long transaction committed only after the endpoint returns, so a CAS
flushed there would be invisible to other workers, and a row lock held there
would deadlock against the graph's own sessions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import text

logger = structlog.get_logger()

# How long a claim stays valid without a heartbeat. The graph renews this
# while it runs, so the TTL only elapses when a worker genuinely stopped.
DEFAULT_LEASE_SECONDS = 120


class ResumePhase(StrEnum):
    CLAIMED = "CLAIMED"
    GRAPH_COMPLETED = "GRAPH_COMPLETED"
    FINALIZED = "FINALIZED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"


class ResumeAction(StrEnum):
    """What the caller should do, decided from durable state alone."""

    RUN_GRAPH = "RUN_GRAPH"
    FINALIZE_ONLY = "FINALIZE_ONLY"
    ALREADY_COMPLETED = "ALREADY_COMPLETED"
    BUSY = "BUSY"


@dataclass(frozen=True)
class ResumeOperation:
    id: UUID
    token: UUID
    review_row_id: UUID
    tenant_id: UUID
    checkpoint_key: str
    decision: str
    phase: ResumePhase
    analysis_id: UUID | None
    idempotency_key: str
    attempts: int


def build_idempotency_key(review_row_id: UUID, checkpoint_key: str) -> str:
    """Stable identity for the durable effects of one resume operation.

    Deliberately derived from the EXACT review row plus the EXACT checkpoint
    -- not the operation token, which changes on takeover, and not the
    project, which would collide with previous analyses, sibling reviews,
    other checkpoints and later reprocess/revisions.
    """
    return f"hitl-resume:{review_row_id}:{checkpoint_key or 'latest'}"


_CLAIM_SQL = text(
    """
    INSERT INTO hitl_resume_operations (
        id, tenant_id, review_row_id, checkpoint_key, thread_id, decision,
        phase, token, idempotency_key, attempts, operation_metadata,
        claimed_at, heartbeat_at, updated_at
    )
    VALUES (
        cast(:id as uuid), cast(:tenant_id as uuid), cast(:review_row_id as uuid),
        cast(:checkpoint_key as text), cast(:thread_id as text), cast(:decision as text),
        'CLAIMED', cast(:token as uuid), cast(:idempotency_key as text), 1,
        cast(:operation_metadata as jsonb), now(), now(), now()
    )
    ON CONFLICT (review_row_id, checkpoint_key) DO NOTHING
    RETURNING id, token, phase, analysis_id, idempotency_key, attempts, decision
    """
)

_LOAD_SQL = text(
    """
    SELECT id, token, phase, analysis_id, idempotency_key, attempts, decision,
           checkpoint_key,
           (heartbeat_at < now() - make_interval(secs => :lease_seconds)) AS lease_expired
      FROM hitl_resume_operations
     WHERE review_row_id = cast(:review_row_id as uuid)
       AND checkpoint_key = cast(:checkpoint_key as text)
       AND tenant_id = cast(:tenant_id as uuid)
    """
)

# Takeover is itself a CAS: it only succeeds while the row is still in the
# phase/lease state we decided to take over from, so two recovering workers
# cannot both win.
_TAKEOVER_SQL = text(
    """
    UPDATE hitl_resume_operations
       SET token = cast(:token as uuid),
           decision = cast(:decision as text),
           phase = 'CLAIMED',
           attempts = attempts + 1,
           heartbeat_at = now(),
           updated_at = now()
     WHERE review_row_id = cast(:review_row_id as uuid)
       AND checkpoint_key = cast(:checkpoint_key as text)
       AND tenant_id = cast(:tenant_id as uuid)
       AND (
             phase = 'FAILED_RETRYABLE'
             OR (phase = 'CLAIMED'
                 AND heartbeat_at < now() - make_interval(secs => :lease_seconds))
           )
    RETURNING id, token, phase, analysis_id, idempotency_key, attempts, decision
    """
)

_HEARTBEAT_SQL = text(
    """
    UPDATE hitl_resume_operations
       SET heartbeat_at = now(), updated_at = now()
     WHERE id = cast(:id as uuid) AND token = cast(:token as uuid)
    RETURNING id
    """
)

_MARK_GRAPH_COMPLETED_SQL = text(
    """
    UPDATE hitl_resume_operations
       SET phase = 'GRAPH_COMPLETED',
           analysis_id = cast(:analysis_id as uuid),
           heartbeat_at = now(),
           updated_at = now()
     WHERE id = cast(:id as uuid)
       AND token = cast(:token as uuid)
       AND phase IN ('CLAIMED', 'GRAPH_COMPLETED')
    RETURNING id
    """
)

_MARK_FAILED_SQL = text(
    """
    UPDATE hitl_resume_operations
       SET phase = 'FAILED_RETRYABLE',
           last_error = cast(:last_error as text),
           updated_at = now()
     WHERE id = cast(:id as uuid)
       AND token = cast(:token as uuid)
       AND phase = 'CLAIMED'
    RETURNING id
    """
)


async def begin_or_recover(
    *,
    review_row_id: UUID,
    tenant_id: UUID,
    checkpoint_id: str | None,
    thread_id: str | None,
    decision: str,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    session_factory: Any = None,
) -> tuple[ResumeOperation | None, ResumeAction]:
    """Decide, from durable state alone, what this caller may do."""
    checkpoint_key = checkpoint_id or ""
    idem = build_idempotency_key(review_row_id, checkpoint_key)
    token = uuid4()

    async with _session(session_factory, tenant_id) as session:
        inserted = (
            await session.execute(
                _CLAIM_SQL,
                {
                    "id": str(uuid4()),
                    "tenant_id": str(tenant_id),
                    "review_row_id": str(review_row_id),
                    "checkpoint_key": checkpoint_key,
                    "thread_id": thread_id,
                    "decision": decision,
                    "token": str(token),
                    "idempotency_key": idem,
                    "operation_metadata": "{}",
                },
            )
        ).first()
        if inserted is not None:
            return _to_operation(inserted, review_row_id, tenant_id, checkpoint_key), (
                ResumeAction.RUN_GRAPH
            )

        existing = (
            await session.execute(
                _LOAD_SQL,
                {
                    "review_row_id": str(review_row_id),
                    "checkpoint_key": checkpoint_key,
                    "tenant_id": str(tenant_id),
                    "lease_seconds": lease_seconds,
                },
            )
        ).first()
        if existing is None:
            # Another tenant owns this row (RLS/tenant predicate excluded it).
            return None, ResumeAction.BUSY

        phase = ResumePhase(existing.phase)
        operation = _to_operation(existing, review_row_id, tenant_id, checkpoint_key)

        # PHASE FIRST -- never the lease alone. This is what keeps a stale
        # claim from being mistaken for "the graph never ran".
        if phase is ResumePhase.FINALIZED:
            return operation, ResumeAction.ALREADY_COMPLETED
        if phase is ResumePhase.GRAPH_COMPLETED:
            return operation, ResumeAction.FINALIZE_ONLY
        if phase is ResumePhase.CLAIMED and not existing.lease_expired:
            return operation, ResumeAction.BUSY

        taken = (
            await session.execute(
                _TAKEOVER_SQL,
                {
                    "review_row_id": str(review_row_id),
                    "checkpoint_key": checkpoint_key,
                    "tenant_id": str(tenant_id),
                    "token": str(token),
                    "decision": decision,
                    "lease_seconds": lease_seconds,
                },
            )
        ).first()
        if taken is None:
            # Lost the takeover race to another recovering worker.
            return operation, ResumeAction.BUSY
        logger.warning(
            "hitl_resume_operation_taken_over",
            review_row_id=str(review_row_id),
            previous_phase=phase.value,
            attempts=taken.attempts,
        )
        return _to_operation(taken, review_row_id, tenant_id, checkpoint_key), (
            ResumeAction.RUN_GRAPH
        )


async def heartbeat(
    *, operation: ResumeOperation, session_factory: Any = None
) -> bool:
    """Renew the lease so a healthy long-running graph is never taken over."""
    async with _session(session_factory, operation.tenant_id) as session:
        row = (
            await session.execute(
                _HEARTBEAT_SQL,
                {"id": str(operation.id), "token": str(operation.token)},
            )
        ).first()
    return row is not None


async def mark_graph_completed(
    *, operation: ResumeOperation, analysis_id: UUID | None, session_factory: Any = None
) -> bool:
    """Record durable evidence that THIS operation crossed N17."""
    async with _session(session_factory, operation.tenant_id) as session:
        row = (
            await session.execute(
                _MARK_GRAPH_COMPLETED_SQL,
                {
                    "id": str(operation.id),
                    "token": str(operation.token),
                    "analysis_id": str(analysis_id) if analysis_id else None,
                },
            )
        ).first()
    logger.info(
        "hitl_resume_graph_completed",
        operation_id=str(operation.id),
        analysis_id=str(analysis_id) if analysis_id else None,
        recorded=row is not None,
    )
    return row is not None


async def mark_failed(
    *, operation: ResumeOperation, error: str, session_factory: Any = None
) -> bool:
    """Release the claim for retry WITHOUT asserting anything about effects.

    Only applies while the row is still CLAIMED: if the graph already
    reached GRAPH_COMPLETED, that evidence must survive the failure so a
    retry finalizes instead of replaying N17.
    """
    async with _session(session_factory, operation.tenant_id) as session:
        row = (
            await session.execute(
                _MARK_FAILED_SQL,
                {
                    "id": str(operation.id),
                    "token": str(operation.token),
                    "last_error": error[:2000],
                },
            )
        ).first()
    return row is not None


def _to_operation(
    row: Any, review_row_id: UUID, tenant_id: UUID, checkpoint_key: str
) -> ResumeOperation:
    return ResumeOperation(
        id=row.id if isinstance(row.id, UUID) else UUID(str(row.id)),
        token=row.token if isinstance(row.token, UUID) else UUID(str(row.token)),
        review_row_id=review_row_id,
        tenant_id=tenant_id,
        checkpoint_key=checkpoint_key,
        decision=str(row.decision),
        phase=ResumePhase(row.phase),
        analysis_id=(
            row.analysis_id
            if row.analysis_id is None or isinstance(row.analysis_id, UUID)
            else UUID(str(row.analysis_id))
        ),
        idempotency_key=str(row.idempotency_key),
        attempts=int(row.attempts),
    )


def _session(session_factory: Any, tenant_id: UUID) -> Any:
    if session_factory is not None:
        return session_factory(tenant_id)
    from src.core.database import get_session_with_tenant

    return get_session_with_tenant(tenant_id)


_FINALIZE_REVIEW_SQL = text(
    """
    UPDATE review_items
       SET current_status = cast(:status as reviewstatus),
           approved_at = now(),
           approved_by = coalesce(cast(:approved_by as text), approved_by),
           -- review_decision is a first-class COLUMN (the repository maps it
           -- out of the domain metadata), not a metadata key.
           review_decision = cast(:feedback as text),
           review_metadata = coalesce(review_metadata, '{}'::jsonb)
                             || jsonb_build_object(
                                    'resume_checkpoint_id', cast(:checkpoint_id as text)
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
    UPDATE hitl_resume_operations
       SET phase = 'FINALIZED', heartbeat_at = now(), updated_at = now()
     WHERE id = cast(:id as uuid)
       AND phase IN ('CLAIMED', 'GRAPH_COMPLETED')
    RETURNING id
    """
)


async def finalize(
    *,
    operation: ResumeOperation,
    review_row_id: UUID,
    tenant_id: UUID,
    status: str,
    approved_by: str | None,
    feedback: str,
    checkpoint_id: str | None,
    document_id: UUID | None,
    mark_document_analyzed: bool,
    session_factory: Any = None,
    fault: Any = None,
) -> None:
    """Commit the whole post-graph outcome in ONE transaction.

    Review decision, document status and the operation phase land together
    or not at all. That is what makes a clean success response truthful: it
    can no longer mean "review APPROVED but the document never became
    ANALYZED and Health stays unavailable", which the previous best-effort
    document update (it swallowed its own exceptions) allowed.

    On failure nothing commits and the operation stays GRAPH_COMPLETED, so
    recovery finalizes later WITHOUT re-running the graph.
    """
    async with _session(session_factory, tenant_id) as session:
        review = (
            await session.execute(
                _FINALIZE_REVIEW_SQL,
                {
                    "review_row_id": str(review_row_id),
                    "tenant_id": str(tenant_id),
                    "status": status,
                    "approved_by": approved_by,
                    "feedback": feedback,
                    "checkpoint_id": checkpoint_id,
                },
            )
        ).first()
        if review is None:
            raise RuntimeError(
                f"Finalization could not update review row {review_row_id}; nothing committed."
            )

        if mark_document_analyzed:
            if document_id is None:
                raise RuntimeError(
                    "Finalization requires a document_id to mark the document ANALYZED; "
                    "refusing to report success without it."
                )
            # Deterministic fault injection point (tests only): proves a
            # document-status failure aborts the WHOLE finalization rather
            # than being swallowed into a false success.
            if fault is not None:
                await fault("document")
            document = (
                await session.execute(
                    _FINALIZE_DOCUMENT_SQL,
                    {"document_id": str(document_id), "tenant_id": str(tenant_id)},
                )
            ).first()
            if document is None:
                raise RuntimeError(
                    f"Finalization could not mark document {document_id} ANALYZED; "
                    "nothing committed."
                )

        finalized = (
            await session.execute(
                _FINALIZE_OPERATION_SQL, {"id": str(operation.id)}
            )
        ).first()
        if finalized is None:
            raise RuntimeError(
                f"Finalization could not close resume operation {operation.id}; "
                "nothing committed."
            )

    logger.info(
        "hitl_resume_finalized",
        operation_id=str(operation.id),
        review_row_id=str(review_row_id),
        status=status,
    )
