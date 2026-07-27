"""Tests for material ProjectEvent to snapshot trigger publishing.

Test Suite ID: TS-UT-TEMPORAL-SNAPSHOT-TRIGGER-001
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

from src.temporal.domain.project_snapshot import SnapshotTrigger


@pytest.mark.asyncio
async def test_records_committed_event_before_non_blocking_snapshot_enqueue(monkeypatch) -> None:
    """TS-UT-TEMPORAL-SNAPSHOT-TRIGGER-001: event lineage commits before Celery enqueue."""
    from src.temporal.application import project_snapshot_trigger

    tenant_id = uuid4()
    project_id = uuid4()
    call_order: list[str] = []
    captured: dict[str, object] = {}

    @asynccontextmanager
    async def fake_session(_tenant_id):
        yield object()
        call_order.append("commit")

    class FakeEventRepository:
        def __init__(self, _session) -> None:
            pass

        async def append(self, event):
            call_order.append("append")
            captured["event"] = event
            return event

    def fake_enqueue(**kwargs) -> None:
        call_order.append("enqueue")
        captured["enqueue"] = kwargs

    monkeypatch.setattr(project_snapshot_trigger, "get_session_with_tenant", fake_session)
    monkeypatch.setattr(
        project_snapshot_trigger,
        "SqlAlchemyProjectEventRepository",
        FakeEventRepository,
    )
    monkeypatch.setattr(project_snapshot_trigger, "enqueue_project_snapshot", fake_enqueue)

    event_id = await project_snapshot_trigger.record_project_event_and_enqueue_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        event_type="graph.completed",
        payload={"analysis_id": "analysis-1"},
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        actor="analysis_graph",
    )

    event = captured["event"]
    assert event.event_id == event_id
    assert event.project_id == project_id
    assert event.tenant_id == tenant_id
    assert event.event_type == "graph.completed"
    assert captured["enqueue"] == {
        "project_id": project_id,
        "tenant_id": tenant_id,
        "trigger": SnapshotTrigger.GRAPH_COMPLETED,
        "source_event_id": event_id,
    }
    assert call_order == ["append", "commit", "enqueue"]


@pytest.mark.asyncio
async def test_snapshot_enqueue_failure_does_not_lose_committed_event_or_block_caller(monkeypatch) -> None:
    """TS-UT-TEMPORAL-SNAPSHOT-TRIGGER-001: Celery publish is explicitly fail-open."""
    from src.temporal.application import project_snapshot_trigger

    @asynccontextmanager
    async def fake_session(_tenant_id):
        yield object()

    class FakeEventRepository:
        def __init__(self, _session) -> None:
            pass

        async def append(self, event):
            return event

    def failing_enqueue(**_kwargs) -> None:
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(project_snapshot_trigger, "get_session_with_tenant", fake_session)
    monkeypatch.setattr(
        project_snapshot_trigger,
        "SqlAlchemyProjectEventRepository",
        FakeEventRepository,
    )
    monkeypatch.setattr(project_snapshot_trigger, "enqueue_project_snapshot", failing_enqueue)

    event_id = await project_snapshot_trigger.record_project_event_and_enqueue_snapshot(
        project_id=uuid4(),
        tenant_id=uuid4(),
        event_type="hitl.correction",
        payload={"review_item_id": "review-1"},
        trigger=SnapshotTrigger.HITL_CORRECTION,
    )

    assert event_id is not None
