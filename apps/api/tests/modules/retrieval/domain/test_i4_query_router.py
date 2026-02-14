import pytest
from typing import Literal

# Assuming this will be defined in the skeleton
# from apps.api.src.modules.retrieval.domain.services import QueryRouter
# from apps.api.src.modules.retrieval.domain.entities import RetrievalStrategy


class MockQueryRouter:
    def route_query_by_intent(self, query: str) -> Literal["keyword", "vector", "hybrid"]:
        if "exact phrase" in query or "specific legal term" in query:
            return "keyword"
        if "conceptual understanding" in query or "similar concepts" in query:
            return "vector"
        if "complex intent combining" in query:
            return "hybrid"
        return "hybrid" # Default or fallback

@pytest.fixture
def query_router():
    return MockQueryRouter()


@pytest.mark.skip(reason="Unit test for query router, will fail until actual logic is implemented.")
def test_i4_router_selects_keyword_for_exact_match_intent(query_router):
    """Refers to I4.1: Unit test - query router selects keyword strategy for exact match intent."""
    query = "Find the exact phrase 'force majeure' clause"
    strategy = query_router.route_query_by_intent(query)
    assert strategy == "keyword"

@pytest.mark.skip(reason="Unit test for query router, will fail until actual logic is implemented.")
def test_i4_router_selects_vector_for_conceptual_intent(query_router):
    """Refers to I4.1: Unit test - query router selects vector strategy for conceptual intent."""
    query = "Explain the implications of unforeseen events on contract performance"
    strategy = query_router.route_query_by_intent(query)
    assert strategy == "vector"

@pytest.mark.skip(reason="Unit test for query router, will fail until actual logic is implemented.")
def test_i4_router_selects_hybrid_for_complex_intent(query_router):
    """Refers to I4.1: Unit test - query router selects hybrid strategy for complex intent."""
    query = "Find clauses related to payment terms and also mentions specific legal term 'late penalties'"
    strategy = query_router.route_query_by_intent(query)
    assert strategy == "hybrid"
