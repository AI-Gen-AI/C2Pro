"""
C2Pro - Retrieval Application Ports

Defines abstract interfaces (ports) for external dependencies.
Following Hexagonal Architecture, these interfaces are implemented by adapters.

Increment I4: Hybrid RAG Retrieval Correctness
- VectorStore: Abstract interface for vector database queries
- KeywordSearch: Abstract interface for keyword-based search
- Reranker: Abstract interface for result reranking
- RetrievalService: Application service orchestrating hybrid RAG retrieval
"""

import structlog
from abc import ABC, abstractmethod
from typing import Optional, Protocol, Any

from src.modules.retrieval.domain.entities import RetrievalResult, QueryIntent
from src.modules.retrieval.domain.services import QueryRouter

logger = structlog.get_logger(__name__)


class LangSmithClientProtocol(Protocol):
    """Protocol for LangSmith client interface (for observability)."""

    def start_span(
        self, name: str, input: Any = None, run_type: str = "tool", **kwargs
    ) -> Any:
        """Start a new span for tracing."""
        ...

    def end_span(self, span: dict[str, Any], outputs: Any = None) -> None:
        """End a span with outputs."""
        ...


class VectorStore(ABC):
    """
    Abstract Base Class for vector database interactions.

    Refers to I4.2: Integration test - top-k includes expected clause.

    This port defines the contract for vector-based retrieval,
    enabling the system to use different vector stores (pgvector, Pinecone, etc.)
    transparently.

    The adapter pattern allows for:
    - Database-agnostic business logic
    - Easy testing with mock implementations
    - Future database additions without changing core logic
    """

    @abstractmethod
    async def query(
        self, embedding_vector: list[float], top_k: int
    ) -> list[RetrievalResult]:
        """
        Queries the vector store with an embedding vector.

        Args:
            embedding_vector: Dense embedding vector (typically 768 or 1536 dimensions)
            top_k: Maximum number of results to return

        Returns:
            List of RetrievalResult ordered by similarity score (descending)
        """
        raise NotImplementedError("VectorStore adapters must implement query()")


class KeywordSearch(ABC):
    """
    Abstract Base Class for keyword-based search (e.g., Elasticsearch, PostgreSQL FTS).

    Refers to I4.4: Expected failure - Vector-only retrieval misses exact legal language.

    This port ensures exact phrase matching and legal term precision,
    which is critical for contract analysis where specific language matters.
    """

    @abstractmethod
    async def query(self, query_text: str, top_k: int) -> list[RetrievalResult]:
        """
        Queries the keyword search engine with a text query.

        Args:
            query_text: Raw query text for keyword matching
            top_k: Maximum number of results to return

        Returns:
            List of RetrievalResult ordered by relevance score (descending)
        """
        raise NotImplementedError("KeywordSearch adapters must implement query()")


class Reranker(ABC):
    """
    Abstract Base Class for reranking retrieved results.

    Refers to I4.4: Reranker absent or not deterministic.

    Reranking improves retrieval quality by:
    - Combining signals from multiple retrieval strategies
    - Applying cross-encoder models for query-document relevance
    - Ensuring deterministic ordering for reproducibility
    """

    @abstractmethod
    async def rerank(
        self, results: list[RetrievalResult], query: str
    ) -> list[RetrievalResult]:
        """
        Reranks a list of retrieval results based on the original query.

        Args:
            results: Initial retrieval results to rerank
            query: Original query text for relevance scoring

        Returns:
            Reranked list of RetrievalResult ordered by updated scores (descending)

        Note:
            Must be deterministic - same inputs produce same output order
        """
        raise NotImplementedError("Reranker adapters must implement rerank()")


