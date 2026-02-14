"""
I5 Graph Domain Service
Test Suite ID: TS-I5-GRAPH-DOM-001
"""

from typing import Literal
from uuid import UUID

from src.modules.graph.domain.entities import GraphEdge, GraphNode, NodeProperties, EdgeProperties


class GraphService:
    """In-memory graph service with duplicate-edge policy and referential checks."""

    def __init__(self) -> None:
        self.nodes: dict[UUID, GraphNode] = {}
        self.edges: list[GraphEdge] = []

    def create_node(
        self,
        node_id: UUID,
        node_type: str,
        properties: NodeProperties | None = None,
    ) -> GraphNode:
        node = GraphNode(id=node_id, type=node_type, properties=properties or {})
        self.nodes[node_id] = node
        return node

    def create_edge(
        self,
        source_node_id: UUID,
        target_node_id: UUID,
        edge_type: str,
        properties: EdgeProperties | None = None,
        duplicate_policy: Literal["reject", "merge"] = "reject",
    ) -> GraphEdge:
        if source_node_id not in self.nodes or target_node_id not in self.nodes:
            raise ValueError("Source or target node does not exist.")

        incoming = GraphEdge(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            type=edge_type,
            properties=properties or {},
        )

        for existing in self.edges:
            is_duplicate = (
                existing.source_node_id == incoming.source_node_id
                and existing.target_node_id == incoming.target_node_id
                and existing.type == incoming.type
            )
            if not is_duplicate:
                continue

            if duplicate_policy == "reject":
                raise ValueError(
                    f"Duplicate edge {edge_type} ({source_node_id} -> {target_node_id}) rejected."
                )
            if duplicate_policy == "merge":
                existing.properties.update(incoming.properties)
                return existing
            raise ValueError(f"Unsupported duplicate policy: {duplicate_policy}")

        self.edges.append(incoming)
        return incoming
