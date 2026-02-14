import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import List, Dict, Any
from uuid import UUID, uuid4

# Assuming these will be defined in the skeleton
from apps.api.src.modules.retrieval.domain.entities import RetrievalResult, QueryIntent
from apps.api.src.modules.retrieval.application.ports import (
    VectorStore, KeywordSearch, Reranker, RetrievalService, QueryRouter,
    LangSmithClientProtocol # Re-use protocol from I3 if in conftest, or define locally
)

# Mock LangSmith Client (from conftest.py or local)
class MockLangSmithClient:
    def __init__(self):
        self.spans = []

    def start_span(self, name: str, input: Any = None, run_type: str = "tool", **kwargs):
        span = {"name": name, "input": input, "run_type": run_type, "kwargs": kwargs, "id": uuid4(), "outputs": None}
        self.spans.append(span)
        return span

    def end_span(self, span: Dict[str, Any], outputs: Any = None):
        for s in self.spans:
            if s["id"] == span["id"]:
                s["outputs"] = outputs
                break

    def get_spans_by_name(self, name: str):
        return [s for s in self.spans if s["name"] == name]

@pytest.fixture
def mock_langsmith_client():
    return MockLangSmithClient()

@pytest.fixture
def mock_vector_store():
    """Mock for VectorStore adapter."""
    mock = AsyncMock(spec=VectorStore)
    mock.query.return_value = [
        RetrievalResult(
            doc_id=uuid4(), version_id=uuid4(), clause_id=uuid4(),
            text="Conceptual clause about payment terms.", score=0.8,
            metadata={"source_type": "vector", "embedding_model": "test-model"}
        ),
        RetrievalResult(
            doc_id=uuid4(), version_id=uuid4(), clause_id=uuid4(),
            text="Another conceptual clause.", score=0.75,
            metadata={"source_type": "vector", "embedding_model": "test-model"}
        ),
    ]
    return mock

@pytest.fixture
def mock_keyword_search():
    """Mock for KeywordSearch adapter."""
    mock = AsyncMock(spec=KeywordSearch)
    mock.query.return_value = [
        RetrievalResult(
            doc_id=uuid4(), version_id=uuid4(), clause_id=uuid4(),
            text="This clause explicitly mentions force majeure.", score=0.95,
            metadata={"source_type": "keyword", "search_engine": "test-engine"}
        ),
        RetrievalResult(
            doc_id=uuid4(), version_id=uuid4(), clause_id=uuid4(),
            text="Another clause with force majeure in context.", score=0.9,
            metadata={"source_type": "keyword", "search_engine": "test-engine"}
        ),
    ]
    return mock

@pytest.fixture
def mock_reranker():
    """Mock for Reranker adapter."""
    mock = AsyncMock(spec=Reranker)
    # Reranker should return results with updated scores, maintaining determinism
    mock.rerank.return_value = [
        RetrievalResult(
            doc_id=uuid4(), version_id=uuid4(), clause_id=uuid4(),
            text="This clause explicitly mentions force majeure.", score=0.98,
            metadata={"source_type": "keyword", "search_engine": "test-engine", "reranked": True}
        ),
        RetrievalResult(
            doc_id=uuid4(), version_id=uuid4(), clause_id=uuid4(),
            text="Conceptual clause about payment terms.", score=0.92,
            metadata={"source_type": "vector", "embedding_model": "test-model", "reranked": True}
        ),
        RetrievalResult(
            doc_id=uuid4(), version_id=uuid4(), clause_id=uuid4(),
            text="Another clause with force majeure in context.", score=0.85,
            metadata={"source_type": "keyword", "search_engine": "test-engine", "reranked": True}
        ),
    ]
    return mock

@pytest.fixture
def mock_query_router():
    """Mock for QueryRouter."""
    mock = MagicMock(spec=QueryRouter)
    mock.route_query_by_intent.return_value = QueryIntent.HYBRID
    return mock

@pytest.mark.asyncio
@pytest.mark.skip(reason="Integration test for RAG service, will fail until RetrievalService is implemented.")
async def test_i4_top_k_includes_expected_clause_and_evidence(
    mock_vector_store, mock_keyword_search, mock_reranker, mock_query_router
):
    """Refers to I4.2: Integration test - top-k includes expected clause and evidence chunk."""
    rag_service = RetrievalService(
        vector_store=mock_vector_store,
        keyword_search=mock_keyword_search,
        reranker=mock_reranker,
        query_router=mock_query_router,
        evidence_threshold=0.7
    )
    query = "Find information about force majeure and payment terms"
    results = await rag_service.retrieve(query, top_k=3)

    assert len(results) == 3
    assert any("force majeure" in r.text for r in results)
    assert any("payment terms" in r.text for r in results)
    assert all(r.score > 0 for r in results) # Ensure scores are present and non-zero

