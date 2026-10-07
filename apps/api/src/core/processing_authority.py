"""#711 document-processing authority: attempts, fencing tokens, DB-clock leases.

A document is processed by exactly one owner at a time. The owner is an
*attempt* -- ``attempt_id`` + ``owner_token`` + a monotonic ``fencing_token`` --
recorded on the single ``document_processing_operations`` row for the
document, together with the canonical ``revision_id``, processing
``generation`` and ``stage`` (INGESTION -> ANALYSIS) it was granted for.

Design (same shape as the HITL V3 resume fence, separate tables):

* **Acquire / takeover.** A worker may take the row only when nobody validly
  owns it: phase PENDING, or an owner whose lease has expired by
  ``clock_timestamp()``. Every grant mints a new attempt, a new owner token and
  ``fencing_token + 1``, which supersedes the previous attempt.
* **Recovery hand-off.** The recovery sweep claims (phase CLAIMED) and passes
  the exact authority in the task message; the replacement task *adopts* it
  (CLAIMED -> RUNNING). A redelivered copy of that message finds RUNNING and
  refuses -- starting never mints a fresh fence by itself.
* **Heartbeat** renews the lease only for the exact current attempt whose
  lease is still valid. A superseded or expired worker cannot renew.
* **Durable writes** call :func:`verify_in_transaction` inside the SAME
  transaction as the business mutation. It row-locks the operation (so a
  takeover waits for the write to finish, or the write waits for the
  takeover and then fails) and re-checks attempt, owner, fence, revision,
  generation, stage, phase and lease. Anything stale raises
  :class:`ProcessingAuthorityLost`; the caller rolls back.
* **New revision / explicit reprocess** call :func:`begin_generation`, which
  bumps the generation and the fence in the same transaction as the reset, so
  no earlier worker can ever write into the new generation.

All timing is PostgreSQL ``clock_timestamp()`` (never application time, and
never ``now()``, which is transaction start and would make a long transaction
look permanently fresh). Timestamps are naive UTC like the recovery index.

Graph nodes and completion hooks run deep inside the analysis worker, so the
active authority is also bound to a :class:`contextvars.ContextVar`;
:func:`fence_current` is a no-op outside a processing worker (API requests,
HITL resumes -- which carry their own V3 fence).
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator, Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import text

logger = structlog.get_logger()

LEASE_TTL_SECONDS = 300


class ProcessingStage(StrEnum):
    INGESTION = "INGESTION"
    ANALYSIS = "ANALYSIS"


class ProcessingPhase(StrEnum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AcquireOutcome(StrEnum):
    ACQUIRED = "acquired"
    BUSY = "busy"
    SUPERSEDED = "superseded"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingAuthorityLost(RuntimeError):
    """This attempt no longer owns the document's processing: fail closed."""


@dataclass(frozen=True)
class ProcessingAuthority:
    """The exact grant a worker holds; every durable write re-verifies it."""

    tenant_id: UUID
    document_id: UUID
    revision_id: UUID | None
    generation: int
    stage: ProcessingStage
    attempt_id: UUID
    owner_token: UUID
    fencing_token: int

    def to_message(self) -> dict[str, Any]:
        """JSON-safe form carried in a Celery message (recovery hand-off)."""
        return {
            "tenant_id": str(self.tenant_id),
            "document_id": str(self.document_id),
            "revision_id": str(self.revision_id) if self.revision_id else None,
            "generation": self.generation,
            "stage": self.stage.value,
            "attempt_id": str(self.attempt_id),
            "owner_token": str(self.owner_token),
            "fencing_token": self.fencing_token,
        }

    @classmethod
    def from_message(cls, raw: Mapping[str, Any] | None) -> ProcessingAuthority | None:
        if not raw:
            return None
        try:
            revision = raw.get("revision_id")
            return cls(
                tenant_id=UUID(str(raw["tenant_id"])),
                document_id=UUID(str(raw["document_id"])),
                revision_id=UUID(str(revision)) if revision else None,
                generation=int(raw["generation"]),
                stage=ProcessingStage(str(raw["stage"])),
                attempt_id=UUID(str(raw["attempt_id"])),
                owner_token=UUID(str(raw["owner_token"])),
                fencing_token=int(raw["fencing_token"]),
            )
        except (KeyError, TypeError, ValueError):
            return None


