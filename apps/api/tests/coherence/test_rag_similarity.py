
"""
Tests for RAG Similarity Detection — Coherence Engine Phase 6

Tests the embedding-based similarity detection for cross-document analysis:
1. EmbeddingRepository interface and pgvector adapter
2. RAG similarity check node
3. Embedding enrichment in prepare_context
4. Zero-LLM cost verification

Location: apps/api/tests/coherence/test_rag_similarity.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.coherence.adapters.persistence.pgvector_embedding_repository import (
    PgvectorEmbeddingRepository,
)
from src.coherence.graph.nodes import prepare_context_async, rag_similarity_check_async
from src.coherence.graph.state import (
    ClauseWithEmbedding,
    CoherenceGraphState,
    EvaluationConfig,
)
from src.coherence.models import Clause
from src.coherence.ports.embedding_repository import (
    EmbeddingMatch,
    EmbeddingRecord,
    EmbeddingSearchResult,
    IEmbeddingRepository,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_embedding() -> list[float]:
    """Generate a sample 1536-dimensional embedding."""
    return [0.1] * 1536


@pytest.fixture
def sample_project_id() -> UUID:
    """Sample project UUID."""
    return uuid4()


@pytest.fixture
def sample_clause() -> Clause:
    """Sample clause for testing."""
    return Clause(
        id="BUD-001",
        text="Budget item: $100,000 for steel beams",
        data={"line_total": 100000, "unit_price": 1000, "quantity": 100},
    )


@pytest.fixture
def sample_embedding_record(
    sample_project_id: UUID, sample_embedding: list[float]
) -> EmbeddingRecord:
    """Sample embedding record."""
    return EmbeddingRecord(
        clause_id="BUD-001",
        project_id=sample_project_id,
        document_id=uuid4(),
        document_type="budget",
        text="Budget item: $100,000 for steel beams",
        embedding=sample_embedding,
        category="BUDGET",
        metadata={"line_total": 100000},
        created_at=datetime.now(UTC),
    )


# =============================================================================
# DTO TESTS
# =============================================================================


def test_embedding_record_has_embedding(sample_embedding_record: EmbeddingRecord):
    """Test EmbeddingRecord.has_embedding() method."""
    assert sample_embedding_record.has_embedding() is True

    empty_record = EmbeddingRecord(
        clause_id="TEST-001",
        project_id=uuid4(),
        embedding=[],
    )
    assert empty_record.has_embedding() is False


def test_embedding_match_is_high_similarity(sample_project_id: UUID):
    """Test EmbeddingMatch.is_high_similarity() method."""
    high_match = EmbeddingMatch(
        source_clause_id="BUD-001",
        target_clause_id="SCH-001",
        target_project_id=sample_project_id,
        similarity_score=0.92,
    )
    assert high_match.is_high_similarity(threshold=0.85) is True

    low_match = EmbeddingMatch(
        source_clause_id="BUD-001",
        target_clause_id="SCH-002",
        target_project_id=sample_project_id,
        similarity_score=0.75,
    )
    assert low_match.is_high_similarity(threshold=0.85) is False


def test_embedding_search_result_top_match(sample_project_id: UUID):
    """Test EmbeddingSearchResult.top_match() method."""
    matches = [
        EmbeddingMatch(
            source_clause_id="BUD-001",
            target_clause_id="SCH-001",
            target_project_id=sample_project_id,
            similarity_score=0.85,
        ),
        EmbeddingMatch(
            source_clause_id="BUD-001",
            target_clause_id="SCH-002",
            target_project_id=sample_project_id,
            similarity_score=0.92,
        ),
        EmbeddingMatch(
            source_clause_id="BUD-001",
            target_clause_id="SCH-003",
            target_project_id=sample_project_id,
            similarity_score=0.78,
        ),
    ]

    result = EmbeddingSearchResult(
        query_clause_id="BUD-001",
        matches=matches,
    )

    assert result.match_count == 3
    top = result.top_match()
    assert top is not None
    assert top.target_clause_id == "SCH-002"
    assert top.similarity_score == 0.92

    # Empty result
    empty_result = EmbeddingSearchResult(query_clause_id="BUD-001", matches=[])
    assert empty_result.top_match() is None


# =============================================================================
# PGVECTOR REPOSITORY TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_pgvector_store_embedding_validates_dimension(sample_project_id: UUID):
    """Test that store_embedding validates embedding dimension."""
    mock_session = AsyncMock()
    repo = PgvectorEmbeddingRepository(mock_session)

    # Invalid dimension should raise ValueError
    with pytest.raises(ValueError, match="Invalid embedding dimension"):
        await repo.store_embedding(
            clause_id="TEST-001",
            project_id=sample_project_id,
            embedding=[0.1] * 100,  # Wrong size!
        )


@pytest.mark.asyncio
async def test_pgvector_store_embedding_truncates_text(
    sample_project_id: UUID, sample_embedding: list[float]
):
    """Test that store_embedding truncates long text."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchone.return_value = (datetime.now(UTC),)
    mock_session.execute.return_value = mock_result

    repo = PgvectorEmbeddingRepository(mock_session)

    long_text = "A" * 2000  # 2000 chars
    record = await repo.store_embedding(
        clause_id="TEST-001",
        project_id=sample_project_id,
        embedding=sample_embedding,
        text=long_text,
    )

    assert len(record.text) == 1000  # Truncated
    assert record.text == "A" * 1000