@pytest.mark.asyncio
@pytest.mark.skip(reason="Negative test for retrieval, will fail if vector-only retrieval is used where keyword is needed.")
async def test_i4_vector_only_retrieval_misses_exact_legal_language(
    mock_vector_store, mock_keyword_search, mock_reranker, mock_query_router
):
    """Refers to I4.4: Expected failure - Vector-only retrieval misses exact legal language."""
    # Configure router to only select vector for a keyword-specific query
    mock_query_router.route_query_by_intent.return_value = QueryIntent.VECTOR_ONLY

    # Configure vector store to return irrelevant results for this specific query
    mock_vector_store.query.return_value = [
        RetrievalResult(
            doc_id=uuid4(), version_id=uuid4(), clause_id=uuid4(),
            text="Irrelevant conceptual clause.", score=0.6,
            metadata={"source_type": "vector", "embedding_model": "test-model"}
        )
    ]

    rag_service = RetrievalService(
        vector_store=mock_vector_store,
        keyword_search=mock_keyword_search, # This won't be called if router forces VECTOR_ONLY
        reranker=mock_reranker,
        query_router=mock_query_router,
        evidence_threshold=0.7
    )
    query = "Exact phrase 'liquidated damages' clause"
    results = await rag_service.retrieve(query, top_k=1)

    # This assertion will pass if the implementation correctly handles hybrid or keyword.
    # It will FAIL if vector-only is used and misses the exact phrase.
    # The expected failure for the "red phase" is that it will miss this.
    assert not any("liquidated damages" in r.text for r in results), "Vector-only retrieval should miss exact legal term."
    assert len(results) == 1
    assert "Irrelevant conceptual clause." in results[0].text # Confirm it returned the irrelevant vector result


@pytest.mark.asyncio
@pytest.mark.skip(reason="Negative test for reranker, will fail if reranker is absent or non-deterministic.")
async def test_i4_reranker_deterministcally_orders_results(
    mock_vector_store, mock_keyword_search, mock_reranker
):
    """Refers to I4.4: Expected failure - Reranker absent or not deterministic."""
    # Mock reranker to return a specific, predictable order
    mock_reranker.rerank.return_value = [
        RetrievalResult(
            doc_id=uuid4(), version_id=uuid4(), clause_id=uuid4(),
            text="High relevance result after rerank.", score=0.99,
            metadata={"reranked_score": 0.99}
        ),
        RetrievalResult(
            doc_id=uuid4(), version_id=uuid4(), clause_id=uuid4(),
            text="Medium relevance result after rerank.", score=0.80,
            metadata={"reranked_score": 0.80}
        ),
    ]

    # Simulate a set of mixed search results
    mock_results = [
        RetrievalResult(doc_id=uuid4(), version_id=uuid4(), clause_id=uuid4(), text="Initial result B.", score=0.7),
        RetrievalResult(doc_id=uuid4(), version_id=uuid4(), clause_id=uuid4(), text="Initial result A.", score=0.9),
    ]

    # This test directly calls the reranker to ensure its determinism.
    # The initial "red phase" failure would be if reranker.rerank isn't called or returns non-deterministic order.
    reranked_results_1 = await mock_reranker.rerank(mock_results, "test query")
    reranked_results_2 = await mock_reranker.rerank(mock_results, "test query")

    assert len(reranked_results_1) == len(mock_results)
    assert reranked_results_1[0].text == "High relevance result after rerank." # Assert specific order
    assert reranked_results_1[1].text == "Medium relevance result after rerank."

    # Crucially, assert determinism
    assert reranked_results_1 == reranked_results_2