@dataclass(frozen=True)
class AcquireResult:
    outcome: AcquireOutcome
    authority: ProcessingAuthority | None = None
    generation: int | None = None


# ── SQL ───────────────────────────────────────────────────────────────────────

_SET_TENANT_SQL = text("SELECT set_config('app.current_tenant', :tenant, true)")

# #758: first row for every authority transaction that can take authority.
_LOCK_DOCUMENT_SQL = text(
    """
    SELECT id FROM documents
     WHERE id = CAST(:document_id AS uuid)
       AND tenant_id = CAST(:tenant_id AS uuid)
     FOR UPDATE
    """
)

_LOCK_SQL = text(
    """
    SELECT document_id, tenant_id, revision_id, generation, stage, phase,
           attempt_id, owner_token, fencing_token,
           (lease_expires_at IS NOT NULL
            AND lease_expires_at > (clock_timestamp() AT TIME ZONE 'UTC')) AS lease_valid
      FROM document_processing_operations
     WHERE document_id = CAST(:document_id AS uuid)
       AND tenant_id = CAST(:tenant_id AS uuid)
     FOR UPDATE
    """
)

_INSERT_SQL = text(
    """
    INSERT INTO document_processing_operations (
        document_id, tenant_id, revision_id, generation, stage, phase,
        fencing_token, created_at, updated_at
    ) VALUES (
        CAST(:document_id AS uuid), CAST(:tenant_id AS uuid), CAST(:revision_id AS uuid),
        :generation, :stage, 'PENDING', 0,
        clock_timestamp() AT TIME ZONE 'UTC', clock_timestamp() AT TIME ZONE 'UTC'
    )
    ON CONFLICT (document_id) DO NOTHING
    """
)

_GRANT_SQL = text(
    """
    UPDATE document_processing_operations
       SET attempt_id = CAST(:attempt_id AS uuid),
           owner_token = CAST(:owner_token AS uuid),
           fencing_token = fencing_token + 1,
           phase = :phase,
           revision_id = COALESCE(revision_id, CAST(:revision_id AS uuid)),
           lease_expires_at = (clock_timestamp() AT TIME ZONE 'UTC')
                              + make_interval(secs => :ttl),
           heartbeat_at = clock_timestamp() AT TIME ZONE 'UTC',
           attempt_count = attempt_count + 1,
           updated_at = clock_timestamp() AT TIME ZONE 'UTC'
     WHERE document_id = CAST(:document_id AS uuid)
       AND tenant_id = CAST(:tenant_id AS uuid)
    RETURNING revision_id, generation, stage, fencing_token
    """
)

_EXACT_PREDICATE = """
       document_id = CAST(:document_id AS uuid)
   AND tenant_id = CAST(:tenant_id AS uuid)
   AND attempt_id = CAST(:attempt_id AS uuid)
   AND owner_token = CAST(:owner_token AS uuid)
   AND fencing_token = :fencing_token
   AND generation = :generation
   AND stage = :stage
   AND revision_id IS NOT DISTINCT FROM CAST(:revision_id AS uuid)
"""

_ADOPT_SQL = text(
    f"""
    UPDATE document_processing_operations
       SET phase = 'RUNNING',
           lease_expires_at = (clock_timestamp() AT TIME ZONE 'UTC')
                              + make_interval(secs => :ttl),
           heartbeat_at = clock_timestamp() AT TIME ZONE 'UTC',
           updated_at = clock_timestamp() AT TIME ZONE 'UTC'
     WHERE {_EXACT_PREDICATE}
       AND phase = 'CLAIMED'
       AND lease_expires_at > (clock_timestamp() AT TIME ZONE 'UTC')
    RETURNING document_id
    """
)

