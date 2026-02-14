"""
C2Pro - Retrieval Domain Entities

Defines the canonical data contracts for retrieval results and query intents.

Increment I4: Hybrid RAG Retrieval Correctness
- RetrievalResult: DTO for retrieved evidence (clauses, chunks)
- QueryIntent: Enum for retrieval strategy selection
"""

from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional
from enum import StrEnum


class QueryIntent(StrEnum):
    """
    Enum for different query intents that determine retrieval strategy.

    Refers to I4.1: Query router selects retrieval strategy by intent.

    Using StrEnum (Python 3.11+) allows enum members to be compared
    directly with string literals, satisfying both domain and application
    layer test expectations.

    Values:
        KEYWORD_ONLY: "keyword" - Exact phrase/legal term matching
        VECTOR_ONLY: "vector" - Conceptual/semantic similarity
        HYBRID: "hybrid" - Combined keyword + vector retrieval
    """
    KEYWORD_ONLY = "keyword"
    VECTOR_ONLY = "vector"
    HYBRID = "hybrid"


class RetrievalResult(BaseModel):
    """
    DTO for a retrieved document chunk or clause, representing evidence.

    Refers to I4.2: Top-k includes expected clause and evidence chunk.

    This DTO ensures that retrieved results include:
    - Complete provenance metadata (doc_id, version_id, clause_id)
    - Relevance score for ranking and threshold filtering
    - Extensible metadata for reranking, source tracking, and HITL flags

    Attributes:
        doc_id: ID of the document the evidence comes from
        version_id: ID of the document version
        clause_id: Optional ID of the specific clause if applicable
        text: The retrieved text content (chunk or clause)
        score: Relevance score of the retrieved item (0.0-1.0)
        metadata: Additional metadata (source_type, reranked, requires_reviewer_validation, etc.)
    """

    doc_id: UUID = Field(
        ...,
        description="ID of the document the evidence comes from."
    )

    version_id: UUID = Field(
        ...,
        description="ID of the document version."
    )

    clause_id: Optional[UUID] = Field(
        None,
        description="Optional ID of the specific clause if applicable."
    )

    text: str = Field(
        ...,
        min_length=1,
        description="The retrieved text content (chunk or clause)."
    )

    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance score of the retrieved item (0.0-1.0)."
    )

    metadata: dict = Field(
        default_factory=dict,
        description="Additional metadata about the retrieval source or process."
    )

    model_config = {
        "frozen": False,  # Allow mutation for metadata updates (e.g., HITL flags)
        "str_strip_whitespace": True,
        "validate_assignment": True,
    }
