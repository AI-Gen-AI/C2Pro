"""
I5 Graph Domain Entities
Test Suite ID: TS-I5-GRAPH-DOM-001
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

NodeProperties = dict[str, Any]
EdgeProperties = dict[str, Any]


class GraphNode(BaseModel):
    """Represents a node in the project knowledge graph."""

    id: UUID = Field(..., description="Unique identifier for the node.")
    type: str = Field(..., min_length=1, description="Type of node (Clause, Obligation, etc.).")
    properties: NodeProperties = Field(default_factory=dict, description="Node metadata properties.")


class GraphEdge(BaseModel):
    """Represents a directed relationship between two graph nodes."""

    source_node_id: UUID = Field(..., description="Source node ID.")
    target_node_id: UUID = Field(..., description="Target node ID.")
    type: str = Field(..., min_length=1, description="Relationship type.")
    properties: EdgeProperties = Field(default_factory=dict, description="Edge metadata properties.")