_HEARTBEAT_SQL = text(
    f"""
    UPDATE document_processing_operations
       SET lease_expires_at = (clock_timestamp() AT TIME ZONE 'UTC')
                              + make_interval(secs => :ttl),
           heartbeat_at = clock_timestamp() AT TIME ZONE 'UTC'
     WHERE {_EXACT_PREDICATE}
       AND phase = 'RUNNING'
       AND lease_expires_at > (clock_timestamp() AT TIME ZONE 'UTC')
    RETURNING document_id
    """
)

# The discovery index only routes the recovery scan; authority lives above.
_INDEX_HEARTBEAT_SQL = text(
    """
    UPDATE system_recovery.document_work_index
       SET heartbeat_at = clock_timestamp() AT TIME ZONE 'UTC'
     WHERE document_id = CAST(:document_id AS uuid)
    """
)

_BEGIN_GENERATION_SQL = text(
    """
    INSERT INTO document_processing_operations (
        document_id, tenant_id, revision_id, generation, stage, phase,
        fencing_token, created_at, updated_at
    ) VALUES (
        CAST(:document_id AS uuid), CAST(:tenant_id AS uuid), CAST(:revision_id AS uuid),
        1, 'INGESTION', 'PENDING', 1,
        clock_timestamp() AT TIME ZONE 'UTC', clock_timestamp() AT TIME ZONE 'UTC'
    )
    ON CONFLICT (document_id) DO UPDATE
        SET generation = document_processing_operations.generation + 1,
            revision_id = COALESCE(EXCLUDED.revision_id,
                                   document_processing_operations.revision_id),
            stage = 'INGESTION',
            phase = 'PENDING',
            attempt_id = NULL,
            owner_token = NULL,
            fencing_token = document_processing_operations.fencing_token + 1,
            lease_expires_at = NULL,
            heartbeat_at = NULL,
            attempt_count = 0,
            outcome = NULL,
            last_error = NULL,
            updated_at = clock_timestamp() AT TIME ZONE 'UTC'
     WHERE document_processing_operations.tenant_id = EXCLUDED.tenant_id
       AND (
            CAST(:expected_revision_id AS uuid) IS NULL
            OR document_processing_operations.revision_id = CAST(:expected_revision_id AS uuid)
       )
       AND (
            CAST(:expected_generation AS bigint) IS NULL
            OR document_processing_operations.generation = CAST(:expected_generation AS bigint)
       )
       AND (
            CAST(:expected_stage AS text) IS NULL
            OR document_processing_operations.stage = CAST(:expected_stage AS text)
       )
       AND (
            CAST(:expected_phase AS text) IS NULL
            OR document_processing_operations.phase = CAST(:expected_phase AS text)
       )
       AND (
            CAST(:expected_outcome AS text) IS NULL
            OR document_processing_operations.outcome = CAST(:expected_outcome AS text)
       )
    RETURNING generation
    """
)


def _exact_params(authority: ProcessingAuthority) -> dict[str, Any]:
    return {
        "document_id": str(authority.document_id),
        "tenant_id": str(authority.tenant_id),
        "attempt_id": str(authority.attempt_id),
        "owner_token": str(authority.owner_token),
        "fencing_token": authority.fencing_token,
        "generation": authority.generation,
        "stage": authority.stage.value,
        "revision_id": str(authority.revision_id) if authority.revision_id else None,
    }


async def _set_tenant(session: Any, tenant_id: UUID) -> None:
    # The operations table is FORCE-RLS; raw worker sessions carry no tenant.
    await session.execute(_SET_TENANT_SQL, {"tenant": str(tenant_id)})


