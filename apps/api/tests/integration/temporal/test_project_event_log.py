"""Integration tests for ProjectEvent append-only log (ADR-015 / TASK-V3-015-03)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.domain.project_event import ProjectEvent

pytestmark = pytest.mark.asyncio


def _now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _event(project_id: UUID, tenant_id: UUID, occurred_at: datetime) -> ProjectEvent:
    return ProjectEvent(
        event_id=uuid4(),
        project_id=project_id,
        tenant_id=tenant_id,
        event_type="revision.ingested",
        payload={"ok": True},
        occurred_at=occurred_at,
        created_at=_now_naive(),
    )


async def test_append_events_lists_ordered_and_since_filtered(db: AsyncSession) -> None:
    repo = SqlAlchemyProjectEventRepository(db)
    project_id = uuid4()
    tenant_id = uuid4()
    base = _now_naive()
    older = _event(project_id, tenant_id, base - timedelta(minutes=2))
    newer = _event(project_id, tenant_id, base)

    await repo.append(newer)
    await repo.append(older)
    await db.commit()

    loaded = await repo.list_for_project(project_id, tenant_id)
    assert [event.event_id for event in loaded] == [older.event_id, newer.event_id]

    tail = await repo.list_for_project(project_id, tenant_id, since=base - timedelta(minutes=1))
    assert [event.event_id for event in tail] == [newer.event_id]


async def test_project_events_reject_update_and_delete(db: AsyncSession) -> None:
    repo = SqlAlchemyProjectEventRepository(db)
    event = _event(uuid4(), uuid4(), _now_naive())
    await repo.append(event)
    await db.commit()

    with pytest.raises(DBAPIError):
        await db.execute(
            text("UPDATE project_events SET actor = 'x' WHERE event_id = :event_id"),
            {"event_id": event.event_id},
        )
        await db.commit()
    await db.rollback()

    with pytest.raises(DBAPIError):
        await db.execute(
            text("DELETE FROM project_events WHERE event_id = :event_id"),
            {"event_id": event.event_id},
        )
        await db.commit()
    await db.rollback()
