"""
I5 Graph Application Ports and Builder Service
Test Suite ID: TS-I5-GRAPH-APP-001
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Protocol
from uuid import UUID

from src.modules.extraction.domain.entities import ExtractedClause
from src.modules.graph.domain.entities import GraphEdge, GraphNode


class LangSmithClientProtocol(Protocol):
    def start_span(self, name: str, input: Any = None, run_type: str = "tool", **kwargs) -> Any: ...
    def end_span(self, span: dict[str, Any], outputs: Any = None) -> None: ...


class GraphRepository(ABC):
    """Persistence port for graph nodes and edges."""

    @abstractmethod
    async def add_node(self, node: GraphNode) -> UUID:
        raise NotImplementedError

    @abstractmethod
    async def get_node(self, node_id: UUID) -> Optional[GraphNode]:
        raise NotImplementedError

    @abstractmethod
    async def add_edge(self, edge: GraphEdge) -> UUID:
        raise NotImplementedError


class GraphBuilderService:
    """Builds graph structure from extraction outputs with referential checks."""

    def __init__(
        self,
        graph_repository: GraphRepository,
        langsmith_client: Optional[LangSmithClientProtocol] = None,
    ) -> None:
        self.graph_repository = graph_repository
        self.langsmith_client = langsmith_client

    async def build_from_extracted_clauses(
        self,
        clauses: list[ExtractedClause],
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []

        for clause in clauses:
            clause_node = GraphNode(
                id=clause.clause_id,
                type="Clause",
                properties={"text": clause.text, "type": clause.type},
            )
            clause_node_id = await self.graph_repository.add_node(clause_node)

            target_node = await self.graph_repository.get_node(clause.document_id)
            if target_node is None:
                raise ValueError("Source or target node not found for edge.")

            edge = GraphEdge(
                source_node_id=clause_node_id,
                target_node_id=clause.document_id,
                type="BELONGS_TO",
            )
            await self.graph_repository.add_edge(edge)

        return issues
