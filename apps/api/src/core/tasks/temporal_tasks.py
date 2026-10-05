"""Lane C / C3b-2: governed recomputation of legacy temporal comparisons.

``temporal.recompute_legacy_changes`` is dispatched explicitly (operator or
backfill), one project at a time; it is not on the beat schedule. It appends a
``revision.recomputed`` event for every ``revision.changed`` produced by an
older registered matcher, using only the immutable snapshots that comparison
used (``temporal.application.legacy_recomputation``). Originals are never
mutated; a re-run, a duplicate delivery or a concurrent run adds nothing
(deterministic event id + primary key).
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from sqlalchemy import text

from src.core.database import get_raw_session, init_db
from src.core.tasks.async_runtime import run_async_db_task
from src.core.tasks.celery_app import celery_app
from src.core.tenants.types import require_tenant_id
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.application.legacy_recomputation import (
    RecomputeStatus,
    recompute_legacy_changes_for_project,
)

logger = logging.getLogger(__name__)

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


async def recompute_project_legacy_changes(
    *,
    tenant_id: UUID,
    project_id: UUID,
    session_factory: SessionFactory | None = None,
) -> dict[str, int]:
    """Recompute every eligible legacy comparison of one project; counts by status."""
    factory = session_factory or _default_session
    if session_factory is None:
        await _maybe_await(init_db())
    async with factory(tenant_id) as session:
        try:
            outcomes = await recompute_legacy_changes_for_project(
                SqlAlchemyProjectEventRepository(session),
                tenant_id=tenant_id,
                project_id=project_id,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    counts = {status.value: 0 for status in RecomputeStatus}
    for outcome in outcomes:
        counts[outcome.status.value] += 1
    logger.info(
        "temporal_legacy_recomputation",
        extra={"tenant_id": str(tenant_id), "project_id": str(project_id), **counts},
    )
    return counts


@celery_app.task(name="temporal.recompute_legacy_changes")
def recompute_legacy_changes_task(*, tenant_id: str, project_id: str) -> dict[str, int]:
    return run_async_db_task(
        recompute_project_legacy_changes(
            tenant_id=require_tenant_id(tenant_id), project_id=UUID(project_id)
        )
    )


__all__ = ["recompute_legacy_changes_task", "recompute_project_legacy_changes"]
