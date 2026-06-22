"""Celery snapshot task tests (ADR-015 / TASK-V3-015-05)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.temporal.domain.project_snapshot import SnapshotTrigger


class _Session:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.executed: list[str] = []

    async def execute(self, statement):
        self.executed.append(str(statement))
        return SimpleNamespace(all=lambda: [])

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_write_project_snapshot_async_commits_once(monkeypatch) -> None:
    from src.core.tasks import snapshot_tasks

    session = _Session()

    @asynccontextmanager
    async def fake_raw_session():
        yield session

    class FakeWriter:
        def __init__(self, **_kwargs) -> None:
            pass

        async def write_snapshot(self, **kwargs):
            return SimpleNamespace(snapshot_id=uuid4(), **kwargs)

    monkeypatch.setattr(snapshot_tasks, "init_db", lambda: None)
    monkeypatch.setattr(snapshot_tasks, "get_raw_session", fake_raw_session)
    monkeypatch.setattr(snapshot_tasks, "SnapshotWriter", FakeWriter)

    result = await snapshot_tasks._write_project_snapshot_async(
        project_id=uuid4(),
        tenant_id=uuid4(),
        trigger=SnapshotTrigger.REVISION_INGESTED.value,
    )

    assert result["status"] == "ok"
    assert session.commits == 1
    assert session.rollbacks == 0
    assert any("app.current_tenant" in statement for statement in session.executed)


def test_enqueue_project_snapshot_calls_delay(monkeypatch) -> None:
    from src.core.tasks import snapshot_tasks

    calls: list[dict] = []
    monkeypatch.setattr(
        snapshot_tasks.write_project_snapshot,
        "delay",
        lambda **kwargs: calls.append(kwargs) or SimpleNamespace(id="task-1"),
    )
    project_id = uuid4()
    tenant_id = uuid4()
    source_event_id = uuid4()

    result = snapshot_tasks.enqueue_project_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.REVISION_INGESTED,
        source_event_id=source_event_id,
    )

    assert result.id == "task-1"
    assert calls == [
        {
            "project_id": str(project_id),
            "tenant_id": str(tenant_id),
            "trigger": SnapshotTrigger.REVISION_INGESTED.value,
            "source_event_id": str(source_event_id),
        }
    ]


@pytest.mark.asyncio
async def test_enqueue_daily_project_snapshots_async_enqueues_active_projects(
    monkeypatch,
) -> None:
    from src.core.tasks import snapshot_tasks

    tenant_id = uuid4()
    project_id = uuid4()

    class _Result:
        def all(self):
            return [(project_id, tenant_id)]

    class _DailySession(_Session):
        async def execute(self, statement):
            self.executed.append(str(statement))
            return _Result()

    session = _DailySession()

    @asynccontextmanager
    async def fake_raw_session():
        yield session

    calls: list[dict] = []
    monkeypatch.setattr(snapshot_tasks, "init_db", lambda: None)
    monkeypatch.setattr(snapshot_tasks, "get_raw_session", fake_raw_session)
    monkeypatch.setattr(
        snapshot_tasks,
        "enqueue_project_snapshot",
        lambda **kwargs: calls.append(kwargs) or SimpleNamespace(id="daily-1"),
    )

    result = await snapshot_tasks._enqueue_daily_project_snapshots_async(batch_size=10)

    assert result == {"status": "ok", "enqueued": 1}
    assert calls == [
        {
            "project_id": project_id,
            "tenant_id": tenant_id,
            "trigger": SnapshotTrigger.SCHEDULED,
            "source_event_id": None,
        }
    ]
