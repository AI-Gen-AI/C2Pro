"""
Embedding Repository Port for Coherence Engine v0.3 — Phase 6

Defines the contract for embedding-based similarity detection in cross-document
analysis. This port follows hexagonal architecture, allowing the coherence engine
to work with different vector stores (pgvector, Pinecone, etc.) transparently.

The primary use case is detecting semantically similar clauses across documents
(e.g., budget items that relate to schedule milestones) for cross-clause coherence
analysis without LLM cost.

Location: apps/api/src/coherence/ports/embedding_repository.py
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from src.core.json_types import JsonDict

# =============================================================================
# DTOs (Data Transfer Objects)
# =============================================================================


@dataclass(frozen=True)
class EmbeddingRecord:
    """
    A stored clause with its embedding vector.

    Represents a clause that has been embedded and stored in the vector database.
    Used for similarity queries and cross-document analysis.

    Attributes:
        clause_id: Unique identifier for the clause
        project_id: Project this clause belongs to
        document_id: Source document identifier
        document_type: Type of source document (contract, budget, schedule, bom)
        text: Original clause text (truncated for large clauses)
        embedding: Dense vector representation (1536 dims for OpenAI ada-002/small)
        category: Inferred clause category (BUDGET, TIME, LEGAL, SCOPE, etc.)
        metadata: Additional structured data from the clause
        created_at: When the embedding was created
    """

    clause_id: str
    project_id: UUID
    document_id: UUID | None = None
    document_type: Literal["contract", "budget", "schedule", "bom", "other"] = "other"
    text: str = ""
    embedding: list[float] = field(default_factory=list)
    category: str = "SCOPE"
    metadata: JsonDict = field(default_factory=dict)
    created_at: datetime | None = None

    def has_embedding(self) -> bool:
        """Check if embedding has been computed."""
        return len(self.embedding) > 0


@dataclass(frozen=True)
class EmbeddingMatch:
    """
    A similarity match between two clauses.

    Represents a pair of clauses that are semantically similar based on
    cosine similarity of their embeddings. Used to identify cross-document
    relationships for coherence analysis.

    Attributes:
        source_clause_id: The clause we're finding matches for
        target_clause_id: The similar clause found
        target_project_id: Project of the target clause
        target_document_id: Document of the target clause
        target_document_type: Document type of the target
        target_text: Text of the matched clause (for context)
        target_category: Category of the matched clause
        similarity_score: Cosine similarity (0.0-1.0, higher = more similar)
        match_reason: Why these clauses were matched (e.g., "embedding_similarity")
    """

    source_clause_id: str
    target_clause_id: str
    target_project_id: UUID
    target_document_id: UUID | None = None
    target_document_type: str = "other"
    target_text: str = ""
    target_category: str = "SCOPE"
    similarity_score: float = 0.0
    match_reason: str = "embedding_similarity"

    def is_high_similarity(self, threshold: float = 0.85) -> bool:
        """Check if this match exceeds the similarity threshold."""
        return self.similarity_score >= threshold


@dataclass(frozen=True)
class EmbeddingSearchResult:
    """
    Result of a batch embedding similarity search.

    Contains all matches found for a query clause, along with metadata
    about the search operation.

    Attributes:
        query_clause_id: The clause we searched for
        matches: List of similar clauses found
        search_time_ms: Time taken for the search in milliseconds
        total_candidates: Total number of candidates considered
    """

    query_clause_id: str
    matches: list[EmbeddingMatch] = field(default_factory=list)
    search_time_ms: float = 0.0
    total_candidates: int = 0

    @property
    def match_count(self) -> int:
        """Number of matches found."""
        return len(self.matches)

    def top_match(self) -> EmbeddingMatch | None:
        """Get the highest similarity match."""
        if not self.matches:
            return None
        return max(self.matches, key=lambda m: m.similarity_score)


# =============================================================================
# PORT INTERFACE
# =============================================================================


class IEmbeddingRepository(ABC):
    """
    Repository interface for embedding-based clause similarity detection.

    This port defines the contract for:
    1. Storing clause embeddings in a vector database
    2. Finding similar clauses via cosine similarity
    3. Batch operations for efficient cross-document analysis

    Implementations can use pgvector, Pinecone, Milvus, or other vector stores.

    Example usage:
        ```python
        repo = PgvectorEmbeddingRepository(db_session)

        # Store embeddings for clauses
        await repo.store_embedding(clause_id="BUD-001", project_id=proj_id,
                                   embedding=embedding_vector, category="BUDGET")

        # Find similar clauses
        matches = await repo.find_similar(
            embedding=query_embedding,
            project_id=proj_id,
            top_k=10,
            similarity_threshold=0.85,
        )
        ```
    """

    @abstractmethod
    async def store_embedding(
        self,
        *,
        clause_id: str,
        project_id: UUID,
        embedding: list[float],
        document_id: UUID | None = None,
        document_type: str = "other",
        text: str = "",
        category: str = "SCOPE",
        metadata: JsonDict | None = None,
    ) -> EmbeddingRecord:
        """
        Store an embedding for a clause.

        Args:
            clause_id: Unique identifier for the clause
            project_id: Project this clause belongs to
            embedding: Dense embedding vector (e.g., 1536 dims)
            document_id: Optional source document identifier
            document_type: Type of source document
            text: Original clause text (will be truncated if > 1000 chars)
            category: Clause category (BUDGET, TIME, LEGAL, etc.)
            metadata: Additional structured data

        Returns:
            EmbeddingRecord with the stored embedding

        Raises:
            ValueError: If embedding dimension is invalid
        """
        ...

    @abstractmethod
    async def store_embeddings_batch(
        self,
        records: list[EmbeddingRecord],
    ) -> int:
        """
        Store multiple embeddings in a single batch operation.

        More efficient than calling store_embedding() multiple times.

        Args:
            records: List of EmbeddingRecord objects to store

        Returns:
            Number of records successfully stored
        """
        ...

    @abstractmethod
    async def find_similar(
        self,
        *,
        embedding: list[float],
        project_id: UUID,
        top_k: int = 10,
        similarity_threshold: float = 0.85,
        exclude_clause_ids: list[str] | None = None,
        filter_categories: list[str] | None = None,
        filter_document_types: list[str] | None = None,
    ) -> list[EmbeddingMatch]:
        """
        Find clauses similar to the given embedding.

        Uses cosine similarity: similarity = 1 - (embedding <=> target)

        Args:
            embedding: Query embedding vector
            project_id: Project to search within
            top_k: Maximum number of matches to return
            similarity_threshold: Minimum similarity score (0.0-1.0)
            exclude_clause_ids: Clause IDs to exclude from results
            filter_categories: Only return matches from these categories
            filter_document_types: Only return matches from these document types

        Returns:
            List of EmbeddingMatch objects, sorted by similarity (descending)
        """
        ...

    @abstractmethod
    async def find_cross_document_pairs(
        self,
        *,
        project_id: UUID,
        similarity_threshold: float = 0.85,
        max_pairs: int = 20,
        categories_to_compare: list[tuple[str, str]] | None = None,
    ) -> list[EmbeddingMatch]:
        """
        Find similar clauses across different document types.

        This is the primary method for cross-document coherence analysis.
        It finds clauses from different documents that are semantically
        related and may need coherence checking.

        For example, finds budget items related to schedule milestones,
        or contract clauses that relate to BOM specifications.

        Args:
            project_id: Project to analyze
            similarity_threshold: Minimum similarity for a match
            max_pairs: Maximum number of pairs to return
            categories_to_compare: Specific category pairs to compare,
                e.g., [("BUDGET", "TIME"), ("SCOPE", "TECHNICAL")]

        Returns:
            List of cross-document EmbeddingMatch pairs
        """
        ...

    @abstractmethod
    async def get_embedding(
        self,
        clause_id: str,
        project_id: UUID,
    ) -> EmbeddingRecord | None:
        """
        Get the stored embedding for a specific clause.

        Args:
            clause_id: The clause identifier
            project_id: Project the clause belongs to

        Returns:
            EmbeddingRecord or None if not found
        """
        ...

    @abstractmethod
    async def load_embeddings_batch(
        self,
        clause_ids: list[str],
        project_id: UUID,
    ) -> dict[str, list[float]]:
        """Batch-load embedding vectors for a set of clauses in one query.

        Returns a ``clause_id -> vector`` mapping; clauses without a
        stored embedding are omitted. Adapters must perform tenant
        ownership verification for ``project_id``.
        """
        ...

    @abstractmethod
    async def delete_project_embeddings(
        self,
        project_id: UUID,
    ) -> int:
        """
        Delete all embeddings for a project.

        Used when a project is deleted or embeddings need to be regenerated.

        Args:
            project_id: Project whose embeddings to delete

        Returns:
            Number of embeddings deleted
        """
        ...

    @abstractmethod
    async def count_embeddings(
        self,
        project_id: UUID,
    ) -> int:
        """
        Count the number of stored embeddings for a project.

        Args:
            project_id: Project to count embeddings for

        Returns:
            Number of stored embeddings
        """
        ...


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "EmbeddingRecord",
    "EmbeddingMatch",
    "EmbeddingSearchResult",
    "IEmbeddingRepository",
]
