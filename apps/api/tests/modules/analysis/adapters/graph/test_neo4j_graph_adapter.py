"""
Refers to Suite ID: TS-UAD-PER-GRP-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from src.analysis.adapters.graph.neo4j_client import Neo4jGraphClient
from src.analysis.adapters.graph.knowledge_graph import GraphPath


@dataclass
class _FakeResult:
    rows: list[dict[str, Any]]

    def data(self) -> list[dict[str, Any]]:
        return self.rows


class _FakeSession:
    def __init__(self) -> None:
        self.queries: list[tuple[str, dict[str, Any]]] = []
        self.path_rows: list[dict[str, Any]] = []
        self.entered = False
        self.exited = False

    def run(self, query: str, **params: Any) -> _FakeResult:
        self.queries.append((query, params))
        if "shortestPath" in query:
            return _FakeResult(self.path_rows)
        return _FakeResult([])

    def __enter__(self) -> "_FakeSession":
        self.entered = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.exited = True
        return None


class _FakeDriver:
    def __init__(self) -> None:
        self.session_obj = _FakeSession()

    def session(self) -> _FakeSession:
        return self.session_obj


@pytest.fixture
def driver() -> _FakeDriver:
    return _FakeDriver()


def test_upsert_node_merges_label_and_key(driver: _FakeDriver) -> None:
    client = Neo4jGraphClient(driver)
    client.upsert_node(
        label="Project",
        key="id",
        key_value="proj-1",
        properties={"name": "Alpha"},
    )

    query, _ = driver.session_obj.queries[-1]
    assert "MERGE (n:Project {id: $key_value})" in query


def test_upsert_node_sets_properties(driver: _FakeDriver) -> None:
    client = Neo4jGraphClient(driver)
    client.upsert_node(
        label="Task",
        key="code",
        key_value="T-1",
        properties={"status": "open"},
    )

    query, params = driver.session_obj.queries[-1]
    assert "SET n += $props" in query
    assert params["props"] == {"status": "open"}


def test_upsert_node_passes_key_value_param(driver: _FakeDriver) -> None:
    client = Neo4jGraphClient(driver)
    client.upsert_node(
        label="Clause",
        key="id",
        key_value="clause-9",
        properties={},
    )

    _, params = driver.session_obj.queries[-1]
    assert params["key_value"] == "clause-9"


def test_upsert_edge_merges_nodes_and_relation(driver: _FakeDriver) -> None:
    client = Neo4jGraphClient(driver)
    client.upsert_edge(
        source_label="Project",
        source_key="id",
        source_value="proj-1",
        target_label="Task",
        target_key="id",
        target_value="task-1",
        relation="DEPENDS_ON",
        properties={"weight": 1},
    )

    query, _ = driver.session_obj.queries[-1]
    assert "MERGE (a:Project {id: $source_value})" in query
    assert "MERGE (b:Task {id: $target_value})" in query
    assert "MERGE (a)-[r:DEPENDS_ON]->(b)" in query


def test_upsert_edge_sets_properties(driver: _FakeDriver) -> None:
    client = Neo4jGraphClient(driver)
    client.upsert_edge(
        source_label="Project",
        source_key="id",
        source_value="proj-1",
        target_label="Task",
        target_key="id",
        target_value="task-1",
        relation="ASSIGNED",
        properties={"role": "owner"},
    )

    query, params = driver.session_obj.queries[-1]
    assert "SET r += $props" in query
    assert params["props"] == {"role": "owner"}


def test_upsert_edge_uses_empty_props_when_none(driver: _FakeDriver) -> None:
    client = Neo4jGraphClient(driver)
    client.upsert_edge(
        source_label="Project",
        source_key="id",
        source_value="proj-1",
        target_label="Task",
        target_key="id",
        target_value="task-1",
        relation="LINKED",
        properties=None,
    )

    _, params = driver.session_obj.queries[-1]
    assert params["props"] == {}


def test_upsert_edge_passes_source_target_params(driver: _FakeDriver) -> None:
    client = Neo4jGraphClient(driver)
    client.upsert_edge(
        source_label="Project",
        source_key="id",
        source_value="proj-2",
        target_label="Task",
        target_key="id",
        target_value="task-2",
        relation="BLOCKS",
        properties={"lag": 2},
    )

    _, params = driver.session_obj.queries[-1]
    assert params["source_value"] == "proj-2"
    assert params["target_value"] == "task-2"


def test_find_shortest_path_returns_empty_when_no_rows(driver: _FakeDriver) -> None:
    client = Neo4jGraphClient(driver)
    path = client.find_shortest_path(
        source_label="Project",
        source_key="id",
        source_value="proj-x",
        target_label="Task",
        target_key="id",
        target_value="task-x",
    )

    assert isinstance(path, GraphPath)
    assert path.nodes == []
    assert path.edges == []


def test_find_shortest_path_returns_graph_path(driver: _FakeDriver) -> None:
    driver.session_obj.path_rows = [
        {"nodes": ["proj-1", "task-1"], "rels": ["DEPENDS_ON"]}
    ]
    client = Neo4jGraphClient(driver)
    path = client.find_shortest_path(
        source_label="Project",
        source_key="id",
        source_value="proj-1",
        target_label="Task",
        target_key="id",
        target_value="task-1",
    )

    assert path.nodes == ["proj-1", "task-1"]
    assert path.edges == ["DEPENDS_ON"]


def test_find_shortest_path_query_contains_shortest_path(driver: _FakeDriver) -> None:
    client = Neo4jGraphClient(driver)
    client.find_shortest_path(
        source_label="Project",
        source_key="id",
        source_value="proj-1",
        target_label="Task",
        target_key="id",
        target_value="task-1",
    )

    query, _ = driver.session_obj.queries[-1]
    assert "shortestPath" in query


def test_find_shortest_path_limits_depth(driver: _FakeDriver) -> None:
    client = Neo4jGraphClient(driver)
    client.find_shortest_path(
        source_label="Project",
        source_key="id",
        source_value="proj-1",
        target_label="Task",
        target_key="id",
        target_value="task-1",
    )

    query, _ = driver.session_obj.queries[-1]
    assert "[*..6]" in query


def test_find_shortest_path_returns_nodes_and_rels(driver: _FakeDriver) -> None:
    client = Neo4jGraphClient(driver)
    client.find_shortest_path(
        source_label="Project",
        source_key="id",
        source_value="proj-1",
        target_label="Task",
        target_key="id",
        target_value="task-1",
    )

    query, _ = driver.session_obj.queries[-1]
    assert "RETURN [n IN nodes(p)" in query
    assert "relationships(p)" in query


def test_upsert_node_uses_context_manager(driver: _FakeDriver) -> None:
    client = Neo4jGraphClient(driver)
    client.upsert_node(
        label="Project",
        key="id",
        key_value="proj-1",
        properties={"name": "Alpha"},
    )

    assert driver.session_obj.entered is True
    assert driver.session_obj.exited is True


def test_find_shortest_path_uses_context_manager(driver: _FakeDriver) -> None:
    client = Neo4jGraphClient(driver)
    client.find_shortest_path(
        source_label="Project",
        source_key="id",
        source_value="proj-1",
        target_label="Task",
        target_key="id",
        target_value="task-1",
    )

    assert driver.session_obj.entered is True
    assert driver.session_obj.exited is True