async def _touch_index(
    session: Any, *, tenant_id: UUID, document_id: UUID, lock_document: bool = True
) -> None:
    """Refresh the discovery hint while preserving canonical lock order.

    Authority writers take documents -> discovery index -> authority row.
    Heartbeat is deliberately exempt from the document lock because it does
    not take an authority row lock and must not lose its lease while queued
    behind a long document transaction.
    """
    await _set_tenant(session, tenant_id)
    if lock_document:
        await _lock_document(session, tenant_id=tenant_id, document_id=document_id)
    await session.execute(_INDEX_HEARTBEAT_SQL, {"document_id": str(document_id)})


async def _lock_document(session: Any, *, tenant_id: UUID, document_id: UUID) -> None:
    """Lock the document before processing authority (#758 canonical order)."""
    await session.execute(
        _LOCK_DOCUMENT_SQL,
        {"document_id": str(document_id), "tenant_id": str(tenant_id)},
    )


async def _lock(session: Any, *, tenant_id: UUID, document_id: UUID) -> Any:
    await _set_tenant(session, tenant_id)
    await _lock_document(session, tenant_id=tenant_id, document_id=document_id)
    return (
        await session.execute(
            _LOCK_SQL, {"document_id": str(document_id), "tenant_id": str(tenant_id)}
        )
    ).first()


# ── generation lifecycle ──────────────────────────────────────────────────────


async def begin_generation(
    session: Any,
    *,
    tenant_id: UUID,
    document_id: UUID,
    revision_id: UUID | None,
    expected_revision_id: UUID | None = None,
    expected_generation: int | None = None,
    expected_stage: str | None = None,
    expected_phase: str | None = None,
    expected_outcome: str | None = None,
) -> int:
    """Start a new processing generation (new revision or explicit reprocess).

    Runs in the caller's transaction, with the document reset it belongs to.
    Bumps generation AND fence, so every earlier attempt is superseded.

    #758: a pending HITL review must stop being resumable at THIS boundary,
    not later when the replacement attempt happens to reach the HITL gate.
    Parsing and RAG run in between, and in that window an approval of the
    inherited review resumes a lineage the new revision has already
    invalidated. The generation bump is itself what makes a review's recorded
    lineage stale (see :mod:`src.core.resume_lineage`); the stamp below only
    brings LEGACY rows, which record no lineage at all, into the same
    comparison. Everything lands in the caller's transaction, so "the new
    generation is authoritative" and "the superseded review is not resumable"
    commit together or not at all.
    """
    from src.core import resume_lineage

    await _set_tenant(session, tenant_id)
    # Document first: ORM status/version updates may still be staged until flush.
    await _lock_document(session, tenant_id=tenant_id, document_id=document_id)
    row = (
        await session.execute(
            _BEGIN_GENERATION_SQL,
            {
                "document_id": str(document_id),
                "tenant_id": str(tenant_id),
                "revision_id": str(revision_id) if revision_id else None,
                "expected_revision_id": (
                    str(expected_revision_id) if expected_revision_id else None
                ),
                "expected_generation": expected_generation,
                "expected_stage": expected_stage,
                "expected_phase": expected_phase,
                "expected_outcome": expected_outcome,
            },
        )
    ).first()
    if row is None:
        raise ProcessingAuthorityLost(
            f"document {document_id} processing authority changed before generation start"
        )
    generation = int(row.generation)
    superseded = await resume_lineage.stamp_superseded_reviews(
        session,
        tenant_id=tenant_id,
        document_id=document_id,
        superseded_generation=generation - 1,
    )
    if superseded:
        logger.info(
            "review_lineage_superseded_by_generation",
            document_id=str(document_id),
            generation=generation,
            review_row_ids=[str(row_id) for row_id in superseded],
        )
    return generation


