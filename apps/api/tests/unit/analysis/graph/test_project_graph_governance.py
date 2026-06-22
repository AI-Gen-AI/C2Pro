"""ProjectGraph governance tests (ADR-017 / TASK-V3-017-05).

TS-UT-ADR017-GOV-001
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest


class _FakeCache:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    async def get(self, key: str, default: object | None = None) -> object | None:
        return self.values.get(key, default)

    async def set(self, key: str, value: object, ttl: int | None = None) -> bool:  # noqa: ARG002
        self.values[key] = value
        return True

    async def delete(self, key: str) -> bool:
        return self.values.pop(key, None) is not None

    async def incr(
        self,
        key: str,
        *,
        amount: int = 1,
        ttl_seconds: int | None = None,  # noqa: ARG002
    ) -> int:
        current = int(self.values.get(key, 0) or 0) + amount
        self.values[key] = current
        return current

    async def decr(self, key: str, *, amount: int = 1) -> int:
        current = max(0, int(self.values.get(key, 0) or 0) - amount)
        if current == 0:
            self.values.pop(key, None)
            return 0
        self.values[key] = current
        return current

    async def set_if_absent(self, key: str, value: object, *, ttl_seconds: int) -> bool:  # noqa: ARG002
        if key in self.values:
            return False
        self.values[key] = value
        return True


class _RacyLegacyCache(_FakeCache):
    async def get(self, key: str, default: object | None = None) -> object | None:
        value = self.values.get(key, default)
        await asyncio.sleep(0)
        return value

    async def set(self, key: str, value: object, ttl: int | None = None) -> bool:  # noqa: ARG002
        await asyncio.sleep(0)
        self.values[key] = value
        return True


@pytest.mark.asyncio
async def test_project_graph_debounce_suppresses_duplicate_enqueue(monkeypatch) -> None:
    from src.core.tasks import project_graph_tasks
    from src.core.tasks.project_graph_governance import ProjectGraphGovernance

    tenant_id = uuid4()
    project_id = uuid4()
    calls: list[dict[str, str | None]] = []
    governance = ProjectGraphGovernance(cache=_FakeCache())

    monkeypatch.setattr(project_graph_tasks, "is_project_graph_enabled", _always_enabled)
    monkeypatch.setattr(
        project_graph_tasks.run_project_graph,
        "delay",
        lambda **kwargs: calls.append(kwargs),
    )

    await project_graph_tasks.enqueue_project_graph(
        project_id=project_id,
        tenant_id=tenant_id,
        governance=governance,
    )
    await project_graph_tasks.enqueue_project_graph(
        project_id=project_id,
        tenant_id=tenant_id,
        governance=governance,
    )

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_project_graph_tenant_slot_released_on_success_and_error() -> None:
    from src.core.tasks.project_graph_governance import ProjectGraphGovernance

    tenant_id = uuid4()
    governance = ProjectGraphGovernance(cache=_FakeCache(), tenant_concurrency_limit=1)

    assert await governance.acquire_tenant_slot(tenant_id) is True
    assert await governance.acquire_tenant_slot(tenant_id) is False

    await governance.release_tenant_slot(tenant_id)
    assert await governance.acquire_tenant_slot(tenant_id) is True

    await governance.release_tenant_slot(tenant_id)
    await governance.release_tenant_slot(tenant_id)
    assert await governance.current_tenant_slots(tenant_id) == 0


@pytest.mark.asyncio
async def test_project_graph_concurrent_acquire_never_exceeds_limit() -> None:
    from src.core.tasks.project_graph_governance import ProjectGraphGovernance

    tenant_id = uuid4()
    limit = 3
    governance = ProjectGraphGovernance(
        cache=_RacyLegacyCache(),
        tenant_concurrency_limit=limit,
    )

    results = await asyncio.gather(
        *(governance.acquire_tenant_slot(tenant_id) for _ in range(limit + 5))
    )

    assert results.count(True) == limit
    assert results.count(False) == 5
    assert await governance.current_tenant_slots(tenant_id) == limit


@pytest.mark.asyncio
async def test_project_graph_concurrent_debounce_has_single_winner() -> None:
    from src.core.tasks.project_graph_governance import ProjectGraphGovernance

    project_id = uuid4()
    governance = ProjectGraphGovernance(cache=_RacyLegacyCache())

    results = await asyncio.gather(
        *(governance.should_enqueue_project(project_id) for _ in range(8))
    )

    assert results.count(True) == 1
    assert results.count(False) == 7


@pytest.mark.asyncio
async def test_project_graph_governance_fails_open_without_cache() -> None:
    from src.core.tasks.project_graph_governance import ProjectGraphGovernance

    governance = ProjectGraphGovernance(cache=None)

    assert await governance.acquire_tenant_slot(uuid4()) is True
    assert await governance.should_enqueue_project(uuid4()) is True


@pytest.mark.asyncio
async def test_project_graph_over_limit_requeues_without_running(monkeypatch) -> None:
    from src.core.tasks import project_graph_tasks
    from src.core.tasks.project_graph_governance import ProjectGraphGovernance

    tenant_id = uuid4()
    project_id = uuid4()
    requeued: list[dict[str, object]] = []
    governance = ProjectGraphGovernance(cache=_FakeCache(), tenant_concurrency_limit=0)

    monkeypatch.setattr(
        project_graph_tasks.run_project_graph,
        "apply_async",
        lambda **kwargs: requeued.append(kwargs),
        raising=False,
    )

    result = await project_graph_tasks._run_project_graph_async(
        project_id=project_id,
        tenant_id=tenant_id,
        governance=governance,
    )

    assert result["status"] == "requeued"
    assert requeued[0]["countdown"] == governance.requeue_countdown_seconds
    assert await governance.current_tenant_slots(tenant_id) == 0


@pytest.mark.asyncio
async def test_project_graph_terminal_failure_records_dlq(monkeypatch) -> None:
    from src.core.tasks import project_graph_tasks

    tenant_id = uuid4()
    project_id = uuid4()
    pushed: list[dict[str, object]] = []

    class FakeDLQService:
        async def push(self, **kwargs):
            pushed.append(kwargs)
            return uuid4()

    monkeypatch.setattr(project_graph_tasks, "DLQService", FakeDLQService)

    await project_graph_tasks.record_project_graph_dead_letter(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger_event_id=None,
        error=RuntimeError("boom"),
    )

    assert pushed[0]["tenant_id"] == tenant_id
    assert pushed[0]["task_type"] == "project_graph.run"
    assert pushed[0]["payload"]["project_id"] == str(project_id)


async def _always_enabled(_tenant_id) -> bool:
    return True