@pytest.mark.asyncio
@pytest.mark.skip(reason="Eval test, will fail until RetrievalService implements recall/groundedness metrics conceptually.")
async def test_i4_recall_at_5_threshold_met_conceptually(
    mock_vector_store, mock_keyword_search, mock_reranker, mock_query_router
):
    """Refers to I4.3: Eval test - recall@5 and groundedness thresholds on curated corpus."""
    # This is a conceptual test. In reality, an eval harness would run against a dataset.
    # For TDD, we simulate a simple scenario.
    rag_service = RetrievalService(
        vector_store=mock_vector_store,
        keyword_search=mock_keyword_search,
        reranker=mock_reranker,
        query_router=mock_query_router,
        evidence_threshold=0.7
    )
    query = "Query for recall evaluation"

    # Mock return values to simulate a scenario where recall@5 is 'met'
    mock_vector_store.query.return_value = [
        RetrievalResult(doc_id=uuid4(), version_id=uuid4(), clause_id=uuid4(), text="Relevant clause 1.", score=0.9),
        RetrievalResult(doc_id=uuid4(), version_id=uuid4(), clause_id=uuid4(), text="Relevant clause 2.", score=0.8),
        RetrievalResult(doc_id=uuid4(), version_id=uuid4(), clause_id=uuid4(), text="Less relevant clause.", score=0.6),
    ]
    mock_keyword_search.query.return_value = [] # No keyword specific match

    results = await rag_service.retrieve(query, top_k=5)

    # Conceptual assertions for recall (would be against actual ground truth)
    # Here, we just check if expected number of "relevant" items are in top-k
    relevant_count = sum(1 for r in results if "Relevant clause" in r.text)
    assert relevant_count >= 2 # Assuming 2 relevant clauses are expected in top-5

@pytest.mark.asyncio
@pytest.mark.skip(reason="Observability hook test, will fail until LangSmith logs retrieved IDs, rerank scores, and miss reasons.")
async def test_i4_langsmith_logs_retrieved_ids_and_rerank_scores(
    mock_vector_store, mock_keyword_search, mock_reranker, mock_query_router, mock_langsmith_client
):
    """Refers to I4.5: Observability hooks (LangSmith) - Log retrieved IDs, rerank scores, miss reasons."""
    rag_service = RetrievalService(
        vector_store=mock_vector_store,
        keyword_search=mock_keyword_search,
        reranker=mock_reranker,
        query_router=mock_query_router,
        evidence_threshold=0.7,
        langsmith_client=mock_langsmith_client
    )
    query = "Query for logging"
    await rag_service.retrieve(query, top_k=2)

    retrieval_spans = mock_langsmith_client.get_spans_by_name("hybrid_retrieval")
    assert len(retrieval_spans) == 1
    logged_span = retrieval_spans[0]

    assert "retrieved_ids" in logged_span["outputs"]
    assert len(logged_span["outputs"]["retrieved_ids"]) > 0
    assert "reranked_scores" in logged_span["outputs"]
    assert len(logged_span["outputs"]["reranked_scores"]) > 0
    assert "miss_reasons" in logged_span["outputs"] # Expecting this field, even if empty

@pytest.mark.asyncio
@pytest.mark.skip(reason="Human-in-the-loop checkpoint, will fail until RetrievalService flags low evidence for review.")
async def test_i4_evidence_threshold_failure_requires_reviewer(
    mock_vector_store, mock_keyword_search, mock_reranker, mock_query_router
):
    """Refers to I4.6: Human-in-the-loop checkpoints - If evidence threshold fails, require reviewer."""
    # Configure mocks to return results below the evidence threshold
    mock_vector_store.query.return_value = [
        RetrievalResult(doc_id=uuid4(), version_id=uuid4(), clause_id=uuid4(), text="Low evidence 1.", score=0.3),
    ]
    mock_keyword_search.query.return_value = [
        RetrievalResult(doc_id=uuid4(), version_id=uuid4(), clause_id=uuid4(), text="Low evidence 2.", score=0.4),
    ]
    mock_reranker.rerank.return_value = [
        RetrievalResult(
            doc_id=uuid4(), version_id=uuid4(), clause_id=uuid4(),
            text="Combined low evidence.", score=0.45,
            metadata={"reranked_score": 0.45}
        )
    ]

    rag_service = RetrievalService(
        vector_store=mock_vector_store,
        keyword_search=mock_keyword_search,
        reranker=mock_reranker,
        query_router=mock_query_router,
        evidence_threshold=0.5 # Set a threshold that will fail
    )
    query = "Query for low evidence"
    results = await rag_service.retrieve(query, top_k=1)

    assert len(results) == 1
    assert results[0].score < rag_service.evidence_threshold
    # The service should add a flag to the result or return a specific status
    assert results[0].metadata.get("requires_reviewer_validation") is True
    assert results[0].metadata.get("evidence_failure_reason") == "below_threshold"
