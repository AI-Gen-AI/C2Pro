# Path: apps/api/src/documents/tests/integration/test_i5_graph_schema_and_integrity.py
import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4

# TDD: These imports will fail until the application services, DTOs, and ports are created.
try:
    from src.documents.application.services import GraphBuilderService
    from src.documents.application.ports import GraphRepository, DuplicatePolicy
    from src.documents.application.dtos import Node, Edge, NormalizedClause
    from src.documents.application.errors import (
        ReferentialIntegrityError,
        DuplicateEdgeError,
        NodeNotFoundError,
    )
except ImportError:
    # Define dummy classes to allow the test file to be parsed before implementation
    GraphBuilderService = type("GraphBuilderService", (), {})
    GraphRepository = type("GraphRepository", (), {})
    DuplicatePolicy = type("DuplicatePolicy", (), {})
    Node = type("Node", (), {})
    Edge = type("Edge", (), {})
    NormalizedClause = type("NormalizedClause", (), {})
    ReferentialIntegrityError = type("ReferentialIntegrityError", (Exception,), {})
    DuplicateEdgeError = type("DuplicateEdgeError", (Exception,), {})
    NodeNotFoundError = type("NodeNotFoundError", (Exception,), {})


@pytest.fixture
def mock_graph_repo() -> GraphRepository:
    """A mock for the graph database repository port."""
    mock = AsyncMock(spec=GraphRepository)
    mock.create_node.return_value = True
    mock.create_edge.return_value = True
    return mock


@pytest.fixture
def graph_builder(mock_graph_repo: GraphRepository) -> GraphBuilderService:
    """
    TDD: This fixture expects a `GraphBuilderService` that uses a repository
    to construct the graph. The service itself does not exist yet.
    """
    return GraphBuilderService(
        repository=mock_graph_repo, duplicate_policy=DuplicatePolicy.REJECT
    )


@pytest.mark.integration
@pytest.mark.tdd
class TestGraphSchemaAndIntegrity:
    """
    Test suite for I5 - Graph Schema + Relationship Integrity.
    """

    @pytest.mark.asyncio
    async def test_i5_01_builder_creates_valid_nodes_and_edges(
        self, graph_builder: GraphBuilderService, mock_graph_repo: GraphRepository
    ):
        """
        [TEST-I5-01] Verifies the builder creates schema-compliant nodes and edges.
        """
        # Arrange
        clause_node = Node(id=uuid4(), type="Clause", properties={"text": "Clause 1"})
        obligation_node = Node(
            id=uuid4(), type="Obligation", properties={"modality": "MUST"}
        )
        edge = Edge(
            source_id=clause_node.id,
            target_id=obligation_node.id,
            type="CONTAINS_OBLIGATION",
        )

        # Act: These calls will fail until the service and its methods are implemented.
        await graph_builder.add_node(clause_node)
        await graph_builder.add_node(obligation_node)
        await graph_builder.add_edge(edge)

        # Assert
        assert mock_graph_repo.create_node.call_count == 2
        mock_graph_repo.create_edge.assert_called_once_with(edge)

    @pytest.mark.asyncio
    async def test_i5_02_builder_handles_duplicate_edge_creation(
        self, graph_builder: GraphBuilderService, mock_graph_repo: GraphRepository
    ):
        """
        [TEST-I5-02] Verifies the builder handles duplicate edges based on policy.
        """
        # Arrange
        edge = Edge(source_id=uuid4(), target_id=uuid4(), type="LINKS_TO")
        # Simulate the repository finding a duplicate on the second attempt.
        mock_graph_repo.create_edge.side_effect = [True, DuplicateEdgeError()]

        # Act
        await graph_builder.add_edge(edge)  # First call should succeed
        await graph_builder.add_edge(edge)  # Second call should be gracefully handled

        # Assert
        assert (
            mock_graph_repo.create_edge.call_count == 2
        ), "Should attempt to create edge twice"
        # The service should not propagate the DuplicateEdgeError

    @pytest.mark.asyncio
    async def test_i5_03_builder_raises_on_broken_referential_integrity(
        self, graph_builder: GraphBuilderService, mock_graph_repo: GraphRepository
    ):
        """
        [TEST-I5-03] Verifies an error is raised for edges pointing to non-existent nodes.
        """
        # Arrange
        edge_to_nonexistent_node = Edge(
            source_id=uuid4(), target_id=uuid4(), type="LINKS_TO"
        )
        mock_graph_repo.create_edge.side_effect = NodeNotFoundError(
            f"Node with ID {edge_to_nonexistent_node.target_id} not found."
        )

        # Act & Assert
        with pytest.raises(ReferentialIntegrityError):
            await graph_builder.add_edge(edge_to_nonexistent_node)

    @pytest.mark.xfail(reason="[TDD] Drives end-to-end graph construction logic.", strict=True)
    @pytest.mark.asyncio
    async def test_i5_04_full_construction_produces_expected_graph_shape(self):
        """
        [TEST-I5-04] Verifies the full construction process produces a valid graph.
        """
        # Arrange
        # This test requires a higher-level orchestration service that doesn't exist yet.
        from src.documents.application.services import GraphConstructionService

        mock_repo = MagicMock(spec=GraphRepository)
        construction_service = GraphConstructionService(repository=mock_repo)
        clauses = [NormalizedClause(type="PAYMENT"), NormalizedClause(type="DELIVERY")]

        # Act
        await construction_service.build_from_clauses(clauses)

        # Assert
        # The implementation should create nodes for clauses and their types, and link them.
        assert mock_repo.create_node.call_count == 4  # 2 clause nodes + 2 obligation nodes
        assert mock_repo.create_edge.call_count == 2  # 2 edges linking clauses to obligations
        assert False, "Remove this line once graph construction service is implemented."