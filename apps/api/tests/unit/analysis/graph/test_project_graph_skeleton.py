"""ProjectGraph skeleton tests (ADR-017 / TASK-V3-017-02).

TS-UT-ADR017-PG-001
"""

from __future__ import annotations

import inspect
from contextlib import contextmanager
from uuid import uuid4

import pytest

from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.domain.node_result import NodeStatus
from src.coherence.models import EnrichedCoherenceResult


def _artifact(document_id: str, *, revision_id: str) -> DocumentArtifact:
    return DocumentArtifact(
        document_id=document_id,
        document_revision_id=revision_id,
        doc_type="contract",
        document_category="LEGAL",
    )


def _initial_state() -> dict[str, object]:
    artifacts = [
        _artifact("doc-1", revision_id=str(uuid4())),
        _artifact("doc-2", revision_id=str(uuid4())),
    ]
    return {
        "project_id": uuid4(),
        "tenant_id": uuid4(),
        "trigger_event_id": None,
        "previous_snapshot_id": None,
        "changed_artifact_ids": [],
        "artifacts": artifacts,
        "coherence_result": {"should": "be cleared by honest-null stub"},
        "impact_result": {"should": "be cleared by honest-null stub"},
        "health_result": {"should": "be cleared by honest-null stub"},
        "snapshot_id": None,
        "node_results": [],
    }


def _disable_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """TS-UT-ADR017-PG-001 - Neutralize local LangSmith tracer flakes."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGCHAIN_CALLBACKS_BACKGROUND", "false")
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    from langchain_core.tracers import context as langchain_tracing_context
    from langsmith import run_helpers as langsmith_run_helpers
    from langsmith import utils as langsmith_utils

    @contextmanager
    def _disabled_tracing_v2(*_args: object, **_kwargs: object):
        yield None

    monkeypatch.setattr(
        langsmith_run_helpers,
        "get_tracing_context",
        lambda: {"parent": None, "project_name": None, "enabled": False},
    )
    monkeypatch.setattr(langsmith_utils, "tracing_is_enabled", lambda: False)
    monkeypatch.setattr(langchain_tracing_context, "_tracing_v2_is_enabled", lambda: False)
    monkeypatch.setattr(langchain_tracing_context, "tracing_v2_enabled", _disabled_tracing_v2)
    monkeypatch.setattr(
        "langchain_core.callbacks.manager._get_tracer_project",
        lambda *_args, **_kwargs: "default",
        raising=False,
    )
    monkeypatch.setattr(
        "langchain_core.tracers.context._get_tracer_project",
        lambda *_args, **_kwargs: "default",
        raising=False,
    )


def _patch_cross_doc_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.analysis.adapters.graph import project_graph

    async def _fake_evaluate(_clauses, _project_id, *, config, seed_signals, seed_coverage):
        return EnrichedCoherenceResult(
            overall_score=None,
            score_reason="insufficient_cross_doc_fixture",
            score_missing_dimensions=["SCOPE"],
        )

    async def _llm_disabled(_tenant_id):
        return False

    monkeypatch.setattr(project_graph, "evaluate_coherence_async", _fake_evaluate)
    monkeypatch.setattr(project_graph, "is_coherence_llm_enabled", _llm_disabled)


def test_build_project_graph_compiles() -> None:
    from src.analysis.adapters.graph.project_graph import build_project_graph

    compiled = build_project_graph()

    assert hasattr(compiled, "ainvoke")


@pytest.mark.asyncio
async def test_project_graph_runs_serially_and_emits_every_node_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.analysis.adapters.graph.project_graph import (
        PROJECT_GRAPH_NODE_ORDER,
        build_project_graph,
    )

    _disable_tracing(monkeypatch)
    _patch_cross_doc_engine(monkeypatch)
    result = await build_project_graph().ainvoke(_initial_state())

    node_results = result["node_results"]
    assert [node_result.node for node_result in node_results] == PROJECT_GRAPH_NODE_ORDER
    assert len({node_result.node for node_result in node_results}) == len(PROJECT_GRAPH_NODE_ORDER)
    assert node_results[0].status is NodeStatus.OK
    assert result["changed_artifact_ids"] == [
        artifact.document_revision_id for artifact in result["artifacts"]
    ]


@pytest.mark.asyncio
async def test_project_graph_downstream_stubs_remain_honest_null_and_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.analysis.adapters.graph.project_graph import build_project_graph

    _disable_tracing(monkeypatch)
    _patch_cross_doc_engine(monkeypatch)
    result = await build_project_graph().ainvoke(_initial_state())
    by_node = {node_result.node: node_result for node_result in result["node_results"]}

    assert result["coherence_result"] is not None
    assert by_node["cross_doc_coherence"].status is NodeStatus.OK
    assert result["impact_result"] is None
    assert result["health_result"] is not None
    assert by_node["health"].status is NodeStatus.OK
    assert result["snapshot_id"] is None
    assert by_node["change_impact"].status is NodeStatus.SKIPPED
    assert "no prior snapshot" in (by_node["change_impact"].degradation_reason or "")
    for node_name in {
        "write_snapshot",
        "alert_correlation",
        "hitl_routing",
    }:
        assert by_node[node_name].status is NodeStatus.SKIPPED
        assert "pending" in (by_node[node_name].degradation_reason or "")


@pytest.mark.asyncio
async def test_project_graph_skeleton_has_no_llm_celery_or_db_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.analysis.adapters.graph.project_graph as project_graph

    source = inspect.getsource(project_graph)
    forbidden_tokens = [
        "get_anthropic_wrapper",
        "generate_structured",
        "bypass_anonymization",
        "celery",
        ".delay(",
        "AsyncSession",
        "sessionmaker",
    ]

    for token in forbidden_tokens:
        assert token not in source

    _disable_tracing(monkeypatch)
    _patch_cross_doc_engine(monkeypatch)
    result = await project_graph.build_project_graph().ainvoke(_initial_state())

    assert result["coherence_result"] is not None


@pytest.mark.asyncio
async def test_project_graph_feature_gate_fails_closed(monkeypatch) -> None:
    from src.analysis.adapters.graph import project_graph

    def _explode(*_args, **_kwargs):
        raise RuntimeError("tenant flag storage unavailable")

    monkeypatch.setattr(project_graph, "get_raw_session", _explode, raising=False)

    assert await project_graph.is_project_graph_enabled(uuid4()) is False
