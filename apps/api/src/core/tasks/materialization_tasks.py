"""Lane C / C3b-1: drain pending trusted-artifact materialization obligations.

The approval transaction (#714 ``commit_candidate``) leaves a durable
``materialization_state = 'pending'`` obligation keyed by ``artifact_id``. The
fenced HITL resume materializes it in that SAME transaction, so normally
nothing is left pending. Anything that is -- an approval path that committed
without materializing, a crash, a lost dispatch -- is recovered here:

* ``reconcile_pending_materializations`` (beat) re-dispatches pending
  obligations; it never writes business state itself.
* ``materialize_pending_artifact`` runs the ONE canonical materializer
  (``analysis.application.trusted_materialization``) under the canonical lock
  order. Delivery is at-least-once; the effect is idempotent by artifact_id
  (``uq_analyses_source_artifact``), so a duplicate or a replay after the
  resume already materialized writes nothing. A stale/superseded artifact is
  marked ``obsolete`` with zero canonical writes. Repeated failures stop at
  ``operator_required`` -- trust state is never touched.
"""

from __future__ import annotations

import inspect
import json
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from sqlalchemy import text

from src.analysis.application import trusted_materialization as materializer
from src.core.database import get_raw_session, init_db
from src.core.tasks.async_runtime import run_async_db_task
from src.core.tasks.celery_app import celery_app
from src.core.tenants.types import require_tenant_id

logger = logging.getLogger(__name__)

MAX_MATERIALIZATION_ATTEMPTS = 5
RECONCILE_BATCH_SIZE = 50
RECONCILE_GRACE_SECONDS = 60

_OBLIGATION_SQL = text(
    """
    SELECT o.artifact_id, o.document_id, o.project_id, o.tenant_id,
           o.artifact_version, o.artifact_hash, o.materialization_state
      FROM system_recovery.trusted_projection_index o
     WHERE o.artifact_id = cast(:artifact_id as uuid)
       AND o.tenant_id = cast(:tenant_id as uuid)
    """
)

_LOCK_PENDING_OBLIGATION_SQL = text(
    """
    SELECT materialization_state
      FROM system_recovery.trusted_projection_index
     WHERE artifact_id = cast(:artifact_id as uuid)
       AND tenant_id = cast(:tenant_id as uuid)
     FOR UPDATE
    """
)

_ARTIFACT_CONTENT_SQL = text(
    """
    SELECT payload, scoring
      FROM document_artifacts
     WHERE artifact_id = cast(:artifact_id as uuid)
       AND tenant_id = cast(:tenant_id as uuid)
    """
)

_RECORD_FAILURE_SQL = text(
    """
    UPDATE system_recovery.trusted_projection_index
       SET materialization_attempts = materialization_attempts + 1,
           materialization_state = CASE
               WHEN materialization_attempts + 1 >= :max_attempts THEN 'operator_required'
               ELSE materialization_state
           END,
           materialization_detail = cast(:detail as jsonb),
           materialization_checked_at = (clock_timestamp() AT TIME ZONE 'UTC'),
           updated_at = (clock_timestamp() AT TIME ZONE 'UTC')
     WHERE artifact_id = cast(:artifact_id as uuid)
       AND tenant_id = cast(:tenant_id as uuid)
       AND materialization_state = 'pending'
    RETURNING materialization_state
    """
)

_PENDING_MATERIALIZATIONS_SQL = text(
    """
    SELECT artifact_id, tenant_id
      FROM system_recovery.trusted_projection_index
     WHERE materialization_state = 'pending'
       AND created_at <= (clock_timestamp() AT TIME ZONE 'UTC') - make_interval(secs => :grace)
       AND (materialization_checked_at IS NULL
            OR materialization_checked_at
               <= (clock_timestamp() AT TIME ZONE 'UTC') - make_interval(secs => :grace))
     ORDER BY coalesce(materialization_checked_at, created_at)
     LIMIT :limit
    """
)

_TOUCH_SQL = text(
    """
    UPDATE system_recovery.trusted_projection_index
       SET materialization_checked_at = (clock_timestamp() AT TIME ZONE 'UTC')
     WHERE artifact_id = cast(:artifact_id as uuid)
       AND materialization_state = 'pending'
    """
)

SessionFactory = Callable[[UUID], Any]


async def _maybe_await(value: object) -> None:
    if inspect.isawaitable(value):
        await value


def _default_session(tenant_id: UUID) -> Any:
    @asynccontextmanager
    async def _ctx() -> AsyncIterator[Any]:
        async with get_raw_session() as session:
            await session.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
            yield session

    return _ctx()


async def materialize_pending_artifact(
    *,
    artifact_id: UUID,
    tenant_id: UUID,
    session_factory: SessionFactory | None = None,
) -> dict[str, Any]:
    """Materialize one pending obligation, at most once. Never raises."""
    factory = session_factory or _default_session
    if session_factory is None:
        await _maybe_await(init_db())
    try:
        async with factory(tenant_id) as session:
            try:
                result = await _materialize(session, artifact_id=artifact_id, tenant_id=tenant_id)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
    except Exception as exc:
        logger.exception(
            "trusted_materialization_failed",
            extra={"artifact_id": str(artifact_id), "tenant_id": str(tenant_id)},
        )
        state = await _record_failure(
            factory, artifact_id=artifact_id, tenant_id=tenant_id, error=exc
        )
        return {"status": "failed", "materialization_state": state}


