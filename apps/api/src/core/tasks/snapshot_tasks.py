"""Celery tasks for ProjectSnapshot writing (ADR-015 / TASK-V3-015-05).

TS-INT-TASK-SNAP-001
"""

from __future__ import annotations

import inspect
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select, text

from src.analysis.adapters.persistence.analysis_repository import SqlAlchemyAnalysisRepository
from src.core.database import get_raw_session, init_db
from src.core.tasks.async_runtime import run_async_db_task
from src.core.tasks.celery_app import celery_app
from src.core.tenants.types import TenantId, require_tenant_id
from src.project_state.adapters.persistence.project_state_repository import (
    SqlAlchemyProjectStateRepository,
)
from src.projects.adapters.persistence.models import ProjectORM
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.adapters.persistence.project_snapshot_repository import (
    SqlAlchemyProjectSnapshotRepository,
)
from src.temporal.application.snapshot_writer import SnapshotWriter
from src.temporal.domain.project_snapshot import SnapshotTrigger

logger = logging.getLogger(__name__)


_SOURCE_EVENT_LOCK_SQL = text(
    """
    SELECT pg_advisory_xact_lock(
        hashtextextended('project_snapshot:' || cast(:source_event_id as text), 0)
    )
    """
)

_HITL_GRAPH_COMPLETION_CURRENCY_SQL = text(
    """
    SELECT
        e.resume_operation_id,
        CASE
            WHEN e.resume_operation_id IS NULL THEN true
            WHEN o.id IS NULL OR r.id IS NULL THEN false
            ELSE
                r.thread_id IS NOT DISTINCT FROM o.thread_id
                AND (
                    (r.lineage_generation IS NULL
                     AND r.lineage_fencing_token IS NULL)
                    OR a.generation IS NULL
                    OR (
                        (r.lineage_generation IS NULL
                         OR r.lineage_generation = a.generation)
                        AND (
                            r.lineage_fencing_token IS NULL
                            OR a.fencing_token IS NULL
                            OR r.lineage_fencing_token = a.fencing_token
                        )
                    )
                )
        END AS lineage_current
      FROM project_events e
      LEFT JOIN resume_operations o
        ON o.id = e.resume_operation_id
       AND o.tenant_id = e.tenant_id
       AND o.project_id = e.project_id
      LEFT JOIN review_items r
        ON r.id = o.review_row_id
       AND r.tenant_id = o.tenant_id
      LEFT JOIN document_processing_operations a
        ON a.document_id = r.document_id
       AND a.tenant_id = r.tenant_id
     WHERE e.event_id = cast(:source_event_id as uuid)
       AND e.tenant_id = cast(:tenant_id as uuid)
       AND e.project_id = cast(:project_id as uuid)
       AND e.event_type = 'graph.completed'
    """
)


async def _source_event_is_current_hitl_lineage(
    session: Any,
    *,
    source_event_id: UUID,
    tenant_id: TenantId,
    project_id: UUID,
) -> bool:
    """Fail closed only for HITL graph events proven to belong to stale lineage.

    A non-HITL graph.completed event has no resume_operation_id and therefore
    returns no row here; its pre-existing behavior is unchanged. For HITL,
    this mirrors ReviewLineage.is_current_for_document at the final writer
    boundary so a delayed old delivery cannot become the newest Health state.
    """
    row = (
        await session.execute(
            _HITL_GRAPH_COMPLETION_CURRENCY_SQL,
            {
                "source_event_id": str(source_event_id),
                "tenant_id": str(tenant_id),
                "project_id": str(project_id),
            },
        )
    ).first()
    return row is None or bool(row.lineage_current)


async def _maybe_await(value: object) -> None:
    if inspect.isawaitable(value):
        await value


def enqueue_project_snapshot(
    *,
    project_id: UUID,
    tenant_id: UUID,
    trigger: SnapshotTrigger,
    source_event_id: UUID | None = None,
) -> Any:
    return write_project_snapshot.delay(
        project_id=str(project_id),
        tenant_id=str(tenant_id),
        trigger=trigger.value,
        source_event_id=str(source_event_id) if source_event_id else None,
    )


