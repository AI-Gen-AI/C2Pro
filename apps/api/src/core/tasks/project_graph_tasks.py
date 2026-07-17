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
from src.core.dlq.dlq_service import DLQService
from src.core.tasks.celery_app import celery_app
from src.core.tasks.project_graph_governance import ProjectGraphGovernance
from src.core.tenants.types import TenantId, require_tenant_id

logger = logging.getLogger(__name__)


async def _maybe_await(value: object) -> None:
    if inspect.isawaitable(value):
        await value


async def enqueue_project_graph(
    *,
    project_id: UUID,
    tenant_id: UUID,
    trigger_event_id: UUID | None = None,
    governance: ProjectGraphGovernance | None = None,
) -> None:
    if not await is_project_graph_enabled(tenant_id):
        return
    active_governance = governance or ProjectGraphGovernance()
    if not await active_governance.should_enqueue_project(project_id):
        return
    run_project_graph.delay(
        project_id=str(project_id),
        tenant_id=str(tenant_id),
        trigger_event_id=str(trigger_event_id) if trigger_event_id else None,
    )


async def run_project_graph_once(
    *,
    project_id: UUID,
    tenant_id: TenantId,
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
            "artifact_repository": artifact_repository,
        }
    )
    return {
        "status": "ok",
        "artifact_count": len(artifacts),
        "node_result_count": len(result.get("node_results", [])),
        "coherence_result": _serializable(result.get("coherence_result")),
        "node_results": result.get("node_results", []),
    }


def _serializable(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


async def _run_project_graph_async(
    *,
    project_id: UUID,
    tenant_id: TenantId,
    trigger_event_id: UUID | None = None,
    governance: ProjectGraphGovernance | None = None,
) -> dict[str, object]:
    active_governance = governance or ProjectGraphGovernance()
    if not await active_governance.acquire_tenant_slot(tenant_id):
        run_project_graph.apply_async(
            kwargs={
                "project_id": str(project_id),
                "tenant_id": str(tenant_id),
                "trigger_event_id": str(trigger_event_id) if trigger_event_id else None,
            },
            countdown=active_governance.requeue_countdown_seconds,
        )
        return {"status": "requeued", "artifact_count": 0, "node_result_count": 0}

    await _maybe_await(init_db())
    try:
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
                await active_governance.clear_project_pending(project_id)
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
    finally:
        await active_governance.release_tenant_slot(tenant_id)


async def record_project_graph_dead_letter(
    *,
    project_id: UUID,
    tenant_id: TenantId,
    trigger_event_id: UUID | None,
    error: Exception,
) -> UUID:
    return await DLQService().push(
        tenant_id=tenant_id,
        task_type="project_graph.run",
        document_id=None,
        payload={
            "project_id": str(project_id),
            "tenant_id": str(tenant_id),
            "trigger_event_id": str(trigger_event_id) if trigger_event_id else None,
        },
        error_message=str(error),
        error_traceback=None,
        max_retries=0,
    )


@celery_app.task(
    name="project_graph.run",
    bind=True,
    max_retries=3,
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
    project_uuid = UUID(project_id)
    tenant_uuid = require_tenant_id(tenant_id)
    trigger_uuid = UUID(trigger_event_id) if trigger_event_id else None
    try:
        return asyncio.run(
            _run_project_graph_async(
                project_id=project_uuid,
                tenant_id=tenant_uuid,
                trigger_event_id=trigger_uuid,
            )
        )
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            asyncio.run(
                record_project_graph_dead_letter(
                    project_id=project_uuid,
                    tenant_id=tenant_uuid,
                    trigger_event_id=trigger_uuid,
                    error=exc,
                )
            )
            raise
        raise self.retry(exc=exc, countdown=60) from exc


__all__ = [
    "enqueue_project_graph",
    "record_project_graph_dead_letter",
    "run_project_graph",
    "run_project_graph_once",
]
