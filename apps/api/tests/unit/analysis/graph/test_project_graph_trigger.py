"""ProjectGraph trigger tests (ADR-017 / TASK-V3-017-03).

TS-UT-ADR017-TRG-001
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.analysis.domain.contracts import DocumentArtifact
from src.core.tenants.types import TenantId


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


def test_run_project_graph_normalizes_tenant_once_at_task_boundary(monkeypatch) -> None:
    """TS-UT-ADR017-TRG-001: normalize serialized tenant before graph application code."""
    from src.core.tasks import project_graph_tasks

    project_id = uuid4()
    raw_tenant_id = str(uuid4())
    normalized_tenant_id = TenantId(uuid4())
    normalize = Mock(return_value=normalized_tenant_id)
    captured: dict[str, object] = {}

    async def fake_run_project_graph_async(**kwargs):
        captured.update(kwargs)
        return {"status": "ok"}

    monkeypatch.setattr(project_graph_tasks, "require_tenant_id", normalize, raising=False)
    monkeypatch.setattr(
        project_graph_tasks,
        "_run_project_graph_async",
        fake_run_project_graph_async,
    )

    result = project_graph_tasks.run_project_graph(
        None,
        project_id=str(project_id),
        tenant_id=raw_tenant_id,
    )

    normalize.assert_called_once_with(raw_tenant_id)
    assert captured["tenant_id"] is normalized_tenant_id
    assert result == {"status": "ok"}


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


@pytest.mark.asyncio
async def test_document_artifact_completion_normalizes_tenant_at_state_boundary(monkeypatch) -> None:
    """TS-UT-ADR017-TRG-001: normalize graph-state tenant before persistence ports."""
    from src.analysis.application import document_artifact_completion

    project_id = uuid4()
    raw_tenant_id = str(uuid4())
    normalized_tenant_id = TenantId(uuid4())
    normalize = Mock(return_value=normalized_tenant_id)
    captured: dict[str, object] = {}

    class FakeSession:
        async def execute(self, _statement):
            return None

        async def commit(self) -> None:
            return None

        async def rollback(self) -> None:
            return None

    class FakeRepository:
        def __init__(self, _session) -> None:
            pass

        async def save(self, _artifact, **kwargs):
            captured.update(kwargs)

    @asynccontextmanager
    async def fake_raw_session():
        yield FakeSession()

    async def no_op(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        document_artifact_completion,
        "require_tenant_id",
        normalize,
        raising=False,
    )
    monkeypatch.setattr(document_artifact_completion, "init_db", no_op)
    monkeypatch.setattr(document_artifact_completion, "get_raw_session", fake_raw_session)
    monkeypatch.setattr(
        document_artifact_completion,
        "SqlAlchemyDocumentArtifactRepository",
        FakeRepository,
    )
    monkeypatch.setattr(
        document_artifact_completion,
        "build_document_artifact",
        lambda _state: SimpleNamespace(),
    )
    monkeypatch.setattr(document_artifact_completion, "enqueue_project_graph", no_op)

    await document_artifact_completion._persist_artifact(
        {
            "project_id": str(project_id),
            "tenant_id": raw_tenant_id,
        }
    )

    normalize.assert_called_once_with(raw_tenant_id)
    assert captured["tenant_id"] is normalized_tenant_id