class RetrievalService:
    """
    Application service for orchestrating hybrid RAG retrieval.

    Refers to I4.2: Top-k includes expected clause and evidence chunk.
    Refers to I4.4: Expected failure - Vector-only retrieval misses exact legal language.
    Refers to I4.5: Observability hooks (LangSmith) - Log retrieved IDs, rerank scores, miss reasons.
    Refers to I4.6: Human-in-the-loop checkpoints - Evidence threshold gating.

    This service:
    - Routes queries to appropriate retrieval strategies (keyword/vector/hybrid)
    - Orchestrates multi-source retrieval
    - Applies reranking for quality improvement
    - Enforces evidence threshold gating
    - Flags low-evidence results for human review
    - Integrates with LangSmith for full observability

    Args:
        vector_store: Vector database adapter
        keyword_search: Keyword search adapter
        reranker: Reranking adapter
        query_router: Domain service for strategy selection
        evidence_threshold: Minimum score for automatic acceptance (0.0-1.0)
        langsmith_client: Optional LangSmith client for observability
    """

    def __init__(
        self,
        vector_store: VectorStore,
        keyword_search: KeywordSearch,
        reranker: Reranker,
        query_router: QueryRouter,
        evidence_threshold: float,
        langsmith_client: Optional[LangSmithClientProtocol] = None,
    ):
        """
        Initialize the retrieval service.

        Args:
            vector_store: Vector database adapter
            keyword_search: Keyword search adapter
            reranker: Reranking adapter
            query_router: Domain service for strategy selection
            evidence_threshold: Minimum score for automatic acceptance
            langsmith_client: Optional LangSmith client for observability
        """
        self.vector_store = vector_store
        self.keyword_search = keyword_search
        self.reranker = reranker
        self.query_router = query_router
        self.evidence_threshold = evidence_threshold
        self.langsmith_client = langsmith_client

        logger.info(
            "retrieval_service_initialized",
            evidence_threshold=evidence_threshold,
        )

    async def retrieve(
        self, query: str, top_k: int = 5
    ) -> list[RetrievalResult]:
        """
        Performs hybrid retrieval based on query intent, reranks, and applies evidence threshold.

        Refers to I4.2: Integration test - top-k includes expected clause.
        Refers to I4.5: Observability hooks - Log retrieved IDs, rerank scores, miss reasons.
        Refers to I4.6: Human-in-the-loop - Flag low-evidence results for review.

        Workflow:
        1. Start LangSmith span for observability
        2. Route query to determine strategy (keyword/vector/hybrid)
        3. Execute retrieval based on strategy
        4. Rerank combined results
        5. Apply evidence threshold gating
        6. Flag low-evidence results for human review
        7. End LangSmith span with outputs

        Args:
            query: User's query text
            top_k: Maximum number of results to return

        Returns:
            List of RetrievalResult ordered by reranked relevance (descending)

        Example:
            ```python
            service = RetrievalService(
                vector_store=PgVectorAdapter(),
                keyword_search=PostgresFTSAdapter(),
                reranker=CrossEncoderReranker(),
                query_router=QueryRouter(),
                evidence_threshold=0.7
            )
            results = await service.retrieve("Find force majeure clause", top_k=5)
            for result in results:
                if result.metadata.get("requires_reviewer_validation"):
                    route_to_review_queue(result)
            ```
        """
        logger.info(
            "retrieval_started",
            query_length=len(query),
            top_k=top_k,
        )

        # Step 1: Start LangSmith span for observability
        # Refers to I4.5: Observability hooks
        span = None
        if self.langsmith_client:
            span = self.langsmith_client.start_span(
                name="hybrid_retrieval",
                input={"query": query, "top_k": top_k},
                run_type="chain",
            )

        # Step 2: Route query to determine strategy
        strategy = self.query_router.route_query_by_intent(query)

        logger.info(
            "query_routed",
            strategy=strategy.value,
        )

        # Step 3: Execute retrieval based on strategy
        retrieved_results: list[RetrievalResult] = []
        retrieved_ids: list[str] = []
        miss_reasons: list[str] = []

        # Keyword retrieval (for KEYWORD_ONLY or HYBRID)
        if strategy in (QueryIntent.KEYWORD_ONLY, QueryIntent.HYBRID):
            logger.debug("executing_keyword_search")
            keyword_results = await self.keyword_search.query(query, top_k)
            retrieved_results.extend(keyword_results)
            retrieved_ids.extend(
                [str(r.clause_id) for r in keyword_results if r.clause_id]
            )
            logger.debug(
                "keyword_search_complete",
                result_count=len(keyword_results),
            )

        # Vector retrieval (for VECTOR_ONLY or HYBRID)
        if strategy in (QueryIntent.VECTOR_ONLY, QueryIntent.HYBRID):
            logger.debug("executing_vector_search")
            # In production, generate actual embedding from query
            # For now, use placeholder (will be replaced by adapter)
            mock_embedding = [0.1] * 1536
            vector_results = await self.vector_store.query(mock_embedding, top_k)
            retrieved_results.extend(vector_results)
            retrieved_ids.extend(
                [str(r.clause_id) for r in vector_results if r.clause_id]
            )
            logger.debug(
                "vector_search_complete",
                result_count=len(vector_results),
            )

        # Step 4: Rerank combined results
        logger.debug(
            "reranking_results",
            initial_count=len(retrieved_results),
        )
        reranked_results = await self.reranker.rerank(retrieved_results, query)
        reranked_results = self._validate_reranked_results(
            original_results=retrieved_results,
            reranked_results=reranked_results,
        )
        reranked_scores = [
            {
                "clause_id": str(r.clause_id) if r.clause_id else None,
                "score": r.score,
            }
            for r in reranked_results
        ]
        logger.info(
            "reranking_complete",
            reranked_count=len(reranked_results),
        )

        # Step 5 & 6: Apply evidence threshold gate and flag low-evidence results
        # Refers to I4.6: Human-in-the-loop checkpoints
        final_results = []
        for result in reranked_results[:top_k]:  # Limit to top_k after reranking
            if result.score >= self.evidence_threshold:
                # High-evidence result - automatic acceptance
                final_results.append(result)
                logger.debug(
                    "result_accepted",
                    clause_id=str(result.clause_id) if result.clause_id else None,
                    score=result.score,
                )
            else:
                # Low-evidence result - flag for human review
                result.metadata["requires_reviewer_validation"] = True
                result.metadata["evidence_failure_reason"] = "below_threshold"
                final_results.append(result)
                miss_reasons.append(
                    f"Result {result.clause_id} below evidence threshold (score: {result.score:.2f})"
                )
                logger.warning(
                    "result_flagged_for_review",
                    clause_id=str(result.clause_id) if result.clause_id else None,
                    score=result.score,
                    threshold=self.evidence_threshold,
                )

        logger.info(
            "retrieval_complete",
            total_results=len(final_results),
            flagged_for_review=sum(
                1
                for r in final_results
                if r.metadata.get("requires_reviewer_validation")
            ),
        )

        # Step 7: End LangSmith span with outputs
        if self.langsmith_client and span:
            self.langsmith_client.end_span(
                span,
                outputs={
                    "retrieved_ids": retrieved_ids,
                    "reranked_scores": reranked_scores,
                    "miss_reasons": miss_reasons,
                    "final_result_count": len(final_results),
                },
            )

        return final_results

    def _result_identity(self, result: RetrievalResult) -> str:
        """Build a stable identity key for retrieval/rerank integrity checks."""
        if result.clause_id:
            return f"clause:{result.clause_id}"
        return f"doc:{result.doc_id}|version:{result.version_id}|text:{result.text}"

    def _validate_reranked_results(
        self,
        original_results: list[RetrievalResult],
        reranked_results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """
        Ensure reranker output only contains items from original retrieval results.

        Rerankers should reorder candidates, not introduce synthetic/unseen items.
        If invalid output is detected, fall back to original retrieval ordering.
        """
        original_ids = {self._result_identity(r) for r in original_results}
        filtered: list[RetrievalResult] = [
            r for r in reranked_results if self._result_identity(r) in original_ids
        ]

        if not filtered and original_results:
            logger.warning(
                "reranker_output_invalid_fallback_original",
                original_count=len(original_results),
                reranked_count=len(reranked_results),
            )
            return original_results

        return filtered
