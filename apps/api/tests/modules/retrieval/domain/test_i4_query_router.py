"""
I4 - Query Router Domain Tests
Test Suite ID: TS-I4-ROUTER-001
"""

import pytest

from src.modules.retrieval.domain.entities import QueryIntent
from src.modules.retrieval.domain.services import QueryRouter

@pytest.fixture
def query_router():
    return QueryRouter()


def test_i4_router_selects_keyword_for_exact_match_intent(query_router):
    """Refers to I4.1: Unit test - query router selects keyword strategy for exact match intent."""
    query = "Find the exact phrase 'force majeure' clause"
    strategy = query_router.route_query_by_intent(query)
    assert strategy == QueryIntent.KEYWORD_ONLY

def test_i4_router_selects_vector_for_conceptual_intent(query_router):
    """Refers to I4.1: Unit test - query router selects vector strategy for conceptual intent."""
    query = "Explain the conceptual understanding of unforeseen events on contract performance"
    strategy = query_router.route_query_by_intent(query)
    assert strategy == QueryIntent.VECTOR_ONLY

def test_i4_router_selects_hybrid_for_complex_intent(query_router):
    """Refers to I4.1: Unit test - query router selects hybrid strategy for complex intent."""
    query = "Find clauses related to payment terms and also mentions specific legal term 'late penalties'"
    strategy = query_router.route_query_by_intent(query)
    assert strategy == QueryIntent.HYBRID
