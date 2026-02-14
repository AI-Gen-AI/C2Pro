"""
I5 - Graph Schema + Relationship Integrity (Domain)
Test Suite ID: TS-I5-GRAPH-DOM-001
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

import pytest

try:
    from src.modules.graph.domain.entities import (
        GraphNode,
        GraphEdge,
        NodeProperties,
        EdgeProperties,
    )
    from src.modules.graph.domain.services import GraphService
except ImportError:
    NodeProperties = dict[str, Any]
    EdgeProperties = dict[str, Any]

    @dataclass
    class GraphNode:  # type: ignore[override]
        id: UUID
        type: str
        properties: dict[str, Any] = field(default_factory=dict)

    @dataclass
    class GraphEdge:  # type: ignore[override]
        source_node_id: UUID
        target_node_id: UUID
        type: str
        properties: dict[str, Any] = field(default_factory=dict)

    class GraphService:  # type: ignore[override]
        """Fallback intentionally incomplete to keep QA tests RED before implementation."""

        def __init__(self) -> None:
            self.nodes: dict[UUID, GraphNode] = {}
            self.edges: list[GraphEdge] = []

        def create_node(
            self,
            node_id: UUID,
            node_type: str,
            properties: Optional[NodeProperties] = None,
        ) -> GraphNode:
            node = GraphNode(id=node_id, type=node_type, properties=properties or {})
            self.nodes[node_id] = node
            return node

        def create_edge(
            self,
            source_node_id: UUID,
            target_node_id: UUID,
            edge_type: str,
            properties: Optional[EdgeProperties] = None,
            duplicate_policy: Literal["reject", "merge"] = "reject",
        ) -> GraphEdge:
            edge = GraphEdge(
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                type=edge_type,
                properties=properties or {},
            )
            self.edges.append(edge)
            return edge


@pytest.fixture
def graph_service() -> GraphService:
    return GraphService()


def test_i5_create_relates_to_edge_invalid_missing_node(graph_service: GraphService) -> None:
    """Refers to I5.4: Missing required nodes before edge insertion must fail."""
    existing_node_id = uuid4()
    missing_node_id = uuid4()
    graph_service.create_node(existing_node_id, "Clause", {"text": "Clause A"})

    with pytest.raises(ValueError, match="Source or target node does not exist."):
        graph_service.create_edge(
            source_node_id=existing_node_id,
            target_node_id=missing_node_id,
            edge_type="RELATES_TO",
        )


def test_i5_duplicate_edge_is_rejected_by_policy(graph_service: GraphService) -> None:
    """Refers to I5.2: Duplicate edge behavior must be explicit for reject policy."""
    clause_node_id = uuid4()
    obligation_node_id = uuid4()
    graph_service.create_node(clause_node_id, "Clause", {"text": "Payment terms"})
    graph_service.create_node(obligation_node_id, "Obligation", {"status": "Open"})

    graph_service.create_edge(
        source_node_id=clause_node_id,
        target_node_id=obligation_node_id,
        edge_type="RELATES_TO",
        duplicate_policy="reject",
    )

    with pytest.raises(ValueError, match="Duplicate edge RELATES_TO"):
        graph_service.create_edge(
            source_node_id=clause_node_id,
            target_node_id=obligation_node_id,
            edge_type="RELATES_TO",
            duplicate_policy="reject",
        )
