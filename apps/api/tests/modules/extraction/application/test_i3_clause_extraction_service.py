"""
I3 - Clause Extraction Service Tests

Integration and observability tests for ClauseExtractionService.
Refers to I3.2: Integration tests - extraction preserves clause IDs and obligation actors.
Refers to I3.5: Observability hooks (LangSmith).
Refers to I3.6: Human-in-the-loop checkpoints.
"""

import pytest
from unittest.mock import AsyncMock
from typing import Any
from uuid import UUID, uuid4
from datetime import date

from src.modules.ingestion.domain.entities import IngestionChunk
from src.modules.extraction.domain.entities import ExtractedClause
from src.modules.extraction.application.ports import ClauseExtractionService, LLMAdapter


class MockLangSmithClient:
    """Mock LangSmith client for testing observability hooks."""

    def __init__(self):
        self.spans = []

    def start_span(self, name: str, input: Any = None, run_type: str = "tool", **kwargs):
        span = {
            "name": name,
            "input": input,
            "run_type": run_type,
            "kwargs": kwargs,
            "id": uuid4(),
            "outputs": None
        }
        self.spans.append(span)
        return span

    def end_span(self, span: dict[str, Any], outputs: Any = None):
        for s in self.spans:
            if s["id"] == span["id"]:
                s["outputs"] = outputs
                break

    def get_spans_by_name(self, name: str):
        return [s for s in self.spans if s["name"] == name]


@pytest.fixture
def mock_langsmith_client():
    return MockLangSmithClient()


@pytest.fixture
def mock_llm_adapter():
    """Mock for the LLM adapter used in clause extraction."""
    mock = AsyncMock(spec=LLMAdapter)
    # Simulate LLM response for clause extraction
    mock.extract_structured_data.return_value = {
        "clauses": [
            {
                "clause_id": str(uuid4()),
                "text": "The Contractor shall complete the work.",
                "type": "Work Obligation",
                "modality": "Shall",
                "due_date": None,
                "penalty_linkage": None,
                "confidence": 0.9,
                "ambiguity_flag": False,
                "actors": ["Contractor"],
                "metadata": {}
            },
            {
                "clause_id": str(uuid4()),
                "text": "The Client shall pay invoice within 30 days.",
                "type": "Payment Obligation",
                "modality": "Shall",
                "due_date": date(2024, 1, 30).isoformat(),  # LLM might return ISO format string
                "penalty_linkage": "Interest on late payment.",
                "confidence": 0.85,
                "ambiguity_flag": False,
                "actors": ["Client"],
                "metadata": {}
            }
        ],
        "prompt_version": "v1.0"
    }
    return mock


@pytest.fixture
def mock_ingestion_chunks() -> list[IngestionChunk]:
    """Fixture for mock IngestionChunk objects."""
    doc_id = uuid4()
    version_id = uuid4()
    return [
        IngestionChunk(
            doc_id=doc_id,
            version_id=version_id,
            page=1,
            content="1. The Contractor shall complete the work. 2. The Client shall pay invoice within 30 days.",
            bbox=[0, 0, 1, 1],
            source_hash="hash1",
            confidence=0.99
        )
    ]


@pytest.mark.asyncio
async def test_i3_extraction_preserves_clause_ids(mock_llm_adapter, mock_ingestion_chunks):
    """Refers to I3.2: Integration test - extraction preserves clause IDs."""
    extraction_service = ClauseExtractionService(llm_adapter=mock_llm_adapter)
    extracted_clauses = await extraction_service.extract_clauses(mock_ingestion_chunks)

    assert len(extracted_clauses) == 2
    assert all(isinstance(c.clause_id, UUID) for c in extracted_clauses)
    assert extracted_clauses[0].text == "The Contractor shall complete the work."
    assert extracted_clauses[1].text == "The Client shall pay invoice within 30 days."


