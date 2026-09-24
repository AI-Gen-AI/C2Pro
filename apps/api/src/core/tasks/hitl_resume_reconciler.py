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

It intentionally drives the SAME `ResumeWorkflowUseCase.execute()` path a
human retry would, with the decision the reviewer actually recorded. That
keeps exactly one implementation of recovery: the use case already decides,
from the durable phase, whether an operation needs a replay or only
finalization, and the fence makes a collision with a live worker a
deterministic refusal rather than a race.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text

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
    """
    SELECT o.id, o.tenant_id, o.review_row_id, o.phase, o.decision,
           o.reviewer, o.failure_count, r.item_id
      FROM resume_operations o
      JOIN review_items r ON r.id = o.review_row_id
     WHERE o.phase = ANY(:phases)
       AND (o.lease_expires_at IS NULL OR o.lease_expires_at <= clock_timestamp())
       AND (o.next_attempt_at IS NULL OR o.next_attempt_at <= clock_timestamp())
       AND o.decision IS NOT NULL
     ORDER BY o.updated_at
     LIMIT :limit
    """
)


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
        ResumeWorkflowRequest,
        ResumeWorkflowUseCase,
        WorkflowDecision,
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
            decision = WorkflowDecision(row.decision)
        except ValueError:
            logger.warning(
                "hitl_resume_reconcile_unknown_decision",
                operation_id=str(row.id),
                decision=row.decision,
            )
            continue

        try:
            async with session_factory(tenant_id) as session:
                use_case = use_case_factory(session, tenant_id)
                await use_case.execute(
                    review_id=UUID(str(row.item_id)),
                    request=ResumeWorkflowRequest(
                        decision=decision,
                        feedback="",
                        approved_by=row.reviewer or "reconciler",
                    ),
                )
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
    return asyncio.run(_sweep_async(batch_size=batch_size))
