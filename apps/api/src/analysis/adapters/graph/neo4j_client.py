"""
Neo4j graph adapter.

Refers to Suite ID: TS-INT-GRP-NEO-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.analysis.adapters.graph.knowledge_graph import GraphPath


class _Neo4jSession(Protocol):
    def run(self, query: str, **params: Any): ...
    def __enter__(self): ...
    def __exit__(self, exc_type, exc, tb) -> None: ...


class _Neo4jDriver(Protocol):
    def session(self) -> _Neo4jSession: ...


@dataclass
class Neo4jGraphClient:
    """Refers to Suite ID: TS-INT-GRP-NEO-001."""

    driver: _Neo4jDriver

    def upsert_node(self, *, label: str, key: str, key_value: str, properties: dict[str, Any]) -> None:
        query = (
            f"MERGE (n:{label} {{{key}: $key_value}}) "
            "SET n += $props"
        )
        with self.driver.session() as session:
            session.run(query, key_value=key_value, props=properties)

    def upsert_edge(
        self,
        *,
        source_label: str,
        source_key: str,
        source_value: str,
        target_label: str,
        target_key: str,
        target_value: str,
        relation: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        query = (
            f"MERGE (a:{source_label} {{{source_key}: $source_value}}) "
            f"MERGE (b:{target_label} {{{target_key}: $target_value}}) "
            f"MERGE (a)-[r:{relation}]->(b) "
            "SET r += $props"
        )
        with self.driver.session() as session:
            session.run(
                query,
                source_value=source_value,
                target_value=target_value,
                props=properties or {},
            )

    def find_shortest_path(
        self,
        *,
        source_label: str,
        source_key: str,
        source_value: str,
        target_label: str,
        target_key: str,
        target_value: str,
    ) -> GraphPath:
        query = (
            f"MATCH (a:{source_label} {{{source_key}: $source_value}}), "
            f"(b:{target_label} {{{target_key}: $target_value}}) "
            "MATCH p = shortestPath((a)-[*..6]->(b)) "
            "RETURN [n IN nodes(p) | n."+source_key+"] AS nodes, "
            "[r IN relationships(p) | type(r)] AS rels"
        )
        with self.driver.session() as session:
            result = session.run(
                query,
                source_value=source_value,
                target_value=target_value,
            )
            rows = result.data()
            if not rows:
                return GraphPath(nodes=[], edges=[])
            return GraphPath(nodes=rows[0]["nodes"], edges=rows[0]["rels"])
