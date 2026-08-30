"""P0b acceptance-harness guarantees.

TS-UT-P0B-HARNESS-001.

The acceptance journey has to persist REAL RAG chunks -- that is the seam that
failed in production -- so only the embedding provider's network call is
replaced. These tests pin that the substitute behaves like an embedding and,
more importantly, that it can never be switched on in production.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Deterministic embeddings: harness support that must never reach production.
# ---------------------------------------------------------------------------


def test_deterministic_embedding_is_stable_distinct_and_correctly_shaped() -> None:
    from src.documents.adapters.rag.rag_service import (
        EMBEDDING_DIMENSION,
        _deterministic_embedding,
    )

    first = _deterministic_embedding("clause one")
    again = _deterministic_embedding("clause one")
    other = _deterministic_embedding("clause two")

    assert len(first) == EMBEDDING_DIMENSION
    assert first == again
    assert first != other
    assert round(sum(value * value for value in first) ** 0.5, 6) == 1.0


def test_embeddings_mock_is_refused_in_production() -> None:
    """The acceptance harness must not be able to silently weaken production."""
    from src.config import Settings

    with pytest.raises(ValueError, match="C2PRO_EMBEDDINGS_MOCK"):
        Settings(
            ENVIRONMENT="production",
            C2PRO_AI_MOCK=False,  # isolate: the AI-mock guard would otherwise fire first
            C2PRO_EMBEDDINGS_MOCK=True,
            TEST_DATABASE_URL="postgresql://u:p@localhost:5432/db",
            DATABASE_URL="postgresql://u:p@localhost:5432/db",
            JWT_SECRET_KEY="x" * 32,
        )
