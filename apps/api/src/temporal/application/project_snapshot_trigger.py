"""Material ProjectEvent to ProjectSnapshot trigger bridge (ADR-015).

Test Suite ID: TS-UT-TEMPORAL-SNAPSHOT-TRIGGER-001
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog

from src.core.database import get_session_with_tenant
from src.core.json_types import JsonDict
from src.core.tenants.types import TenantId, require_tenant_id
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.domain.project_event import ProjectEvent
from src.temporal.domain.project_snapshot import SnapshotTrigger

logger = structlog.get_logger(__name__)


def enqueue_project_snapshot(
    *,
    project_id: UUID,
    tenant_id: TenantId,
    trigger: SnapshotTrigger,
    source_event_id: UUID | None,
) -> None:
    """Load Celery only when a material event has committed."""
    from src.core.tasks.snapshot_tasks import enqueue_project_snapshot as enqueue

    enqueue(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=trigger,
        source_event_id=source_event_id,
    )


async def record_project_event_and_enqueue_snapshot(
    *,
    project_id: UUID,
    tenant_id: TenantId | UUID,
    event_type: str,
    payload: JsonDict,
    trigger: SnapshotTrigger,
    actor: str | None = None,
) -> UUID:
    """Append a committed material event, then fire-and-forget its snapshot.

    The event transaction completes before Celery receives its ID, so the worker
    can safely use ``source_event_id`` for its FK and idempotency boundary.
    Enqueue failure is intentionally fail-open: source operations remain usable
    and the daily snapshot job still provides eventual coverage.
    """
    scoped_tenant_id = require_tenant_id(tenant_id)
    now = datetime.now(UTC).replace(tzinfo=None)
    event = ProjectEvent(
        event_id=uuid4(),
        project_id=project_id,
        tenant_id=scoped_tenant_id,
        event_type=event_type,
        payload=payload,
        actor=actor,
        occurred_at=now,
        created_at=now,
    )

    async with get_session_with_tenant(scoped_tenant_id) as session:
        await SqlAlchemyProjectEventRepository(session).append(event)

    try:
        enqueue_project_snapshot(
            project_id=project_id,
            tenant_id=scoped_tenant_id,
            trigger=trigger,
            source_event_id=event.event_id,
        )
    except Exception:  # noqa: BLE001 - enqueue must not block a material operation.
        logger.warning(
            "project_snapshot_enqueue_failed",
            project_id=str(project_id),
            tenant_id=str(scoped_tenant_id),
            event_id=str(event.event_id),
            trigger=trigger.value,
            exc_info=True,
        )

    return event.event_id


__all__ = ["record_project_event_and_enqueue_snapshot"]
