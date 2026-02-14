"""
I5 - Graph Builder Service (Application)
Test Suite ID: TS-I5-GRAPH-APP-001
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional
from uuid import UUID, uuid4
from unittest.mock import AsyncMock

import pytest

from src.modules.extraction.domain.entities import ExtractedClause

try:
    from src.modules.graph.domain.entities import GraphNode
    from src.modules.graph.application.ports import GraphRepository, GraphBuilderService
except ImportError:
    @dataclass
    class GraphNode:  # type: ignore[override]
        id: UUID
        type: str
        properties: dict[str, Any] = field(default_factory=dict)

    class GraphRepository:  # type: ignore[override]
        async def add_node(self, node: GraphNode) -> UUID: ...
        async def get_node(self, node_id: UUID) -> Optional[GraphNode]: ...
        async def add_edge(self, edge: Any) -> UUID: ...

    class GraphBuilderService:  # type: ignore[override]
        """Fallback intentionally incomplete to keep QA tests RED."""

        def __init__(self, graph_repository: GraphRepository, langsmith_client: Any = None):
            self.graph_repository = graph_repository
            self.langsmith_client = langsmith_client

        async def build_from_extracted_clauses(self, clauses: list[ExtractedClause]) -> list[dict[str, Any]]:
            for clause in clauses:
                clause_node = GraphNode(
                    id=clause.clause_id,
                    type="Clause",
                    properties={"text": clause.text, "type": clause.type},
                )
                await self.graph_repository.add_node(clause_node)
                await self.graph_repository.add_edge(
                    {
                        "source_node_id": clause.clause_id,
                        "target_node_id": clause.document_id,
                        "type": "BELONGS_TO",
                    }
                )
            return []


@pytest.fixture
def mock_graph_repository() -> AsyncMock:
    repo = AsyncMock(spec=GraphRepository)
    repo.add_node.return_value = uuid4()
    repo.add_edge.return_value = uuid4()
    repo.get_node.return_value = None
    return repo


@pytest.fixture
def mock_extracted_clauses() -> list[ExtractedClause]:
    doc_id = uuid4()
    version_id = uuid4()
    chunk_id = uuid4()
    return [
        ExtractedClause(
            clause_id=uuid4(),
            document_id=doc_id,
            version_id=version_id,
            chunk_id=chunk_id,
            text="The Contractor shall deliver goods by 2024-12-31.",
            type="Delivery Obligation",
            modality="Shall",
            due_date=date(2024, 12, 31),
            penalty_linkage="Late delivery penalty applies.",
            confidence=0.98,
            ambiguity_flag=False,
            actors=["Contractor", "Client"],
            metadata={},
        )
    ]


@pytest.mark.asyncio
async def test_i5_graph_build_fails_on_missing_referenced_node(
    mock_graph_repository: AsyncMock,
    mock_extracted_clauses: list[ExtractedClause],
) -> None:
    """Refers to I5.4: Graph build must fail when edge targets missing nodes."""
    mock_graph_repository.get_node.return_value = None
    graph_builder = GraphBuilderService(graph_repository=mock_graph_repository)

    with pytest.raises(ValueError, match="Source or target node not found for edge."):
        await graph_builder.build_from_extracted_clauses(mock_extracted_clauses)


@pytest.mark.asyncio
async def test_i5_graph_build_surfaces_duplicate_edge_rejection(
    mock_graph_repository: AsyncMock,
    mock_extracted_clauses: list[ExtractedClause],
) -> None:
    """Refers to I5.2: Duplicate-edge semantics must be explicit (reject surfaced)."""
    mock_graph_repository.get_node.return_value = GraphNode(id=uuid4(), type="Clause")
    mock_graph_repository.add_edge.side_effect = ValueError("Duplicate edge rejected.")
    graph_builder = GraphBuilderService(graph_repository=mock_graph_repository)

    with pytest.raises(ValueError, match="Duplicate edge rejected."):
        await graph_builder.build_from_extracted_clauses(mock_extracted_clauses)
