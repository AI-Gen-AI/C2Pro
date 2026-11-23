"""A17: reconstruct lost Score work from committed HITL approvals.

The durable source is review_items.review_metadata.a17_score_obligation,
stamped by PostgreSQL in the approval's own transaction. Celery/Beat is only a
best-effort dispatch mechanism: a lost task cannot lose the obligation.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text

from src.core.tasks.async_runtime import run_async_db_task
from src.core.tasks.celery_app import celery_app

logger = structlog.get_logger()

DEFAULT_BATCH_SIZE = 20
MAX_RETRY_ATTEMPTS = 6

_PENDING = text("""
SELECT r.id, r.tenant_id, r.project_id
  FROM review_items r
 WHERE r.tenant_id = :tenant_id
   AND r.current_status = 'APPROVED'
   AND r.approved_at IS NOT NULL
   AND r.project_id IS NOT NULL
   AND r.review_metadata -> 'a17_score_obligation' ->> 'state' = 'pending'
   AND (
       nullif(r.review_metadata -> 'a17_score_obligation' ->> 'retry_after', '')
       IS NULL
       OR (r.review_metadata -> 'a17_score_obligation' ->> 'retry_after')::timestamptz
          <= clock_timestamp()
   )
   AND NOT EXISTS (
       SELECT 1 FROM resume_operations o
        WHERE o.tenant_id = r.tenant_id
          AND o.review_row_id = r.id
          AND o.phase <> 'FINALIZED_APPROVED'
   )
 ORDER BY r.approved_at, r.id
 LIMIT :limit
""")

_RETRY = text("""
UPDATE review_items
   SET review_metadata = jsonb_set(
       coalesce(review_metadata, '{}'::jsonb),
       '{a17_score_obligation}',
       (review_metadata -> 'a17_score_obligation')
         || jsonb_build_object(
             'attempts',
             coalesce((review_metadata -> 'a17_score_obligation' ->> 'attempts')::integer, 0) + 1,
             'state', CASE WHEN
                 coalesce((review_metadata -> 'a17_score_obligation' ->> 'attempts')::integer, 0) + 1
                     >= :max_attempts
                 THEN 'operator_required' ELSE 'pending' END,
             'retry_after', clock_timestamp()
                 + make_interval(secs => LEAST(
                     3600, 30 * power(2,
                         LEAST(7, coalesce(
                             (review_metadata -> 'a17_score_obligation' ->> 'attempts')::integer,
                             0))))
                 )
         ),
       true
   )
 WHERE id = :review_id AND tenant_id = :tenant_id
   AND project_id = :project_id
   AND current_status = 'APPROVED'
   AND review_metadata -> 'a17_score_obligation' ->> 'state' = 'pending'
 RETURNING review_metadata -> 'a17_score_obligation' ->> 'state'
""")


async def reconcile_pending_postapproval(
    batch_size: int = DEFAULT_BATCH_SIZE,
    *,
    scan_factory: Any = None,
    tenant_factory: Any = None,
    evaluator: Any = None,
) -> dict[str, int]:
    """Reconcile bounded obligations using only tenant-scoped review reads.

    The existing unscoped session enumerates tenant identities from the
    canonical tenants table, whose SELECT policy explicitly supports this.
    Review/Score/ProjectEvent queries and writes are ALL tenant scoped:
    review_items may have FORCE RLS and must not be globally scanned.
    """
    from src.coherence.application.project_evaluation import (
        run_project_evaluation_after_approval,
    )
    from src.core.database import get_raw_session, get_session_with_tenant, init_db

    if scan_factory is None:
        await init_db()
        scan_factory = get_raw_session
    tenant_factory = tenant_factory or get_session_with_tenant
    evaluator = evaluator or run_project_evaluation_after_approval

    batch_size = max(1, min(int(batch_size), DEFAULT_BATCH_SIZE))
    async with scan_factory() as scan:
        tenant_ids = (
            (await scan.execute(text("SELECT id FROM tenants ORDER BY id"))).scalars().all()
        )

    # Never scan review_items without an RLS tenant. The global ceiling
    # limits work, not visibility; a retrying tenant cannot make other
    # organizations inaccessible.
    rows: list[Any] = []
    for raw_tenant in tenant_ids:
        tenant_id = UUID(str(raw_tenant))
        if len(rows) >= batch_size:
            break
        async with tenant_factory(tenant_id) as scoped_scan:
            candidates = (
                await scoped_scan.execute(
                    _PENDING, {"tenant_id": tenant_id, "limit": batch_size - len(rows)}
                )
            ).all()
            rows.extend(candidates)

    counts = {"scanned": len(rows), "completed": 0, "retry": 0, "operator_required": 0}
    for row in rows:
        review_id, tenant_id, project_id = (UUID(str(x)) for x in row)
        try:
            # Never forge a human user ID: the real approver identity remains
            # in review_items.approved_by; the recovery agent is a service.
            await evaluator(
                tenant_id=tenant_id,
                project_id=project_id,
                review_id=review_id,
                actor_user_id=None,
            )
        except Exception:
            logger.exception("a17_reconcile_evaluator_failed", review_id=str(review_id))
        async with tenant_factory(tenant_id) as session:
            state = await session.scalar(
                text(
                    "SELECT review_metadata -> 'a17_score_obligation' ->> 'state' "
                    "FROM review_items WHERE id = :id AND tenant_id = :tenant "
                    "AND project_id = :project"
                ),
                {"id": review_id, "tenant": tenant_id, "project": project_id},
            )
            if state == "done":
                counts["completed"] += 1
                continue
            if state != "pending":
                continue
            attempt = await session.scalar(
                _RETRY,
                {
                    "review_id": review_id,
                    "tenant_id": tenant_id,
                    "project_id": project_id,
                    "max_attempts": MAX_RETRY_ATTEMPTS,
                },
            )
            if attempt == "operator_required":
                counts["operator_required"] += 1
            elif attempt == "pending":
                counts["retry"] += 1
    logger.info("a17_reconcile_batch", **counts)
    return counts


@celery_app.task(name="coherence.reconcile_postapproval", bind=True)
def reconcile_postapproval_task(self: Any, batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, int]:  # noqa: ARG001
    return run_async_db_task(reconcile_pending_postapproval(batch_size=batch_size))
