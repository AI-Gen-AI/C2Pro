"""Bounded reconciliation of abandoned HITL resume operations.

C2PRO P0b crash-safe HITL resume V3, section 4C.

A resume is driven by an HTTP request, so a worker that dies takes the
retry with it: nothing else would ever notice. Fencing makes a takeover
SAFE, but something has to actually attempt one, or a crashed approval sits
pending forever and the guarantee is theoretical.

This runs on the EXISTING Celery Beat schedule and the existing worker
fleet -- deliberately not a new always-on service, which would be far more
operational surface than the problem warrants.

It is bounded in every direction that matters:

* a LIMIT per sweep, so one bad batch cannot monopolise a worker;
* only operations whose lease has genuinely expired per `clock_timestamp()`
  (a healthy long-running resume is renewing its lease and is skipped);
* `next_attempt_at` honours the exponential backoff already recorded by
  `record_failure`, so a persistently failing operation is retried more and
  more slowly rather than hot-looping;
* after MAX_FAILURES_BEFORE_OPERATOR it becomes OPERATOR_REQUIRED and is
  never picked up again -- a halt, not an infinite retry.

Recovery uses `ResumeWorkflowUseCase.recover()` with the exact scanned
operation/row/decision/fence identity. Unlike human execute(), recovery can
never author a decision revision. Both share the existing fenced graph
executor after their separate acquisition transactions commit.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text

from src.core import resume_lineage
from src.core.tasks.async_runtime import run_async_db_task
from src.core.tasks.celery_app import celery_app

logger = structlog.get_logger()

# One sweep's ceiling. Small on purpose: Beat runs often, so throughput comes
# from frequency, not from long single runs that hold a worker.
DEFAULT_BATCH_SIZE = 20

# Non-terminal phases. FINALIZED_* is done; OPERATOR_REQUIRED is a
# deliberate halt and must never be auto-retried.
_RECOVERABLE_PHASES = (
    "PENDING",
    "RUNNING",
    "FAILED_RETRYABLE",
    "N17_DURABLE",
    "GRAPH_COMPLETED",
)

_CLAIMABLE_SQL = text(
    f"""
    SELECT o.id, o.tenant_id, o.review_row_id, o.phase, o.decision,
           o.decision_hash, o.decision_revision, o.fencing_token
      FROM resume_operations o
      JOIN review_items r ON r.id = o.review_row_id AND r.tenant_id = o.tenant_id
     WHERE o.phase = ANY(:phases)
       AND ((o.owner_token IS NULL AND o.lease_expires_at IS NULL)
            OR o.lease_expires_at <= clock_timestamp())
       AND (o.next_attempt_at IS NULL OR o.next_attempt_at <= clock_timestamp())
       AND o.decision IS NOT NULL
       -- #758: skip operations whose review has been rebound to another
       -- processing lineage. Only a hint, deliberately: this scan is
       -- cross-tenant and cannot see the fail-closed authority table, so the
       -- authoritative comparison stays in acquire_for_reconciliation, under
       -- the review row's lock. Filtering here just stops the sweep from
       -- burning its bounded batch on candidates it will always refuse.
       AND {resume_lineage.OPERATION_LINEAGE_MATCHES_REVIEW_SQL}
     ORDER BY o.updated_at
     LIMIT :limit
    """
)

HEALTH_PROJECTION_BATCH_SIZE = 20
MAX_HEALTH_PROJECTION_ENQUEUES = 12
HEALTH_PROJECTION_RETRY_SECONDS = 300

_PENDING_HEALTH_PROJECTIONS_SQL = text(
    """
    WITH candidates AS (
        SELECT o.id, o.tenant_id, o.project_id, o.updated_at, e.event_id,
               coalesce(
                   (o.operation_metadata
                     -> 'graph_completed_health_projection'
                     ->> 'attempts')::integer,
                   0
               ) AS attempts,
               coalesce(
                   o.operation_metadata
                     -> 'graph_completed_health_projection'
                     ->> 'state',
                   'pending'
               ) AS projection_state,
               nullif(
                   o.operation_metadata
                     -> 'graph_completed_health_projection'
                     ->> 'retry_after',
                   ''
               )::timestamptz AS retry_after,
               EXISTS (
                   SELECT 1
                     FROM project_snapshots s
                    WHERE s.tenant_id = o.tenant_id
                      AND s.project_id = o.project_id
                      AND s.source_event_id = e.event_id
                      AND s.trigger = 'graph_completed'
               ) AS snapshot_exists
          FROM resume_operations o
          JOIN project_events e
            ON e.event_id = cast(
                   o.operation_metadata
                     -> 'graph_completed_health_projection'
                     ->> 'event_id'
                   AS uuid
               )
           AND e.resume_operation_id = o.id
           AND e.tenant_id = o.tenant_id
           AND e.project_id = o.project_id
           AND e.event_type = 'graph.completed'
         WHERE o.phase = 'FINALIZED_APPROVED'
    )
    SELECT id, tenant_id, project_id, event_id, attempts,
           projection_state, retry_after, snapshot_exists
      FROM candidates
     WHERE (
               snapshot_exists
           AND projection_state <> 'projected'
        )
        OR (
               projection_state = 'pending'
           AND attempts < cast(:max_attempts as integer)
        )
        OR (
               projection_state = 'in_flight'
           AND retry_after IS NOT NULL
           AND retry_after <= clock_timestamp()
        )
     ORDER BY
         CASE
             WHEN snapshot_exists THEN 0
             WHEN projection_state = 'pending' THEN 1
             ELSE 2
         END,
         updated_at
     LIMIT :limit
    """
)

_MARK_HEALTH_PROJECTION_PROJECTED_SQL = text(
    """
    UPDATE resume_operations
       SET operation_metadata =
               coalesce(operation_metadata, '{}'::jsonb)
               || jsonb_build_object(
                      'graph_completed_health_projection',
                      coalesce(
                          operation_metadata -> 'graph_completed_health_projection',
                          '{}'::jsonb
                      ) || jsonb_build_object('state', 'projected')
                  ),
           updated_at = clock_timestamp()
     WHERE id = cast(:operation_id as uuid)
       AND tenant_id = cast(:tenant_id as uuid)
       AND phase = 'FINALIZED_APPROVED'
       AND operation_metadata
             -> 'graph_completed_health_projection'
             ->> 'event_id' = cast(:event_id as text)
    """
)

_MARK_HEALTH_PROJECTION_EXHAUSTED_SQL = text(
    """
    UPDATE resume_operations
       SET operation_metadata =
               coalesce(operation_metadata, '{}'::jsonb)
               || jsonb_build_object(
                      'graph_completed_health_projection',
                      coalesce(
                          operation_metadata -> 'graph_completed_health_projection',
                          '{}'::jsonb
                      ) || jsonb_build_object('state', 'exhausted')
                  ),
           updated_at = clock_timestamp()
     WHERE id = cast(:operation_id as uuid)
       AND tenant_id = cast(:tenant_id as uuid)
       AND phase = 'FINALIZED_APPROVED'
       AND operation_metadata
             -> 'graph_completed_health_projection'
             ->> 'event_id' = cast(:event_id as text)
       AND operation_metadata
             -> 'graph_completed_health_projection'
             ->> 'state' = 'in_flight'
       AND coalesce(
               (operation_metadata
                 -> 'graph_completed_health_projection'
                 ->> 'attempts')::integer,
               0
           ) >= cast(:max_attempts as integer)
       AND nullif(
               operation_metadata
                 -> 'graph_completed_health_projection'
                 ->> 'retry_after',
               ''
           )::timestamptz <= clock_timestamp()
    RETURNING id
    """
)

_CLAIM_HEALTH_PROJECTION_RETRY_SQL = text(
    """
    UPDATE resume_operations
       SET operation_metadata =
               coalesce(operation_metadata, '{}'::jsonb)
               || jsonb_build_object(
                      'graph_completed_health_projection',
                      coalesce(
                          operation_metadata -> 'graph_completed_health_projection',
                          '{}'::jsonb
                      ) || jsonb_build_object(
                          'attempts', cast(:next_attempt as integer),
                          'state', 'in_flight',
                          'retry_after',
                              clock_timestamp()
                              + make_interval(
                                    secs => cast(
                                        :retry_delay_seconds as double precision
                                    )
                                )
                      )
                  ),
           updated_at = clock_timestamp()
     WHERE id = cast(:operation_id as uuid)
       AND tenant_id = cast(:tenant_id as uuid)
       AND phase = 'FINALIZED_APPROVED'
       AND operation_metadata
             -> 'graph_completed_health_projection'
             ->> 'event_id' = cast(:event_id as text)
       AND coalesce(
               (operation_metadata
                 -> 'graph_completed_health_projection'
                 ->> 'attempts')::integer,
               0
           ) = cast(:expected_attempt as integer)
       AND coalesce(
               (operation_metadata
                 -> 'graph_completed_health_projection'
                 ->> 'attempts')::integer,
               0
           ) < cast(:max_attempts as integer)
       AND (
            operation_metadata
              -> 'graph_completed_health_projection'
              ->> 'state' = 'pending'
            OR (
                operation_metadata
                  -> 'graph_completed_health_projection'
                  ->> 'state' = 'in_flight'
                AND nullif(
                        operation_metadata
                          -> 'graph_completed_health_projection'
                          ->> 'retry_after',
                        ''
                    )::timestamptz <= clock_timestamp()
            )
       )
    RETURNING id
    """
)

async def _reconcile_graph_completed_health_projections(
    batch_size: int = HEALTH_PROJECTION_BATCH_SIZE,
    *,
    session_factory: Any = None,
) -> dict[str, int]:
    """Recover lost GRAPH_COMPLETED snapshot dispatches after trusted HITL finalization."""
    from src.core.tenants.types import require_tenant_id
    from src.temporal.application import project_snapshot_trigger
    from src.temporal.domain.project_snapshot import SnapshotTrigger

    if session_factory is None:
        from src.core.database import init_db

        result = init_db()
        if asyncio.iscoroutine(result):
            await result
        session_factory = _production_session

    async with session_factory(None) as session:
        rows = (
            await session.execute(
                _PENDING_HEALTH_PROJECTIONS_SQL,
                {
                    "limit": batch_size,
                    "max_attempts": MAX_HEALTH_PROJECTION_ENQUEUES,
                },
            )
        ).all()

    counts = {"scanned": 0, "enqueued": 0, "projected": 0, "exhausted": 0, "failed": 0}
    for row in rows:
        counts["scanned"] += 1
        tenant_id = UUID(str(row.tenant_id))
        project_id = UUID(str(row.project_id))
        event_id = UUID(str(row.event_id))

        if bool(row.snapshot_exists):
            async with session_factory(tenant_id) as session:
                await session.execute(
                    _MARK_HEALTH_PROJECTION_PROJECTED_SQL,
                    {
                        "operation_id": str(row.id),
                        "tenant_id": str(tenant_id),
                        "event_id": str(event_id),
                    },
                )
            counts["projected"] += 1
            continue

        attempts = int(row.attempts)
        if attempts >= MAX_HEALTH_PROJECTION_ENQUEUES:
            async with session_factory(tenant_id) as session:
                exhausted = (
                    await session.execute(
                        _MARK_HEALTH_PROJECTION_EXHAUSTED_SQL,
                        {
                            "operation_id": str(row.id),
                            "tenant_id": str(tenant_id),
                            "event_id": str(event_id),
                            "max_attempts": MAX_HEALTH_PROJECTION_ENQUEUES,
                        },
                    )
                ).first()
            if exhausted is not None:
                counts["exhausted"] += 1
            continue

        next_attempt = attempts + 1
        async with session_factory(tenant_id) as session:
            claimed = (
                await session.execute(
                    _CLAIM_HEALTH_PROJECTION_RETRY_SQL,
                    {
                        "operation_id": str(row.id),
                        "tenant_id": str(tenant_id),
                        "event_id": str(event_id),
                        "expected_attempt": attempts,
                        "next_attempt": next_attempt,
                        "max_attempts": MAX_HEALTH_PROJECTION_ENQUEUES,
                        "retry_delay_seconds": HEALTH_PROJECTION_RETRY_SECONDS,
                    },
                )
            ).first()
        if claimed is None:
            continue

        try:
            project_snapshot_trigger.enqueue_project_snapshot(
                project_id=project_id,
                tenant_id=require_tenant_id(tenant_id),
                trigger=SnapshotTrigger.GRAPH_COMPLETED,
                source_event_id=event_id,
            )
            counts["enqueued"] += 1
        except Exception:  # noqa: BLE001 - bounded reconciler retries on the next beat
            counts["failed"] += 1
            logger.warning(
                "hitl_health_projection_reconcile_enqueue_failed",
                operation_id=str(row.id),
                project_id=str(project_id),
                event_id=str(event_id),
                attempt=next_attempt,
                exc_info=True,
            )

    logger.info("hitl_health_projection_reconcile", **counts)
    return counts


async def _sweep_async(
    batch_size: int = DEFAULT_BATCH_SIZE,
    *,
    session_factory: Any = None,
    use_case_factory: Any = None,
) -> dict[str, Any]:
    """Run one bounded sweep.

    `session_factory` / `use_case_factory` are injection points so the sweep
    can be exercised against a real database with a real graph. They default
    to the production wiring.
    """
    from src.modules.hitl.adapters.persistence.repository import (
        SqlAlchemyReviewQueueRepository,
    )
    from src.modules.hitl.application.resume_workflow_use_case import (
        RecoveryOutcome,
        ResumeRecoveryRequest,
        ResumeWorkflowUseCase,
    )

    if session_factory is None:
        from src.core.database import init_db

        result = init_db()
        if asyncio.iscoroutine(result):
            await result
        session_factory = _production_session

    if use_case_factory is None:

        def use_case_factory(session: Any, tenant_id: UUID) -> Any:
            return ResumeWorkflowUseCase(
                review_queue_repo=SqlAlchemyReviewQueueRepository(
                    session=session, tenant_id=tenant_id
                )
            )

    # Read the candidate list first. The sweep is a cross-tenant operator
    # process; each recovery below is then driven through a session scoped
    # to that operation's OWN tenant.
    async with session_factory(None) as session:
        rows = (
            await session.execute(
                _CLAIMABLE_SQL,
                {"phases": list(_RECOVERABLE_PHASES), "limit": batch_size},
            )
        ).all()

    recovered = 0
    refused = 0
    failed = 0

    for row in rows:
        tenant_id = UUID(str(row.tenant_id))
        try:
            async with session_factory(tenant_id) as session:
                use_case = use_case_factory(session, tenant_id)
                outcome = await use_case.recover(
                    ResumeRecoveryRequest(
                        operation_id=UUID(str(row.id)),
                        review_row_id=UUID(str(row.review_row_id)),
                        tenant_id=tenant_id,
                        expected_decision=row.decision,
                        expected_decision_hash=row.decision_hash,
                        expected_decision_revision=row.decision_revision,
                        expected_fencing_token=row.fencing_token,
                    ),
                )
            if outcome is not RecoveryOutcome.RECOVERED:
                refused += 1
                logger.info(
                    "hitl_resume_reconcile_refused",
                    operation_id=str(row.id), outcome=outcome.value,
                )
                continue
            recovered += 1
            logger.info(
                "hitl_resume_reconciled",
                operation_id=str(row.id),
                from_phase=row.phase,
                decision=row.decision,
            )
        except ValueError as exc:
            # A live owner re-acquired it, or it finalized between the scan
            # and now. Deterministic refusal, not an error.
            refused += 1
            logger.info(
                "hitl_resume_reconcile_refused",
                operation_id=str(row.id),
                reason=str(exc),
            )
        except Exception:  # noqa: BLE001 - one bad operation must not end the sweep
            # The use case already recorded the failure and its backoff, so
            # this operation simply comes back later -- or reaches
            # OPERATOR_REQUIRED and stops coming back at all.
            failed += 1
            logger.warning(
                "hitl_resume_reconcile_failed",
                operation_id=str(row.id),
                from_phase=row.phase,
                exc_info=True,
            )

    return {
        "status": "ok",
        "scanned": len(rows),
        "recovered": recovered,
        "refused": refused,
        "failed": failed,
    }


@asynccontextmanager
async def _production_session(tenant_id: UUID | None) -> Any:
    """A session scoped to one tenant, or unscoped for the candidate scan."""
    from src.core.database import get_raw_session

    async with get_raw_session() as session:
        if tenant_id is not None:
            await session.execute(
                text("SELECT set_config('app.current_tenant', :t, true)"),
                {"t": str(tenant_id)},
            )
        yield session
        await session.commit()


@celery_app.task(name="hitl_resume.reconcile", bind=True)
def reconcile_abandoned_resumes(
    self: Any,  # noqa: ARG001
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, Any]:
    return run_async_db_task(_sweep_async(batch_size=batch_size))


@celery_app.task(name="hitl_resume.reconcile_health_projection", bind=True)
def reconcile_health_projections(
    self: Any,  # noqa: ARG001
    batch_size: int = HEALTH_PROJECTION_BATCH_SIZE,
) -> dict[str, int]:
    return run_async_db_task(
        _reconcile_graph_completed_health_projections(batch_size=batch_size)
    )
