"""Celery tasks for ADR-017 ProjectGraph execution.

TS-UT-ADR017-TRG-001
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from uuid import UUID

from sqlalchemy import text

from src.analysis.adapters.graph.project_graph import (
    build_project_graph,
    is_project_graph_enabled,
)
from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.analysis.ports.document_artifact_repository import IDocumentArtifactRepository
from src.core.database import get_raw_session, init_db
from src.core.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _maybe_await(value: object) -> None:
    if inspect.isawaitable(value):
        await value


async def enqueue_project_graph(
    *,
    project_id: UUID,
    tenant_id: UUID,
    trigger_event_id: UUID | None = None,
) -> None:
    if not await is_project_graph_enabled(tenant_id):
        return
    run_project_graph.delay(
        project_id=str(project_id),
        tenant_id=str(tenant_id),
        trigger_event_id=str(trigger_event_id) if trigger_event_id else None,
    )


async def run_project_graph_once(
    *,
    project_id: UUID,
    tenant_id: UUID,
    artifact_repository: IDocumentArtifactRepository,
    trigger_event_id: UUID | None = None,
) -> dict[str, object]:
    artifacts = await artifact_repository.list_active_for_project(
        project_id=project_id,
        tenant_id=tenant_id,
    )
    result = await build_project_graph().ainvoke(
        {
            "project_id": project_id,
            "tenant_id": tenant_id,
            "trigger_event_id": trigger_event_id,
            "previous_snapshot_id": None,
            "changed_artifact_ids": [],
            "artifacts": artifacts,
            "coherence_result": None,
            "impact_result": None,
            "health_result": None,
            "snapshot_id": None,
            "node_results": [],
        }
    )
    return {
        "status": "ok",
        "artifact_count": len(artifacts),
        "node_result_count": len(result.get("node_results", [])),
    }


async def _run_project_graph_async(
    *,
    project_id: UUID,
    tenant_id: UUID,
    trigger_event_id: UUID | None = None,
) -> dict[str, object]:
    await _maybe_await(init_db())
    async with get_raw_session() as session:
        try:
            await session.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
            result = await run_project_graph_once(
                project_id=project_id,
                tenant_id=tenant_id,
                trigger_event_id=trigger_event_id,
                artifact_repository=SqlAlchemyDocumentArtifactRepository(session),
            )
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            logger.exception(
                "project_graph_run_failed",
                extra={
                    "project_id": str(project_id),
                    "tenant_id": str(tenant_id),
                    "trigger_event_id": str(trigger_event_id) if trigger_event_id else None,
                },
            )
            raise


@celery_app.task(
    name="project_graph.run",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    retry_backoff_max=60,
)
def run_project_graph(
    self,  # noqa: ARG001
    *,
    project_id: str,
    tenant_id: str,
    trigger_event_id: str | None = None,
) -> dict[str, object]:
    return asyncio.run(
        _run_project_graph_async(
            project_id=UUID(project_id),
            tenant_id=UUID(tenant_id),
            trigger_event_id=UUID(trigger_event_id) if trigger_event_id else None,
        )
    )


__all__ = ["enqueue_project_graph", "run_project_graph", "run_project_graph_once"]
