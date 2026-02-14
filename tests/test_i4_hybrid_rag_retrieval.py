# Path: apps/api/src/documents/tests/integration/test_i4_hybrid_rag_retrieval.py
import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4

# TDD: These imports will fail until the application services, DTOs, and ports are created.
try:
    from src.documents.application.services import HybridRetrievalService
    from src.documents.application.ports import BaseRetriever, Reranker
    from src.documents.application.util import QueryRouter
    from src.documents.application.dtos import RetrievedDoc, Query
except ImportError:
    # Define dummy classes to allow the test file to be parsed before implementation
    HybridRetrievalService = type("HybridRetrievalService", (), {})
    BaseRetriever = type("BaseRetriever", (), {})
    Reranker = type("Reranker", (), {})
    QueryRouter = type("QueryRouter", (), {})
    RetrievedDoc = type("RetrievedDoc", (), {})
    Query = type("Query", (), {})


@pytest.fixture
def mock_keyword_retriever() -> BaseRetriever:
    """A mock for the keyword-based retriever (e.g., BM25)."""
    mock = AsyncMock(spec=BaseRetriever)
    mock.name = "keyword_retriever"
    mock.retrieve.return_value = [
        RetrievedDoc(doc_id=uuid4(), chunk_id=uuid4(), score=0.9, text="Clause 14.a details...")
    ]
    return mock


@pytest.fixture
def mock_vector_retriever() -> BaseRetriever:
    """A mock for the vector-based semantic retriever."""
    mock = AsyncMock(spec=BaseRetriever)
    mock.name = "vector_retriever"
    mock.retrieve.return_value = [
        RetrievedDoc(doc_id=uuid4(), chunk_id=uuid4(), score=0.85, text="Details about payment terms...")
    ]
    return mock


@pytest.fixture
def mock_reranker() -> Reranker:
    """A mock for the reranking component."""
    mock = AsyncMock(spec=Reranker)
    # By default, the mock just returns the docs it was given.
    mock.rerank.side_effect = lambda docs, query: docs
    return mock


@pytest.mark.integration
@pytest.mark.tdd
class TestHybridRagRetrieval:
    """
    Test suite for I4 - Hybrid RAG Retrieval Correctness.
    """

    def test_i4_01_query_router_dispatches_correctly(
        self, mock_keyword_retriever: BaseRetriever, mock_vector_retriever: BaseRetriever
    ):
        """
        [TEST-I4-01] Verifies the QueryRouter dispatches to the correct retriever by intent.
        """
        # Arrange: This test expects a `QueryRouter` utility to exist.
        router = QueryRouter(
            retrievers=[mock_keyword_retriever, mock_vector_retriever],
            routing_rules=[(r"\bclause\b", "keyword_retriever")]
        )

        # Act & Assert for keyword query
        keyword_query = Query(text="Show me Clause 14.a")
        keyword_retriever = router.route(keyword_query)
        assert keyword_retriever.name == "keyword_retriever"

        # Act & Assert for semantic query
        semantic_query = Query(text="What are the payment terms?")
        semantic_retriever = router.route(semantic_query)
        assert semantic_retriever.name == "vector_retriever"

    @pytest.mark.asyncio
    async def test_i4_02_hybrid_retrieval_combines_results(
        self, mock_keyword_retriever: BaseRetriever, mock_vector_retriever: BaseRetriever, mock_reranker: Reranker
    ):
        """
        [TEST-I4-02] Verifies the hybrid service combines keyword and vector results.
        """
        # Arrange: This test expects the `HybridRetrievalService` to exist.
        service = HybridRetrievalService(
            keyword_retriever=mock_keyword_retriever,
            vector_retriever=mock_vector_retriever,
            reranker=mock_reranker
        )
        query = Query(text="Find payment terms in Clause 14.a")

        # Act: This call will fail until the service is implemented.
        results = await service.retrieve(query)

        # Assert
        assert len(results) == 2, "Should combine results from both retrievers."
        mock_keyword_retriever.retrieve.assert_called_once()
        mock_vector_retriever.retrieve.assert_called_once()

    @pytest.mark.asyncio
    async def test_i4_03_reranker_promotes_relevant_doc(
        self, mock_keyword_retriever: BaseRetriever, mock_vector_retriever: BaseRetriever, mock_reranker: Reranker
    ):
        """
        [TEST-I4-03] Verifies the reranker step promotes a relevant but low-ranked doc.
        """
        # Arrange
        service = HybridRetrievalService(
            keyword_retriever=mock_keyword_retriever,
            vector_retriever=mock_vector_retriever,
            reranker=mock_reranker
        )
        # Simulate initial retrieval where the best doc is ranked second
        initial_docs = [RetrievedDoc(score=0.7, text="less relevant"), RetrievedDoc(score=0.6, text="most relevant")]
        mock_keyword_retriever.retrieve.return_value = initial_docs
        mock_vector_retriever.retrieve.return_value = []

        # Configure reranker to promote the "most relevant" doc
        reranked_docs = [RetrievedDoc(score=0.95, text="most relevant"), RetrievedDoc(score=0.65, text="less relevant")]
        mock_reranker.rerank.return_value = reranked_docs

        # Act
        results = await service.retrieve(Query(text="find most relevant"))

        # Assert
        assert len(results) > 0
        assert results[0].text == "most relevant", "Reranker should have promoted the most relevant document."
        mock_reranker.rerank.assert_called_once()

    @pytest.mark.xfail(reason="[TDD] Drives implementation of evidence threshold gate.", strict=True)
    @pytest.mark.asyncio
    async def test_i4_04_evidence_threshold_gate_blocks_low_confidence(self):
        """
        [TEST-I4-04] Verifies the service returns nothing if final scores are too low.
        """
        # Arrange
        service = HybridRetrievalService(
            keyword_retriever=MagicMock(spec=BaseRetriever),
            vector_retriever=MagicMock(spec=BaseRetriever),
            reranker=MagicMock(spec=Reranker),
            evidence_threshold=0.8
        )
        # All retrieved and reranked docs have scores below the threshold
        service.reranker.rerank.return_value = [RetrievedDoc(score=0.7), RetrievedDoc(score=0.6)]

        # Act
        results = await service.retrieve(Query(text="find something"))

        # Assert
        assert len(results) == 0, "Evidence threshold gate should have blocked all low-confidence results."
        # The xfail will be removed once the service correctly implements this final filtering step.
        assert False, "Remove this line once the threshold gate is implemented."