"""
Graph domain entities.

Refers to Suite ID: TS-UD-ANA-GRP-001.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class GraphNode:
    """Refers to Suite ID: TS-UD-ANA-GRP-001."""

    node_id: UUID
    label: str
    properties: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.node_id is None:
            raise ValueError("node_id is required")
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("label is required")
        if self.properties is None:
            raise ValueError("properties is required")
