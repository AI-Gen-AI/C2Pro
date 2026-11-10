"""G4: the beat reconciliation touch must stay tenant-scoped.

An artifact UUID is globally unique today, but an operator/worker raw SQL
statement must still carry the tenant predicate when acknowledging work.
This test exercises the actual reconciliation method without Celery or a
production database; separate PostgreSQL and Railway gates remain required.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.core.tasks import materialization_tasks

pytestmark = pytest.mark.asyncio


async def test_reconciliation_updates_checked_at_with_artifact_and_tenant(monkeypatch):
    rows = [
        SimpleNamespace(artifact_id=uuid4(), tenant_id=uuid4()),
        SimpleNamespace(artifact_id=uuid4(), tenant_id=uuid4()),
    ]
    seen: list[tuple[object, dict[str, object]]] = []
    dispatched: list[tuple[object, object]] = []
    commits = 0

    class FakeQueryResult:
        def all(self):
            return rows

    class FakeSession:
        async def execute(self, sql, params):
            seen.append((sql, params))
            if sql is materialization_tasks._PENDING_MATERIALIZATIONS_SQL:
                return FakeQueryResult()
            assert sql is materialization_tasks._TOUCH_SQL
            return None

        async def commit(self):
            nonlocal commits
            commits += 1

    @asynccontextmanager
    async def factory():
        yield FakeSession()

    monkeypatch.setattr(
        materialization_tasks,
        "enqueue_materialization",
        lambda *, artifact_id, tenant_id: dispatched.append((artifact_id, tenant_id)),
    )

    result = await materialization_tasks.reconcile_pending_materializations(
        grace_seconds=0, session_factory=factory
    )

    assert result == {"scanned": 2, "enqueued": 2}
    assert commits == 1
    assert dispatched == [(row.artifact_id, row.tenant_id) for row in rows]
    assert "tenant_id = cast(:tenant_id as uuid)" in str(
        materialization_tasks._TOUCH_SQL
    )
    touches = [
        params for sql, params in seen
        if sql is materialization_tasks._TOUCH_SQL
    ]
    assert touches == [
        {"artifact_id": str(row.artifact_id), "tenant_id": str(row.tenant_id)}
        for row in rows
    ]