async def _materialize(session: Any, *, artifact_id: UUID, tenant_id: UUID) -> dict[str, Any]:
    obligation = (
        await session.execute(
            _OBLIGATION_SQL, {"artifact_id": str(artifact_id), "tenant_id": str(tenant_id)}
        )
    ).first()
    if obligation is None:
        return {"status": "no_obligation"}
    if obligation.materialization_state != materializer.MaterializationState.PENDING:
        return {"status": "noop", "materialization_state": obligation.materialization_state}

    ref = materializer.ArtifactRef(
        artifact_id=obligation.artifact_id,
        document_id=obligation.document_id,
        artifact_version=int(obligation.artifact_version),
        artifact_hash=str(obligation.artifact_hash),
        project_id=obligation.project_id,
        tenant_id=obligation.tenant_id,
    )
    # Canonical lock order: DOCUMENT -> PROJECT -> (ARTIFACT, OBLIGATION).
    await materializer.lock_document(session, tenant_id=tenant_id, document_id=ref.document_id)
    await materializer.lock_project(session, tenant_id=tenant_id, project_id=ref.project_id)
    locked = (
        await session.execute(
            _LOCK_PENDING_OBLIGATION_SQL,
            {"artifact_id": str(artifact_id), "tenant_id": str(tenant_id)},
        )
    ).first()
    if locked is None or locked.materialization_state != materializer.MaterializationState.PENDING:
        # A concurrent delivery (or the resume) finished it while we waited.
        return {
            "status": "noop",
            "materialization_state": locked.materialization_state if locked else None,
        }

    content_row = (
        await session.execute(
            _ARTIFACT_CONTENT_SQL, {"artifact_id": str(artifact_id), "tenant_id": str(tenant_id)}
        )
    ).first()
    content = materializer.MaterializationContent.from_artifact(
        content_row.payload if content_row is not None else {},
        content_row.scoring if content_row is not None else None,
    )
    outcome = await materializer.materialize_in_transaction(session, ref=ref, content=content)
    if outcome.status is materializer.MaterializationStatus.OBSOLETE:
        await materializer.mark_obsolete(session, ref, outcome.reason or "stale")
    return {
        "status": outcome.status.value,
        "analysis_id": str(outcome.analysis_id) if outcome.analysis_id else None,
        "qualifications": list(outcome.qualifications),
        "reason": outcome.reason,
    }


async def _record_failure(
    factory: SessionFactory, *, artifact_id: UUID, tenant_id: UUID, error: Exception
) -> str | None:
    try:
        async with factory(tenant_id) as session:
            row = (
                await session.execute(
                    _RECORD_FAILURE_SQL,
                    {
                        "artifact_id": str(artifact_id),
                        "tenant_id": str(tenant_id),
                        "max_attempts": MAX_MATERIALIZATION_ATTEMPTS,
                        "detail": json.dumps(
                            {
                                "last_error_type": type(error).__name__,
                                "materializer_version": materializer.MATERIALIZER_VERSION,
                            }
                        ),
                    },
                )
            ).first()
            await session.commit()
            return str(row.materialization_state) if row is not None else None
    except Exception:
        logger.exception(
            "trusted_materialization_failure_not_recorded",
            extra={"artifact_id": str(artifact_id)},
        )
        return None


def enqueue_materialization(*, artifact_id: UUID, tenant_id: UUID) -> None:
    materialize_trusted_artifact.delay(artifact_id=str(artifact_id), tenant_id=str(tenant_id))


async def reconcile_pending_materializations(
    *,
    batch_size: int = RECONCILE_BATCH_SIZE,
    grace_seconds: int = RECONCILE_GRACE_SECONDS,
    session_factory: Callable[[], Any] | None = None,
) -> dict[str, int]:
    """Re-dispatch pending obligations whose fast path was lost (broker loss)."""
    counts = {"scanned": 0, "enqueued": 0}
    if session_factory is None:
        await _maybe_await(init_db())
    factory = session_factory or get_raw_session
    async with factory() as session:
        rows = (
            await session.execute(
                _PENDING_MATERIALIZATIONS_SQL, {"grace": grace_seconds, "limit": batch_size}
            )
        ).all()
        for row in rows:
            counts["scanned"] += 1
            enqueue_materialization(
                artifact_id=UUID(str(row.artifact_id)),
                tenant_id=require_tenant_id(str(row.tenant_id)),
            )
            counts["enqueued"] += 1
            await session.execute(_TOUCH_SQL, {"artifact_id": str(row.artifact_id)})
        await session.commit()
    logger.info("trusted_materialization_reconcile", extra=counts)
    return counts


@celery_app.task(name="materialization.materialize_trusted_artifact")
def materialize_trusted_artifact(*, artifact_id: str, tenant_id: str) -> dict[str, Any]:
    return run_async_db_task(
        materialize_pending_artifact(
            artifact_id=UUID(artifact_id), tenant_id=require_tenant_id(tenant_id)
        )
    )


@celery_app.task(name="materialization.reconcile_pending")
def reconcile_pending_materializations_task() -> dict[str, int]:
    return run_async_db_task(reconcile_pending_materializations())


__all__ = [
    "MAX_MATERIALIZATION_ATTEMPTS",
    "enqueue_materialization",
    "materialize_pending_artifact",
    "reconcile_pending_materializations",
]
