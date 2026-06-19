"""ProjectGraph trigger tests (ADR-017 / TASK-V3-017-03).

TS-UT-ADR017-TRG-001
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.analysis.domain.contracts import DocumentArtifact


class _FakeGraph:
    async def ainvoke(self, state):
        return {**state, "ran": True}


class _FakeRepo:
    def __init__(self, artifacts: list[DocumentArtifact]) -> None:
        self.artifacts = artifacts

    async def list_active_for_project(self, *, project_id, tenant_id):
        return self.artifacts


def _artifact() -> DocumentArtifact:
    return DocumentArtifact(document_id=str(uuid4()), doc_type="contract")


@pytest.mark.asyncio
async def test_enqueue_project_graph_flag_off_suppresses_delay(monkeypatch) -> None:
    from src.core.tasks import project_graph_tasks

    async def _disabled(_tenant_id):
        return False

    calls: list[dict[str, str | None]] = []
    monkeypatch.setattr(project_graph_tasks, "is_project_graph_enabled", _disabled)
    monkeypatch.setattr(project_graph_tasks.run_project_graph, "delay", lambda **kwargs: calls.append(kwargs))

    result = await project_graph_tasks.enqueue_project_graph(
        project_id=uuid4(),
        tenant_id=uuid4(),
    )

    assert result is None
    assert calls == []


@pytest.mark.asyncio
async def test_enqueue_project_graph_flag_on_calls_delay(monkeypatch) -> None:
    from src.core.tasks import project_graph_tasks

    async def _enabled(_tenant_id):
        return True

    calls: list[dict[str, str | None]] = []
    monkeypatch.setattr(project_graph_tasks, "is_project_graph_enabled", _enabled)
    monkeypatch.setattr(project_graph_tasks.run_project_graph, "delay", lambda **kwargs: calls.append(kwargs))

    project_id = uuid4()
    tenant_id = uuid4()
    result = await project_graph_tasks.enqueue_project_graph(
        project_id=project_id,
        tenant_id=tenant_id,
    )

    assert result is None
    assert calls == [
        {
            "project_id": str(project_id),
            "tenant_id": str(tenant_id),
            "trigger_event_id": None,
        }
    ]


@pytest.mark.asyncio
async def test_run_project_graph_once_loads_artifacts_and_runs_skeleton(monkeypatch) -> None:
    from src.core.tasks import project_graph_tasks

    artifact = _artifact()
    fake_graph = _FakeGraph()
    monkeypatch.setattr(project_graph_tasks, "build_project_graph", lambda: fake_graph)

    result = await project_graph_tasks.run_project_graph_once(
        project_id=uuid4(),
        tenant_id=uuid4(),
        artifact_repository=_FakeRepo([artifact]),
    )

    assert result["status"] == "ok"
    assert result["artifact_count"] == 1


@pytest.mark.asyncio
async def test_tier1_completion_swallow_store_and_enqueue_errors(monkeypatch) -> None:
    from src.analysis.application import document_artifact_completion

    async def _explode(*_args, **_kwargs):
        raise RuntimeError("store unavailable")

    monkeypatch.setattr(document_artifact_completion, "_persist_artifact", _explode)

    await document_artifact_completion.persist_artifact_and_enqueue_project_graph(
        {
            "project_id": str(uuid4()),
            "tenant_id": str(uuid4()),
            "document_id": str(uuid4()),
            "doc_type": "contract",
        }
    )
