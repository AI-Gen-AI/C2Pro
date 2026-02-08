"""
Neo4j Graph Integration Tests (TDD - RED Phase)

Refers to Suite ID: TS-INT-GRP-NEO-001.
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

    def run(self, query: str, **params: Any) -> _FakeResult:
        self.queries.append((query, params))
        if "shortestPath" in query:
            return _FakeResult(self.path_rows)
        return _FakeResult([])

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeDriver:
    def __init__(self) -> None:
        self.session_obj = _FakeSession()

    def session(self) -> _FakeSession:
        return self.session_obj


def test_neo4j_client_builds_queries_and_reads_paths() -> None:
    """
    Neo4j client should build write queries and parse path results.
    """
    driver = _FakeDriver()
    client = Neo4jGraphClient(driver)

    client.upsert_node(
        label="Project",
        key="id",
        key_value="project-1",
        properties={"name": "Alpha"},
    )

    client.upsert_edge(
        source_label="Project",
        source_key="id",
        source_value="project-1",
        target_label="Task",
        target_key="id",
        target_value="task-1",
        relation="DEPENDS_ON",
        properties={"weight": 1},
    )

    driver.session_obj.path_rows = [
        {"nodes": ["Project:project-1", "Task:task-1"], "rels": ["DEPENDS_ON"]}
    ]
    path = client.find_shortest_path(
        source_label="Project",
        source_key="id",
        source_value="project-1",
        target_label="Task",
        target_key="id",
        target_value="task-1",
    )

    assert isinstance(path, GraphPath)
    assert path.nodes == ["Project:project-1", "Task:task-1"]
    assert path.edges == ["DEPENDS_ON"]

    queries = driver.session_obj.queries
    assert any("MERGE" in query for query, _ in queries)
    assert any("DEPENDS_ON" in query for query, _ in queries)