async def _write_project_snapshot_async(
    *,
    project_id: UUID,
    tenant_id: TenantId,
    trigger: str,
    source_event_id: UUID | None = None,
) -> dict[str, str]:
    await _maybe_await(init_db())
    async with get_raw_session() as session:
        try:
            await session.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
            if source_event_id is not None:
                # Database-level idempotency boundary. Concurrent deliveries of
                # the SAME event serialize for this transaction; the waiter
                # observes the committed snapshot via SnapshotWriter's existing
                # source_event_id replay check instead of inserting a duplicate.
                await session.execute(
                    _SOURCE_EVENT_LOCK_SQL,
                    {"source_event_id": str(source_event_id)},
                )
                if (
                    trigger == SnapshotTrigger.GRAPH_COMPLETED.value
                    and not await _source_event_is_current_hitl_lineage(
                        session,
                        source_event_id=source_event_id,
                        tenant_id=tenant_id,
                        project_id=project_id,
                    )
                ):
                    logger.info(
                        "project_snapshot_stale_hitl_lineage_skipped",
                        extra={
                            "project_id": str(project_id),
                            "tenant_id": str(tenant_id),
                            "source_event_id": str(source_event_id),
                        },
                    )
                    await session.commit()
                    return {
                        "status": "skipped_stale_hitl_lineage",
                        "snapshot_id": "",
                    }
            snapshot = await SnapshotWriter(
                project_state_repository=SqlAlchemyProjectStateRepository(session),
                snapshot_repository=SqlAlchemyProjectSnapshotRepository(session),
                # ADR-024 / P0b L4-3 lineage: source_event_id -> graph.completed
                # {analysis_id} -> analyses.result_json -> persisted assessment.
                event_repository=SqlAlchemyProjectEventRepository(session),
                analysis_repository=SqlAlchemyAnalysisRepository(session, tenant_id=tenant_id),
            ).write_snapshot(
                project_id=project_id,
                tenant_id=tenant_id,
                trigger=SnapshotTrigger(trigger),
                source_event_id=source_event_id,
            )
            await session.commit()
            return {"status": "ok", "snapshot_id": str(snapshot.snapshot_id)}
        except Exception:
            await session.rollback()
            logger.exception(
                "project_snapshot_write_failed",
                extra={
                    "project_id": str(project_id),
                    "tenant_id": str(tenant_id),
                    "trigger": trigger,
                },
            )
            raise


@celery_app.task(
    name="project_snapshots.write",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    retry_backoff_max=60,
)
def write_project_snapshot(
    self: Any,  # noqa: ARG001
    *,
    project_id: str,
    tenant_id: str,
    trigger: str,
    source_event_id: str | None = None,
) -> dict[str, str]:
    return run_async_db_task(
        _write_project_snapshot_async(
            project_id=UUID(project_id),
            tenant_id=require_tenant_id(tenant_id),
            trigger=trigger,
            source_event_id=UUID(source_event_id) if source_event_id else None,
        )
    )


async def _enqueue_daily_project_snapshots_async(batch_size: int = 500) -> dict[str, int | str]:
    await _maybe_await(init_db())
    async with get_raw_session() as session:
        result = await session.execute(
            select(ProjectORM.id, ProjectORM.tenant_id)
            .where(ProjectORM.status == "active")
            .limit(batch_size)
        )
        rows = result.all()

    for project_id, tenant_id in rows:
        enqueue_project_snapshot(
            project_id=project_id,
            tenant_id=tenant_id,
            trigger=SnapshotTrigger.SCHEDULED,
            source_event_id=None,
        )
    return {"status": "ok", "enqueued": len(rows)}


@celery_app.task(name="project_snapshots.enqueue_daily", bind=True)
def enqueue_daily_project_snapshots(self: Any, batch_size: int = 500) -> dict[str, int | str]:  # noqa: ARG001
    return run_async_db_task(_enqueue_daily_project_snapshots_async(batch_size=batch_size))