async def _ensure_row(
    session: Any,
    *,
    tenant_id: UUID,
    document_id: UUID,
    stage: ProcessingStage,
    revision_id: UUID | None,
) -> Any:
    row = await _lock(session, tenant_id=tenant_id, document_id=document_id)
    if row is not None:
        return row
    # Documents that predate #711 (or whose producer did not begin a
    # generation) start at generation 1 in the stage they are observed in.
    await session.execute(
        _INSERT_SQL,
        {
            "document_id": str(document_id),
            "tenant_id": str(tenant_id),
            "revision_id": str(revision_id) if revision_id else None,
            "generation": 1,
            "stage": stage.value,
        },
    )
    return await _lock(session, tenant_id=tenant_id, document_id=document_id)


async def _grant(
    session: Any,
    *,
    tenant_id: UUID,
    document_id: UUID,
    revision_id: UUID | None,
    phase: ProcessingPhase,
) -> ProcessingAuthority:
    attempt_id, owner_token = uuid4(), uuid4()
    granted = (
        await session.execute(
            _GRANT_SQL,
            {
                "document_id": str(document_id),
                "tenant_id": str(tenant_id),
                "attempt_id": str(attempt_id),
                "owner_token": str(owner_token),
                "phase": phase.value,
                "revision_id": str(revision_id) if revision_id else None,
                "ttl": LEASE_TTL_SECONDS,
            },
        )
    ).one()
    return ProcessingAuthority(
        tenant_id=tenant_id,
        document_id=document_id,
        revision_id=UUID(str(granted.revision_id)) if granted.revision_id else None,
        generation=int(granted.generation),
        stage=ProcessingStage(str(granted.stage)),
        attempt_id=attempt_id,
        owner_token=owner_token,
        fencing_token=int(granted.fencing_token),
    )


def _refusal(
    row: Any,
    *,
    stage: ProcessingStage,
    revision_id: UUID | None,
    generation: int | None,
) -> AcquireOutcome | None:
    """Why this invocation may NOT take the row, or None when it may."""
    if generation is not None and int(row.generation) != generation:
        return AcquireOutcome.SUPERSEDED
    if (
        revision_id is not None
        and row.revision_id is not None
        and UUID(str(row.revision_id)) != revision_id
    ):
        return AcquireOutcome.SUPERSEDED
    row_stage = ProcessingStage(str(row.stage))
    if row_stage is not stage:
        # Ingestion already handed over to analysis for this generation: a
        # late/redelivered ingestion message has nothing left to do.
        if stage is ProcessingStage.INGESTION and row_stage is ProcessingStage.ANALYSIS:
            return AcquireOutcome.COMPLETED
        return AcquireOutcome.SUPERSEDED
    phase = ProcessingPhase(str(row.phase))
    if phase is ProcessingPhase.COMPLETED:
        return AcquireOutcome.COMPLETED
    if phase is ProcessingPhase.FAILED:
        return AcquireOutcome.FAILED
    if phase in {ProcessingPhase.RUNNING, ProcessingPhase.CLAIMED} and bool(row.lease_valid):
        return AcquireOutcome.BUSY
    return None


async def acquire(
    session: Any,
    *,
    tenant_id: UUID,
    document_id: UUID,
    stage: ProcessingStage,
    revision_id: UUID | None = None,
    generation: int | None = None,
) -> AcquireResult:
    """Take processing ownership, or explain why this invocation must not.

    Never steals from a valid owner. Takeover only when unowned (PENDING) or
    the owner's lease has expired by the database clock. On refusal the
    caller rolls back.
    """
    await _touch_index(session, tenant_id=tenant_id, document_id=document_id)
    row = await _ensure_row(
        session, tenant_id=tenant_id, document_id=document_id, stage=stage,
        revision_id=revision_id,
    )
    refusal = _refusal(row, stage=stage, revision_id=revision_id, generation=generation)
    if refusal is not None:
        return AcquireResult(refusal, generation=int(row.generation))
    authority = await _grant(
        session, tenant_id=tenant_id, document_id=document_id,
        revision_id=revision_id, phase=ProcessingPhase.RUNNING,
    )
    return AcquireResult(AcquireOutcome.ACQUIRED, authority, authority.generation)