@pytest.mark.asyncio
async def test_pgvector_store_embeddings_batch_validates_all(
    sample_project_id: UUID, sample_embedding: list[float]
):
    """Test that batch store validates all embeddings."""
    mock_session = AsyncMock()
    repo = PgvectorEmbeddingRepository(mock_session)

    records = [
        EmbeddingRecord(
            clause_id="TEST-001",
            project_id=sample_project_id,
            embedding=sample_embedding,
        ),
        EmbeddingRecord(
            clause_id="TEST-002",
            project_id=sample_project_id,
            embedding=[0.1] * 100,  # Invalid!
        ),
    ]

    with pytest.raises(ValueError, match="Invalid embedding dimension"):
        await repo.store_embeddings_batch(records)


@pytest.mark.asyncio
async def test_pgvector_find_similar_validates_dimension(sample_project_id: UUID):
    """Test that find_similar validates query embedding dimension."""
    mock_session = AsyncMock()
    repo = PgvectorEmbeddingRepository(mock_session)

    with pytest.raises(ValueError, match="Invalid embedding dimension"):
        await repo.find_similar(
            embedding=[0.1] * 100,  # Wrong size!
            project_id=sample_project_id,
        )


@pytest.mark.asyncio
async def test_pgvector_find_similar_returns_matches(
    sample_project_id: UUID, sample_embedding: list[float]
):
    """Test that find_similar returns EmbeddingMatch objects."""
    mock_session = AsyncMock()
    mock_result = MagicMock()

    # Simulate database response
    # Row format: (clause_id, document_id, document_type, text, category, metadata, similarity)
    mock_result.__iter__.return_value = [
        (
            "SCH-001",
            str(uuid4()),
            "schedule",
            "Milestone 1",
            "TIME",
            {},
            0.92,
        ),
        (
            "SCH-002",
            str(uuid4()),
            "schedule",
            "Milestone 2",
            "TIME",
            {},
            0.87,
        ),
    ]
    mock_session.execute.return_value = mock_result

    repo = PgvectorEmbeddingRepository(mock_session)

    matches = await repo.find_similar(
        embedding=sample_embedding,
        project_id=sample_project_id,
        top_k=10,
        similarity_threshold=0.85,
    )

    assert len(matches) == 2
    assert matches[0].target_clause_id == "SCH-001"
    assert matches[0].similarity_score == 0.92
    assert matches[0].target_category == "TIME"
    assert matches[1].target_clause_id == "SCH-002"
    assert matches[1].similarity_score == 0.87


@pytest.mark.asyncio
async def test_pgvector_find_cross_document_pairs(sample_project_id: UUID):
    """Test that find_cross_document_pairs returns cross-document matches."""
    mock_session = AsyncMock()
    mock_result = MagicMock()

    # Row format: (source_clause_id, target_clause_id, source_doc_type,
    #              target_doc_type, source_category, target_category, similarity)
    mock_result.__iter__.return_value = [
        ("BUD-001", "SCH-001", "budget", "schedule", "BUDGET", "TIME", 0.89),
        ("BUD-002", "TEC-001", "budget", "bom", "BUDGET", "TECHNICAL", 0.86),
    ]
    mock_session.execute.return_value = mock_result

    repo = PgvectorEmbeddingRepository(mock_session)

    matches = await repo.find_cross_document_pairs(
        project_id=sample_project_id,
        similarity_threshold=0.85,
        max_pairs=20,
    )

    assert len(matches) == 2
    assert matches[0].source_clause_id == "BUD-001"
    assert matches[0].target_clause_id == "SCH-001"
    assert matches[0].target_document_type == "schedule"
    assert matches[0].similarity_score == 0.89
    assert matches[0].match_reason == "cross_document_similarity"