@pytest.mark.asyncio
async def test_i3_extraction_preserves_obligation_actors(mock_llm_adapter, mock_ingestion_chunks):
    """Refers to I3.2: Integration test - extraction preserves obligation actors."""
    extraction_service = ClauseExtractionService(llm_adapter=mock_llm_adapter)
    extracted_clauses = await extraction_service.extract_clauses(mock_ingestion_chunks)

    assert len(extracted_clauses) == 2
    assert "Contractor" in extracted_clauses[0].actors
    assert "Client" in extracted_clauses[1].actors
    assert len(extracted_clauses[0].actors) == 1
    assert len(extracted_clauses[1].actors) == 1


@pytest.mark.asyncio
async def test_i3_missing_confidence_flags_for_ambiguous_clauses(mock_llm_adapter, mock_ingestion_chunks):
    """Refers to I3.4: Expected failure - Missing confidence flags for ambiguous clauses."""
    # Configure LLM to return an ambiguous clause with potentially low confidence
    mock_llm_adapter.extract_structured_data.return_value = {
        "clauses": [
            {
                "clause_id": str(uuid4()),
                "text": "The project might be delayed if conditions change.",
                "type": "Uncertainty",
                "modality": "Might",
                "due_date": None,
                "penalty_linkage": None,
                "confidence": 0.45,  # Low confidence
                "ambiguity_flag": True,  # Should be flagged by the service
                "actors": [],
                "metadata": {"reason": "vague language"}
            }
        ],
        "prompt_version": "v1.0"
    }

    extraction_service = ClauseExtractionService(llm_adapter=mock_llm_adapter)
    extracted_clauses = await extraction_service.extract_clauses(mock_ingestion_chunks)

    assert len(extracted_clauses) == 1
    assert extracted_clauses[0].confidence < 0.5
    assert extracted_clauses[0].ambiguity_flag is True  # Expected to be set by the service


@pytest.mark.asyncio
async def test_i3_langsmith_captures_prompt_version_and_extracted_entities(
    mock_llm_adapter, mock_ingestion_chunks, mock_langsmith_client
):
    """Refers to I3.5: Observability hooks (LangSmith) - Capture prompt version, retrieved context, extracted clause entities."""
    extraction_service = ClauseExtractionService(
        llm_adapter=mock_llm_adapter,
        langsmith_client=mock_langsmith_client
    )
    await extraction_service.extract_clauses(mock_ingestion_chunks)

    extraction_spans = mock_langsmith_client.get_spans_by_name("extract_clauses_run")
    assert len(extraction_spans) == 1
    logged_span = extraction_spans[0]

    assert logged_span["input"]["prompt_version"] == "v1.0"
    assert "chunk_content" in logged_span["input"]
    assert len(logged_span["outputs"]["extracted_clauses"]) > 0
    assert logged_span["outputs"]["extracted_clauses"][0]["type"] == "Work Obligation"


@pytest.mark.asyncio
async def test_i3_ambiguous_high_impact_clauses_require_mandatory_validation(
    mock_llm_adapter, mock_ingestion_chunks
):
    """Refers to I3.6: Human-in-the-loop checkpoints - Mandatory validation for ambiguous/high-impact clauses."""
    # Configure LLM to return a high-impact but ambiguous clause
    mock_llm_adapter.extract_structured_data.return_value = {
        "clauses": [
            {
                "clause_id": str(uuid4()),
                "text": "Any material breach by either party results in immediate contract termination.",
                "type": "Termination Clause",
                "modality": "Results In",
                "due_date": None,
                "penalty_linkage": "Immediate termination",
                "confidence": 0.6,  # Moderate confidence but high impact
                "ambiguity_flag": True,
                "actors": ["Either Party"],
                "metadata": {"impact": "high"}
            }
        ],
        "prompt_version": "v1.0"
    }

    extraction_service = ClauseExtractionService(llm_adapter=mock_llm_adapter)
    extracted_clauses = await extraction_service.extract_clauses(mock_ingestion_chunks)

    assert len(extracted_clauses) == 1
    clause = extracted_clauses[0]
    assert clause.ambiguity_flag is True
    assert clause.metadata.get("impact") == "high"
    # The service's responsibility would be to add a "requires_manual_validation" flag
    assert clause.metadata.get("requires_manual_validation") is True