async def claim_for_recovery(
    session: Any,
    *,
    tenant_id: UUID,
    document_id: UUID,
    stage: ProcessingStage,
    revision_id: UUID | None,
) -> ProcessingAuthority | None:
    """Recovery takeover: only when no valid owner exists (DB-clock lease).

    Returns the CLAIMED authority to hand to exactly one replacement task.
    On refusal (None) the caller rolls back.
    """
    await _touch_index(session, tenant_id=tenant_id, document_id=document_id)
    row = await _ensure_row(
        session, tenant_id=tenant_id, document_id=document_id, stage=stage,
        revision_id=revision_id,
    )
    if _refusal(row, stage=stage, revision_id=None, generation=None) is not None:
        return None
    return await _grant(
        session, tenant_id=tenant_id, document_id=document_id,
        revision_id=revision_id, phase=ProcessingPhase.CLAIMED,
    )


async def recovery_may_fail(
    session: Any, *, tenant_id: UUID, document_id: UUID, stage: ProcessingStage
) -> bool:
    """Whether the sweep may terminally fail this stage: nobody owns it."""
    row = await _lock(session, tenant_id=tenant_id, document_id=document_id)
    if row is None:
        return True
    return _refusal(row, stage=stage, revision_id=None, generation=None) is None


async def adopt(session: Any, authority: ProcessingAuthority) -> bool:
    """Take up a recovery-claimed authority exactly once (CLAIMED -> RUNNING)."""
    await _set_tenant(session, authority.tenant_id)
    adopted = (
        await session.execute(
            _ADOPT_SQL, {**_exact_params(authority), "ttl": LEASE_TTL_SECONDS}
        )
    ).first()
    return adopted is not None


async def heartbeat(session: Any, authority: ProcessingAuthority) -> bool:
    """Renew the lease for the exact, still-valid owner.

    False = authority lost; the caller MUST roll back, so a superseded but
    live worker can never keep the recovery discovery hint fresh either.
    """
    await _touch_index(
        session,
        tenant_id=authority.tenant_id,
        document_id=authority.document_id,
        lock_document=False,
    )
    renewed = (
        await session.execute(
            _HEARTBEAT_SQL, {**_exact_params(authority), "ttl": LEASE_TTL_SECONDS}
        )
    ).first()
    return renewed is not None


async def verify_in_transaction(session: Any, authority: ProcessingAuthority) -> None:
    """Fence a durable write: lock and re-verify the exact grant, or raise.

    Must run inside the SAME transaction as the business mutation. The row
    lock is held until that transaction ends, so a takeover cannot interleave.
    """
    row = await _lock(
        session, tenant_id=authority.tenant_id, document_id=authority.document_id
    )
    if row is None:
        raise ProcessingAuthorityLost(
            f"no processing authority row for document {authority.document_id}"
        )
    expected_revision = str(authority.revision_id) if authority.revision_id else None
    actual_revision = str(row.revision_id) if row.revision_id else None
    mismatches = [
        name
        for name, ok in (
            ("attempt", row.attempt_id is not None
             and UUID(str(row.attempt_id)) == authority.attempt_id),
            ("owner", row.owner_token is not None
             and UUID(str(row.owner_token)) == authority.owner_token),
            ("fence", int(row.fencing_token) == authority.fencing_token),
            ("generation", int(row.generation) == authority.generation),
            ("stage", str(row.stage) == authority.stage.value),
            ("revision", actual_revision == expected_revision),
            ("phase", str(row.phase) == ProcessingPhase.RUNNING.value),
            ("lease", bool(row.lease_valid)),
        )
        if not ok
    ]
    if mismatches:
        raise ProcessingAuthorityLost(
            f"processing authority lost for document {authority.document_id} "
            f"(fence {authority.fencing_token}, now {row.fencing_token}; "
            f"mismatch: {', '.join(mismatches)})"
        )


# ── fenced transitions (each verifies first, in the caller's transaction) ─────

