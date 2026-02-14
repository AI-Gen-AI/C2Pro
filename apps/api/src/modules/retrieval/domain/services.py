"""
C2Pro - Retrieval Domain Services

Pure domain logic for query routing and retrieval strategy selection.

Increment I4: Hybrid RAG Retrieval Correctness
- QueryRouter: Deterministic routing based on query intent patterns
"""

import structlog
from src.modules.retrieval.domain.entities import QueryIntent

logger = structlog.get_logger(__name__)


class QueryRouter:
    """
    Domain service for routing queries to optimal retrieval strategies.

    Refers to I4.1: Unit test - query router selects retrieval strategy by intent.

    This service analyzes query text patterns to determine whether:
    - KEYWORD_ONLY: Query seeks exact phrases or specific legal terms
    - VECTOR_ONLY: Query seeks conceptual understanding or similar concepts
    - HYBRID: Query combines both exact matching and semantic understanding

    Pure domain logic (no external dependencies, framework-agnostic).

    Examples:
        >>> router = QueryRouter()
        >>> router.route_query_by_intent("Find exact phrase 'force majeure'")
        QueryIntent.KEYWORD_ONLY

        >>> router.route_query_by_intent("Explain implications of unforeseen events")
        QueryIntent.VECTOR_ONLY

        >>> router.route_query_by_intent("Find payment terms and specific legal term 'penalties'")
        QueryIntent.HYBRID
    """

    # Pattern keywords for strategy detection
    KEYWORD_INDICATORS = [
        "exact phrase",
        "specific legal term",
        "explicitly",
        "verbatim",
        "quoted",
        "literal",
        "find the term",
    ]

    VECTOR_INDICATORS = [
        "conceptual understanding",
        "similar concepts",
        "explain",
        "implications",
        "meaning of",
        "related to",
        "understand",
    ]

    HYBRID_INDICATORS = [
        "and also",
        "combines",
        "both",
        "as well as",
        "together with",
    ]

    def __init__(self):
        """Initialize the query router with pattern matching rules."""
        logger.info("query_router_initialized")

    def route_query_by_intent(self, query: str) -> QueryIntent:
        """
        Determines the optimal retrieval strategy based on query intent.

        Refers to I4.1: Unit test - query router selects retrieval strategy by intent.

        Algorithm:
        1. Check for hybrid indicators first (highest priority)
        2. Check for keyword indicators
        3. Check for vector indicators
        4. Default to HYBRID for safety (ensures broadest coverage)

        Args:
            query: The user's query text

        Returns:
            QueryIntent enum indicating the selected strategy

        Example:
            ```python
            router = QueryRouter()
            intent = router.route_query_by_intent("Find exact 'liquidated damages' clause")
            # Returns: QueryIntent.KEYWORD_ONLY
            ```
        """
        query_lower = query.lower()

        logger.debug(
            "routing_query",
            query_length=len(query),
            query_preview=query[:50],
        )

        # Priority 1: Check for hybrid indicators
        if any(indicator in query_lower for indicator in self.HYBRID_INDICATORS):
            logger.info(
                "query_routed",
                strategy="hybrid",
                reason="hybrid_indicators_detected",
            )
            return QueryIntent.HYBRID

        # Priority 2: Check for keyword indicators (exact matching needed)
        if any(indicator in query_lower for indicator in self.KEYWORD_INDICATORS):
            logger.info(
                "query_routed",
                strategy="keyword",
                reason="keyword_indicators_detected",
            )
            return QueryIntent.KEYWORD_ONLY

        # Priority 3: Check for vector indicators (semantic search needed)
        if any(indicator in query_lower for indicator in self.VECTOR_INDICATORS):
            logger.info(
                "query_routed",
                strategy="vector",
                reason="vector_indicators_detected",
            )
            return QueryIntent.VECTOR_ONLY

        # Default: HYBRID for safety (broadest coverage)
        logger.info(
            "query_routed",
            strategy="hybrid",
            reason="default_fallback",
        )
        return QueryIntent.HYBRID