# =============================================================================
# RAG SIMILARITY CHECK NODE TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_rag_similarity_check_skips_when_disabled():
    """Test that RAG check is skipped when disabled in config."""
    state = CoherenceGraphState(
        project_id=str(uuid4()),
        clauses=[],
        config=EvaluationConfig(include_rag_similarity=False),
    )

    result = await rag_similarity_check_async(state)

    assert result["cross_pairs"] == []


@pytest.mark.asyncio
async def test_rag_similarity_check_skips_when_no_clauses():
    """Test that RAG check is skipped when no enriched clauses."""
    state = CoherenceGraphState(
        project_id=str(uuid4()),
        clauses=[],
        config=EvaluationConfig(include_rag_similarity=True),
        enriched_clauses=[],
    )

    result = await rag_similarity_check_async(state)

    assert result["cross_pairs"] == []


@pytest.mark.asyncio
async def test_rag_similarity_check_with_invalid_project_id():
    """Test that RAG check handles invalid project ID gracefully."""
    state = CoherenceGraphState(
        project_id="not-a-uuid",
        clauses=[Clause(id="TEST-001", text="Test", data={})],
        config=EvaluationConfig(include_rag_similarity=True),
        enriched_clauses=[
            ClauseWithEmbedding(
                clause=Clause(id="TEST-001", text="Test", data={}),
                embedding=[0.1] * 1536,
            )
        ],
    )

    result = await rag_similarity_check_async(state)

    # Should log error but not crash
    assert "errors" in result
    assert len(result["errors"]) > 0


# =============================================================================
# PREPARE CONTEXT NODE TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_prepare_context_enriches_clauses():
    """Test that prepare_context enriches clauses with categories."""
    clauses = [
        Clause(
            id="BUD-001",
            text="Budget: $100,000",
            data={"line_total": 100000},
        ),
        Clause(
            id="SCH-001",
            text="Deadline: 2024-06-01",
            data={"end_date": "2024-06-01"},
        ),
    ]

    state = CoherenceGraphState(
        project_id=str(uuid4()),
        clauses=clauses,
        config=EvaluationConfig(),
    )

    result = await prepare_context_async(state)

    assert "enriched_clauses" in result
    enriched = result["enriched_clauses"]
    assert len(enriched) == 2
    assert enriched[0].category == "BUDGET"
    assert enriched[1].category == "TIME"


@pytest.mark.asyncio
async def test_prepare_context_creates_cross_pairs():
    """Test that prepare_context creates category-based cross-pairs."""
    clauses = [
        Clause(id="BUD-001", text="Budget: $100,000", data={"line_total": 100000}),
        Clause(id="SCH-001", text="Deadline: 2024-06-01", data={"end_date": "2024-06-01"}),
    ]

    state = CoherenceGraphState(
        project_id=str(uuid4()),
        clauses=clauses,
        config=EvaluationConfig(include_cross_clause=True),
    )

    result = await prepare_context_async(state)

    assert "cross_pairs" in result
    pairs = result["cross_pairs"]
    # Should create BUDGET-TIME pair
    assert len(pairs) > 0
    assert any(
        p.clause_a.category == "BUDGET" and p.clause_b.category == "TIME"
        for p in pairs
    )


@pytest.mark.asyncio
async def test_prepare_context_limits_cross_pairs():
    """Test that prepare_context respects max_cross_pairs limit."""
    # Create many clauses to test limit
    clauses = []
    for i in range(20):
        clauses.append(
            Clause(id=f"BUD-{i:03d}", text=f"Budget item {i}", data={"line_total": i})
        )
    for i in range(20):
        clauses.append(
            Clause(id=f"SCH-{i:03d}", text=f"Schedule item {i}", data={"end_date": f"2024-{i:02d}-01"})
        )

    state = CoherenceGraphState(
        project_id=str(uuid4()),
        clauses=clauses,
        config=EvaluationConfig(
            include_cross_clause=True,
            max_cross_pairs=10,  # Limit to 10
        ),
    )

    result = await prepare_context_async(state)

    pairs = result["cross_pairs"]
    assert len(pairs) <= 10  # Should respect limit


# =============================================================================
# ZERO-LLM COST VERIFICATION
# =============================================================================