_FINISH_INGESTION_SQL = text(
    """
    UPDATE document_processing_operations
       SET stage = 'ANALYSIS', phase = 'PENDING',
           attempt_id = NULL, owner_token = NULL,
           lease_expires_at = NULL, heartbeat_at = NULL,
           attempt_count = 0, failure_count = 0, last_error = NULL,
           outcome = 'ingested',
           updated_at = clock_timestamp() AT TIME ZONE 'UTC'
     WHERE document_id = CAST(:document_id AS uuid)
       AND tenant_id = CAST(:tenant_id AS uuid)
    """
)

_SETTLE_SQL = text(
    """
    UPDATE document_processing_operations
       SET phase = :phase,
           outcome = :outcome,
           last_error = :error,
           failure_count = failure_count + :failed,
           attempt_id = NULL, owner_token = NULL,
           lease_expires_at = NULL, heartbeat_at = NULL,
           updated_at = clock_timestamp() AT TIME ZONE 'UTC'
     WHERE document_id = CAST(:document_id AS uuid)
       AND tenant_id = CAST(:tenant_id AS uuid)
    """
)


async def finish_ingestion(session: Any, authority: ProcessingAuthority) -> None:
    """Hand the generation over to ANALYSIS (unowned, PENDING)."""
    await verify_in_transaction(session, authority)
    await session.execute(
        _FINISH_INGESTION_SQL,
        {"document_id": str(authority.document_id), "tenant_id": str(authority.tenant_id)},
    )


async def settle(
    session: Any,
    authority: ProcessingAuthority,
    *,
    phase: ProcessingPhase,
    outcome: str,
    error: str | None = None,
) -> None:
    """End this attempt: COMPLETED/FAILED, or PENDING to allow a retry."""
    await verify_in_transaction(session, authority)
    await session.execute(
        _SETTLE_SQL,
        {
            "document_id": str(authority.document_id),
            "tenant_id": str(authority.tenant_id),
            "phase": phase.value,
            "outcome": outcome,
            "error": (error or None) and error[:2000],
            "failed": 1 if error else 0,
        },
    )


async def fail_unowned(
    session: Any, *, tenant_id: UUID, document_id: UUID, outcome: str, error: str
) -> None:
    """Recovery-only: terminally fail a stage nobody owns (row already locked)."""
    await session.execute(
        _SETTLE_SQL,
        {
            "document_id": str(document_id),
            "tenant_id": str(tenant_id),
            "phase": ProcessingPhase.FAILED.value,
            "outcome": outcome,
            "error": error[:2000],
            "failed": 1,
        },
    )


# ── ambient authority for graph nodes / hooks ────────────────────────────────

_current_authority: ContextVar[ProcessingAuthority | None] = ContextVar(
    "c2pro_processing_authority", default=None
)


@contextlib.contextmanager
def bound_authority(authority: ProcessingAuthority | None) -> Iterator[None]:
    """Bind the worker's authority for every seam reached from this context."""
    token = _current_authority.set(authority)
    try:
        yield
    finally:
        _current_authority.reset(token)


def current_authority() -> ProcessingAuthority | None:
    return _current_authority.get()


async def fence_current(session: Any) -> None:
    """Fence a durable seam if it runs inside a processing worker.

    No-op outside one (API requests, HITL resumes under their own V3 fence).
    """
    authority = _current_authority.get()
    if authority is not None:
        await verify_in_transaction(session, authority)


__all__ = [
    "LEASE_TTL_SECONDS",
    "AcquireOutcome",
    "AcquireResult",
    "ProcessingAuthority",
    "ProcessingAuthorityLost",
    "ProcessingPhase",
    "ProcessingStage",
    "acquire",
    "adopt",
    "begin_generation",
    "bound_authority",
    "claim_for_recovery",
    "current_authority",
    "fail_unowned",
    "fence_current",
    "finish_ingestion",
    "heartbeat",
    "recovery_may_fail",
    "settle",
    "verify_in_transaction",
]
