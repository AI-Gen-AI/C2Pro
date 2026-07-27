# ruff: noqa: S101
"""Tests for N10 ``knowledge_graph_builder_node`` (TASK-HOTFIX-F4).

The node builds a project knowledge graph via ``ProjectKnowledgeGraph`` and is
expected to:

  * emit an ``OK`` NodeResult with the serialized nodes/edges on the healthy
    path, and
  * fail *open* (emit a ``FAILED`` NodeResult, keep empty graph state, and let
    the pipeline continue to persist) when the adapter raises.

Prior to F4 the healthy path had no coverage, so a regression that pushed the
node into its degraded branch (e.g. a missing import or repository method)
would have gone unnoticed. These tests pin both branches.
"""

from __future__ import annotations

import networkx as nx
import pytest

from src.analysis.domain.node_result import NodeStatus

_TENANT = "00000000-0000-0000-0000-000000000099"
_PROJECT = "00000000-0000-0000-0000-000000000001"


def _make_state(**overrides: object) -> dict:
    state: dict = {
        "project_id": _PROJECT,
        "tenant_id": _TENANT,
        "messages": [],
        "node_results": [],
        "knowledge_graph_nodes": [],
        "knowledge_graph_edges": [],
    }
    state.update(overrides)
    return state


class _AsyncSession:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_exc: object) -> None:
        return None


class _FakeAdapter:
    """Stand-in for ProjectKnowledgeGraph used by BuildProjectKnowledgeGraphUseCase."""

    def __init__(self, graph: nx.DiGraph) -> None:
        self._graph = graph

    async def build_graph(self, project_id: object, tenant_id: object) -> nx.DiGraph:
        return self._graph


@pytest.mark.asyncio
async def test_healthy_path_emits_ok_node_result_with_nodes_and_edges(monkeypatch) -> None:
    """TS-HOTFIX-F4-001: a working adapter yields an OK NodeResult, not degraded."""
    from src.analysis.adapters import graph as graph_pkg
    from src.analysis.adapters.graph import nodes_extended

    graph = nx.DiGraph()
    graph.add_node("stk_1", type="STAKEHOLDER", label="Owner", properties={})
    graph.add_node("tsk_1", type="TASK", label="Foundation", properties={})
    graph.add_edge("stk_1", "tsk_1", relation="MANAGES", properties={})

    monkeypatch.setattr(
        graph_pkg,
        "build_project_knowledge_graph",
        lambda _session: _FakeAdapter(graph),
        raising=False,
    )
    monkeypatch.setattr(
        nodes_extended,
        "get_session_with_tenant",
        lambda _tenant: _AsyncSession(),
        raising=False,
    )

    result = await nodes_extended.knowledge_graph_builder_node(_make_state())

    assert [n["id"] for n in result["knowledge_graph_nodes"]] == ["stk_1", "tsk_1"]
    assert result["knowledge_graph_edges"] == [
        {"source": "stk_1", "target": "tsk_1", "data": {"relation": "MANAGES", "properties": {}}}
    ]
    node_result = result["node_results"][-1]
    assert node_result.node == "knowledge_graph"
    assert node_result.status is NodeStatus.OK


@pytest.mark.asyncio
async def test_missing_project_or_tenant_skips_without_degrading() -> None:
    """No project/tenant → empty graph and an explicit SKIPPED NodeResult."""
    from src.analysis.adapters.graph import nodes_extended

    result = await nodes_extended.knowledge_graph_builder_node(
        _make_state(tenant_id=None)
    )

    assert result["knowledge_graph_nodes"] == []
    assert result["knowledge_graph_edges"] == []
    node_result = result["node_results"][-1]
    assert node_result.node == "knowledge_graph"
    assert node_result.status is NodeStatus.SKIPPED
    assert node_result.degradation_reason == "missing_project_or_tenant_id"


@pytest.mark.asyncio
async def test_adapter_failure_fails_open_with_failed_node_result(monkeypatch) -> None:
    """TS-HOTFIX-F4-002: adapter errors degrade to FAILED but do not raise."""
    from src.analysis.adapters import graph as graph_pkg
    from src.analysis.adapters.graph import nodes_extended

    def _boom(_session: object) -> object:
        raise RuntimeError("knowledge graph adapter unavailable")

    persisted: list[object] = []
    monkeypatch.setattr(graph_pkg, "build_project_knowledge_graph", _boom, raising=False)
    monkeypatch.setattr(
        nodes_extended,
        "get_session_with_tenant",
        lambda _tenant: _AsyncSession(),
        raising=False,
    )
    monkeypatch.setattr(
        nodes_extended,
        "_persist_node_error",
        lambda _state, result: persisted.append(result),
        raising=False,
    )

    result = await nodes_extended.knowledge_graph_builder_node(_make_state())

    assert result["knowledge_graph_nodes"] == []
    assert result["knowledge_graph_edges"] == []
    node_result = result["node_results"][-1]
    assert node_result.node == "knowledge_graph"
    assert node_result.status is NodeStatus.FAILED
    assert node_result.error is not None
    assert persisted == [node_result]
