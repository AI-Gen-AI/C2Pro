"""
Security tests for extraction/retrieval review-gate enforcement.
Test Suite ID: TS-SEC-EXT-RET-001
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.ingestion.domain.entities import IngestionChunk
from src.modules.extraction.application.ports import ClauseExtractionService, LLMAdapter
from src.modules.retrieval.application.ports import (
    RetrievalService,
    VectorStore,
    KeywordSearch,
    Reranker,
    QueryRouter,
)
from src.modules.retrieval.domain.entities import RetrievalResult, QueryIntent


@pytest.fixture
def mock_ingestion_chunks() -> list[IngestionChunk]:
    doc_id = uuid4()
    version_id = uuid4()
    return [
        IngestionChunk(
            doc_id=doc_id,
            version_id=version_id,
            page=1,
            content="Critical contract content.",
            bbox=[0.0, 0.0, 1.0, 1.0],
            source_hash="a1b2c3d4e5f6" * 5 + "a1b2",
            confidence=0.99,
        )
    ]


@pytest.mark.asyncio
async def test_i3_low_confidence_clause_requires_manual_validation_with_reason(
    mock_ingestion_chunks: list[IngestionChunk],
) -> None:
    """TS-SEC-EXT-RET-001 - Low-confidence extraction outputs must require review with explicit reason."""
    llm_adapter = AsyncMock(spec=LLMAdapter)
    llm_adapter.extract_structured_data.return_value = {
        "clauses": [
            {
                "clause_id": str(uuid4()),
                "text": "The project might be delayed by unforeseen events.",
                "type": "Schedule Risk",
                "modality": "Might",
                "due_date": date(2025, 1, 1).isoformat(),
                "penalty_linkage": None,
                "confidence": 0.2,
                "ambiguity_flag": True,
                "actors": [" Contractor ", "Contractor", ""],
                "metadata": {},
            }
        ],
        "prompt_version": "v1.0",
    }

    service = ClauseExtractionService(llm_adapter=llm_adapter, low_confidence_threshold=0.5)
    clauses = await service.extract_clauses(mock_ingestion_chunks)

    assert len(clauses) == 1
    assert clauses[0].metadata.get("requires_manual_validation") is True
    assert clauses[0].metadata.get("manual_validation_reason") == "low_confidence"


@pytest.mark.asyncio
async def test_i3_high_impact_ambiguous_clause_requires_manual_validation(
    mock_ingestion_chunks: list[IngestionChunk],
) -> None:
    """TS-SEC-EXT-RET-001 - High-impact ambiguous extraction outputs must require review."""
    llm_adapter = AsyncMock(spec=LLMAdapter)
    llm_adapter.extract_structured_data.return_value = {
        "clauses": [
            {
                "clause_id": str(uuid4()),
                "text": "Any material breach results in immediate termination.",
                "type": "Termination Clause",
                "modality": "Shall",
                "due_date": None,
                "penalty_linkage": "Immediate termination",
                "confidence": 0.9,
                "ambiguity_flag": True,
                "actors": ["Client"],
                "metadata": {"impact": "high"},
            }
        ],
        "prompt_version": "v1.0",
    }

    service = ClauseExtractionService(llm_adapter=llm_adapter, low_confidence_threshold=0.5)
    clauses = await service.extract_clauses(mock_ingestion_chunks)

    assert len(clauses) == 1
    assert clauses[0].metadata.get("requires_manual_validation") is True
    assert clauses[0].metadata.get("manual_validation_reason") == "high_impact_ambiguity"


@pytest.mark.asyncio
async def test_i4_low_evidence_retrieval_result_requires_reviewer_validation() -> None:
    """TS-SEC-EXT-RET-001 - Low-evidence retrieval outputs must be gated for reviewer validation."""
    vector_store = AsyncMock(spec=VectorStore)
    keyword_search = AsyncMock(spec=KeywordSearch)
    reranker = AsyncMock(spec=Reranker)
    query_router = MagicMock(spec=QueryRouter)

    query_router.route_query_by_intent.return_value = QueryIntent.HYBRID
    vector_store.query.return_value = [
        RetrievalResult(
            doc_id=uuid4(),
            version_id=uuid4(),
            clause_id=uuid4(),
            text="Low evidence conceptual result.",
            score=0.35,
            metadata={"source_type": "vector"},
        )
    ]
    keyword_search.query.return_value = []
    reranker.rerank.return_value = [
        RetrievalResult(
            doc_id=uuid4(),
            version_id=uuid4(),
            clause_id=uuid4(),
            text="Low evidence conceptual result.",
            score=0.35,
            metadata={"source_type": "vector"},
        )
    ]

    service = RetrievalService(
        vector_store=vector_store,
        keyword_search=keyword_search,
        reranker=reranker,
        query_router=query_router,
        evidence_threshold=0.7,
    )
    results = await service.retrieve("query", top_k=1)

    assert len(results) == 1
    assert results[0].metadata.get("requires_reviewer_validation") is True
    assert results[0].metadata.get("evidence_failure_reason") == "below_threshold"
