"""Celery tasks for ProjectSnapshot writing (ADR-015 / TASK-V3-015-05).

TS-INT-TASK-SNAP-001
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from uuid import UUID

from sqlalchemy import select, text

from src.core.database import get_raw_session, init_db
from src.core.tasks.celery_app import celery_app
from src.project_state.adapters.persistence.project_state_repository import (
    SqlAlchemyProjectStateRepository,
)
from src.projects.adapters.persistence.models import ProjectORM
from src.temporal.adapters.persistence.project_snapshot_repository import (
    SqlAlchemyProjectSnapshotRepository,
)
from src.temporal.application.snapshot_writer import SnapshotWriter
from src.temporal.domain.project_snapshot import SnapshotTrigger

logger = logging.getLogger(__name__)


async def _maybe_await(value: object) -> None:
    if inspect.isawaitable(value):
        await value


def enqueue_project_snapshot(
    *,
    project_id: UUID,
    tenant_id: UUID,
    trigger: SnapshotTrigger,
    source_event_id: UUID | None = None,
):
    return write_project_snapshot.delay(
        project_id=str(project_id),
        tenant_id=str(tenant_id),
        trigger=trigger.value,
        source_event_id=str(source_event_id) if source_event_id else None,
    )


async def _write_project_snapshot_async(
    *,
    project_id: UUID,
    tenant_id: UUID,
    trigger: str,
    source_event_id: UUID | None = None,
) -> dict[str, str]:
    await _maybe_await(init_db())
    async with get_raw_session() as session:
        try:
            await session.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
            snapshot = await SnapshotWriter(
                project_state_repository=SqlAlchemyProjectStateRepository(session),
                snapshot_repository=SqlAlchemyProjectSnapshotRepository(session),
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
    self,  # noqa: ARG001
    *,
    project_id: str,
    tenant_id: str,
    trigger: str,
    source_event_id: str | None = None,
) -> dict[str, str]:
    return asyncio.run(
        _write_project_snapshot_async(
            project_id=UUID(project_id),
            tenant_id=UUID(tenant_id),
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
def enqueue_daily_project_snapshots(self, batch_size: int = 500) -> dict[str, int | str]:  # noqa: ARG001
    return asyncio.run(_enqueue_daily_project_snapshots_async(batch_size=batch_size))
