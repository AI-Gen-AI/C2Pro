"""Regression tests for P1-04 retrieval scoring and threshold boundaries."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.retrieval.application.ports import (
    KeywordSearch,
    QueryRouter,
    Reranker,
    RetrievalService,
    VectorStore,
)
from src.modules.retrieval.domain.entities import QueryIntent, RetrievalResult


def _result(text: str, score: float) -> RetrievalResult:
    return RetrievalResult(
        doc_id=uuid4(),
        version_id=uuid4(),
        clause_id=uuid4(),
        text=text,
        score=score,
    )


@pytest.mark.asyncio
async def test_p1_04_hybrid_search_combines_sources_and_applies_reranked_scores() -> None:
    """Hybrid routing should combine keyword + vector candidates before reranking."""
    vector_store = AsyncMock(spec=VectorStore)
    keyword_search = AsyncMock(spec=KeywordSearch)
    reranker = AsyncMock(spec=Reranker)
    query_router = MagicMock(spec=QueryRouter)

    keyword_candidate = _result(text="keyword hit", score=0.40)
    vector_candidate = _result(text="vector hit", score=0.60)

    query_router.route_query_by_intent.return_value = QueryIntent.HYBRID
    keyword_search.query.return_value = [keyword_candidate]
    vector_store.query.return_value = [vector_candidate]

    reranked_keyword = keyword_candidate.model_copy(update={"score": 0.93})
    reranked_vector = vector_candidate.model_copy(update={"score": 0.89})
    reranker.rerank.return_value = [reranked_keyword, reranked_vector]

    service = RetrievalService(
        vector_store=vector_store,
        keyword_search=keyword_search,
        reranker=reranker,
        query_router=query_router,
        evidence_threshold=0.80,
    )

    results = await service.retrieve("find both exact and semantic match", top_k=5)

    keyword_search.query.assert_awaited_once()
    vector_store.query.assert_awaited_once()
    reranker.rerank.assert_awaited_once()

    assert [result.text for result in results] == ["keyword hit", "vector hit"]
    assert [result.score for result in results] == [0.93, 0.89]


@pytest.mark.asyncio
async def test_p1_04_empty_hybrid_results_returns_empty_list() -> None:
    """Empty results from both retrieval channels should return an empty list."""
    vector_store = AsyncMock(spec=VectorStore)
    keyword_search = AsyncMock(spec=KeywordSearch)
    reranker = AsyncMock(spec=Reranker)
    query_router = MagicMock(spec=QueryRouter)

    query_router.route_query_by_intent.return_value = QueryIntent.HYBRID
    keyword_search.query.return_value = []
    vector_store.query.return_value = []
    reranker.rerank.return_value = []

    service = RetrievalService(
        vector_store=vector_store,
        keyword_search=keyword_search,
        reranker=reranker,
        query_router=query_router,
        evidence_threshold=0.50,
    )

    results = await service.retrieve("no matches expected", top_k=3)

    assert results == []


@pytest.mark.asyncio
async def test_p1_04_threshold_boundary_score_equal_to_threshold_is_accepted() -> None:
    """A result exactly at threshold should be accepted without reviewer flags."""
    vector_store = AsyncMock(spec=VectorStore)
    keyword_search = AsyncMock(spec=KeywordSearch)
    reranker = AsyncMock(spec=Reranker)
    query_router = MagicMock(spec=QueryRouter)

    query_router.route_query_by_intent.return_value = QueryIntent.KEYWORD_ONLY

    exact_boundary = _result(text="exact boundary", score=0.70)
    keyword_search.query.return_value = [exact_boundary]
    reranker.rerank.return_value = [exact_boundary]

    service = RetrievalService(
        vector_store=vector_store,
        keyword_search=keyword_search,
        reranker=reranker,
        query_router=query_router,
        evidence_threshold=0.70,
    )

    results = await service.retrieve("exact phrase", top_k=1)

    assert len(results) == 1
    assert results[0].score == 0.70
    assert "requires_reviewer_validation" not in results[0].metadata


@pytest.mark.asyncio
async def test_p1_04_threshold_boundary_score_below_threshold_requires_review() -> None:
    """A result marginally below threshold should be flagged for reviewer validation."""
    vector_store = AsyncMock(spec=VectorStore)
    keyword_search = AsyncMock(spec=KeywordSearch)
    reranker = AsyncMock(spec=Reranker)
    query_router = MagicMock(spec=QueryRouter)

    query_router.route_query_by_intent.return_value = QueryIntent.VECTOR_ONLY

    below_boundary = _result(text="below boundary", score=0.699)
    vector_store.query.return_value = [below_boundary]
    reranker.rerank.return_value = [below_boundary]

    service = RetrievalService(
        vector_store=vector_store,
        keyword_search=keyword_search,
        reranker=reranker,
        query_router=query_router,
        evidence_threshold=0.70,
    )

    results = await service.retrieve("semantic", top_k=1)

    assert len(results) == 1
    assert results[0].metadata["requires_reviewer_validation"] is True
    assert results[0].metadata["evidence_failure_reason"] == "below_threshold"
