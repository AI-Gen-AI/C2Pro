"""G4: durable trusted->ProjectGraph recovery gate (without live deployment)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest


class _Rows:
    def __init__(self, records):
        self.records = records

    def all(self):
        return self.records


class _RecoverySession:
    def __init__(self, records):
        self.records = records
        self.touches = []
        self.queries = []
        self.commits = 0

    async def execute(self, stmt, params):
        self.queries.append((str(stmt), params))
        if "SELECT tenant_id, project_id" in str(stmt):
            return _Rows(self.records)
        assert "UPDATE system_recovery.trusted_projection_index" in str(stmt)
        self.touches.append(params)
        return _Rows([])

    async def commit(self):
        self.commits += 1


class _DbContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, _typ, _exc, _tb):
        return False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("attempts", "enabled", "expected_key", "expected_increment"),
    [
        (0, True, "enqueued", 1),
        (0, False, "flag_disabled", 0),
        (12, True, "exhausted", 0),
    ],
)
async def test_reconcile_pending_obligations_fail_closed(
    monkeypatch, attempts, enabled, expected_key, expected_increment
):
    from src.core.tasks import project_graph_tasks as tasks

    tenant_id, project_id = uuid4(), uuid4()
    session = _RecoverySession(
        [SimpleNamespace(tenant_id=tenant_id, project_id=project_id, attempts=attempts)]
    )
    initialize = AsyncMock()
    enabled_check = AsyncMock(return_value=enabled)
    enqueue = AsyncMock()
    monkeypatch.setattr(tasks, "init_db", initialize)
    monkeypatch.setattr(tasks, "get_raw_session", lambda: _DbContext(session))
    monkeypatch.setattr(tasks, "is_project_graph_enabled", enabled_check)
    monkeypatch.setattr(tasks, "enqueue_project_graph", enqueue)

    result = await tasks.reconcile_trusted_projections(batch_size=5, grace_seconds=120)

    assert result["scanned"] == 1
    assert result[expected_key] == 1
    assert sum(value for name, value in result.items() if name != "scanned") == 1
    assert session.queries[0][1] == {"grace": 120, "limit": 5}
    assert session.touches == [{
        "tenant_id": str(tenant_id),
        "project_id": str(project_id),
        "increment": expected_increment,
    }]
    assert session.commits == 1
    initialize.assert_awaited_once()
    if expected_increment:
        enqueue.assert_awaited_once_with(project_id=project_id, tenant_id=tenant_id)
    else:
        enqueue.assert_not_awaited()
    # Reconcile does not mark work projected. That is reserved for a
    # successful trusted-artifact materialization run in run_project_graph_once.
    assert all("projection_state = 'pending'" in sql for sql, _ in session.queries[1:])


def test_recovery_task_registered_with_300_second_beat_schedule():
    from src.core.tasks.celery_app import celery_app

    task = celery_app.conf.beat_schedule["project-graph-trusted-projection-reconcile"]
    assert task["task"] == "project_graph.reconcile_trusted_projections"
    assert task["schedule"] == 300.0