@pytest.mark.asyncio
async def test_rag_similarity_zero_llm_cost():
    """
    CRITICAL: Verify that RAG similarity check has zero LLM cost.

    This test ensures Phase 6's requirement of pure SQL similarity
    detection without any LLM API calls.
    """
    state = CoherenceGraphState(
        project_id=str(uuid4()),
        clauses=[Clause(id="TEST-001", text="Test", data={})],
        config=EvaluationConfig(include_rag_similarity=True),
        enriched_clauses=[
            ClauseWithEmbedding(
                clause=Clause(id="TEST-001", text="Test", data={}),
                embedding=[0.1] * 1536,
            )
        ],
    )

    # Patch OpenAI client to verify it's never called
    with patch("httpx.AsyncClient") as mock_client:
        result = await rag_similarity_check_async(state)

        # OpenAI should never be called during RAG similarity check
        mock_client.assert_not_called()

    # Verify no LLM cost in result
    assert result.get("llm_cost_usd", 0.0) == pytest.approx(0.0)
    assert result.get("llm_calls_count", 0) == 0


# =============================================================================
# HEXAGONAL ARCHITECTURE VERIFICATION
# =============================================================================


def test_embedding_repository_is_interface():
    """Verify IEmbeddingRepository follows hexagonal architecture."""
    from abc import ABC

    assert issubclass(IEmbeddingRepository, ABC)

    # Verify all methods are abstract
    abstract_methods = [
        "store_embedding",
        "store_embeddings_batch",
        "find_similar",
        "find_cross_document_pairs",
        "get_embedding",
        "delete_project_embeddings",
        "count_embeddings",
    ]

    for method_name in abstract_methods:
        method = getattr(IEmbeddingRepository, method_name, None)
        assert method is not None, f"Method {method_name} not found"
        assert getattr(method, "__isabstractmethod__", False), \
            f"Method {method_name} is not abstract"


def test_pgvector_implements_interface():
    """Verify PgvectorEmbeddingRepository implements IEmbeddingRepository."""
    assert issubclass(PgvectorEmbeddingRepository, IEmbeddingRepository)

    # Verify all interface methods are implemented
    repo_methods = dir(PgvectorEmbeddingRepository)
    interface_methods = [
        "store_embedding",
        "store_embeddings_batch",
        "find_similar",
        "find_cross_document_pairs",
        "get_embedding",
        "delete_project_embeddings",
        "count_embeddings",
    ]

    for method in interface_methods:
        assert method in repo_methods, \
            f"Method {method} not implemented in PgvectorEmbeddingRepository"


# =============================================================================
# INTEGRATION TESTS (Require Database)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pgvector_full_workflow_integration(
    sample_project_id: UUID, sample_embedding: list[float]
):
    """
    Integration test for full pgvector workflow.

    This test requires a real database with pgvector extension.
    """
    pytest.skip("Integration test requires database setup")

    # TODO: Implement once database fixtures are set up
    # from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    #
    # engine = create_async_engine("postgresql+asyncpg://...")
    # async with AsyncSession(engine) as session:
    #     repo = PgvectorEmbeddingRepository(session)
    #
    #     # Store embedding
    #     record = await repo.store_embedding(
    #         clause_id="BUD-001",
    #         project_id=sample_project_id,
    #         embedding=sample_embedding,
    #         category="BUDGET",
    #     )
    #     assert record.clause_id == "BUD-001"
    #
    #     # Find similar
    #     matches = await repo.find_similar(
    #         embedding=sample_embedding,
    #         project_id=sample_project_id,
    #     )
    #     assert len(matches) > 0
    #
    #     # Delete
    #     count = await repo.delete_project_embeddings(sample_project_id)
    #     assert count >= 1


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================


@pytest.mark.performance
@pytest.mark.asyncio
async def test_rag_similarity_performance(sample_project_id: UUID):
    """
    Verify RAG similarity check completes within performance budget.

    Target: <100ms for typical 10-clause project with 100 stored embeddings.
    """
    import time

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.__iter__.return_value = []  # Empty results
    mock_session.execute.return_value = mock_result

    state = CoherenceGraphState(
        project_id=str(sample_project_id),
        clauses=[Clause(id=f"TEST-{i:03d}", text=f"Clause {i}", data={}) for i in range(10)],
        config=EvaluationConfig(include_rag_similarity=True),
        enriched_clauses=[
            ClauseWithEmbedding(
                clause=Clause(id=f"TEST-{i:03d}", text=f"Clause {i}", data={}),
                embedding=[0.1] * 1536,
            )
            for i in range(10)
        ],
    )

    start = time.time()
    await rag_similarity_check_async(state)
    elapsed_ms = (time.time() - start) * 1000

    # Should complete quickly (mostly just function overhead in mocked version)
    assert elapsed_ms < 100, f"RAG check took {elapsed_ms:.2f}ms (target: <100ms)"
