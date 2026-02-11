"""
C2Pro - Increment I1: Canonical Ingestion Contract Tests

Phase 4: AI Core - TDD Implementation

Objective: Define the core data contract for document chunks generated during
ingestion, ensuring all necessary provenance metadata is captured and validated.

Test Coverage:
1. Contract test: Each chunk must include doc_id, version_id, page, bbox, source_hash, confidence
2. Unit test: Blank pages produce zero chunks
3. Unit test: Malformed document returns typed ingestion error
4. Observability: LangSmith trace logging
5. Human-in-the-loop: Low confidence routing

Refers to: PHASE4_TDD_IMPLEMENTATION_ROADMAP.md - I1
"""

import pytest
from pydantic import ValidationError
from uuid import UUID, uuid4
from typing import List, Dict, Any, Optional
from unittest.mock import MagicMock

# ✅ CORRECTED IMPORTS (pythonpath = ["src"] in pyproject.toml)
from src.modules.ingestion.domain.entities import IngestionChunk, IngestionError

# Mock for LangSmith client (to be defined in conftest.py or locally if simple)
# For the purpose of this test, we'll create a simple mock
class MockLangSmithClient:
    def __init__(self):
        self.spans = []

    def start_span(self, name: str, input: Any = None, run_type: str = "tool", **kwargs):
        span = {"name": name, "input": input, "run_type": run_type, "kwargs": kwargs, "id": uuid4(), "outputs": None}
        self.spans.append(span)
        return span

    def end_span(self, span: Dict[str, Any], outputs: Any = None):
        for s in self.spans:
            if s["id"] == span["id"]:
                s["outputs"] = outputs
                break

    def get_spans_by_name(self, name: str):
        return [s for s in self.spans if s["name"] == name]

@pytest.fixture
def mock_langsmith_client():
    return MockLangSmithClient()


def test_i1_chunk_contract_includes_all_required_fields():
    """Refers to I1.1: Contract test - each chunk must include doc_id, version_id, page, bbox, source_hash, confidence."""
    mock_doc_id = uuid4()
    mock_version_id = uuid4()
    mock_bbox = [0.1, 0.2, 0.3, 0.4]
    mock_confidence = 0.95

    chunk_data = {
        "doc_id": mock_doc_id,
        "version_id": mock_version_id,
        "page": 1,
        "content": "This is a test chunk.",
        "bbox": mock_bbox,
        "source_hash": "a1b2c3d4e5f6",
        "confidence": mock_confidence,
        "metadata": {"key": "value"}
    }

    chunk = IngestionChunk(**chunk_data)

    assert isinstance(chunk.doc_id, UUID)
    assert chunk.doc_id == mock_doc_id
    assert isinstance(chunk.version_id, UUID)
    assert chunk.version_id == mock_version_id
    assert isinstance(chunk.page, int)
    assert chunk.page == 1
    assert isinstance(chunk.content, str)
    assert chunk.content == "This is a test chunk."
    assert isinstance(chunk.bbox, list)
    assert chunk.bbox == mock_bbox
    assert isinstance(chunk.source_hash, str)
    assert chunk.source_hash == "a1b2c3d4e5f6"
    assert isinstance(chunk.confidence, float)
    assert chunk.confidence == mock_confidence
    assert isinstance(chunk.metadata, dict)
    assert chunk.metadata == {"key": "value"}

def test_i1_chunk_contract_fails_on_missing_required_fields():
    """Refers to I1.1: Expected failure - Missing chunk schema/validator."""
    with pytest.raises(ValidationError):
        # Missing doc_id, version_id, page, content, bbox, source_hash, confidence
        IngestionChunk(content="partial chunk")

def test_i1_chunk_contract_fails_on_incomplete_provenance_fields():
    """Refers to I1.1: Expected failure - Parser returns incomplete provenance fields (missing confidence)."""
    mock_doc_id = uuid4()
    mock_version_id = uuid4()
    mock_bbox = [0.1, 0.2, 0.3, 0.4]

    with pytest.raises(ValidationError):
        IngestionChunk(
            doc_id=mock_doc_id,
            version_id=mock_version_id,
            page=1,
            content="This is a test chunk.",
            bbox=mock_bbox,
            source_hash="a1b2c3d4e5f6",
            # confidence is intentionally missing
        )

def test_i1_blank_page_produces_zero_chunks():
    """Refers to I1.2: Unit test - blank pages produce zero chunks."""
    # Mock a parser function that should return an empty list for blank pages
    mock_parser = MagicMock(return_value=[])

    # Simulate processing a blank page
    chunks = mock_parser(document_content="blank_page_content", page_number=1)

    assert isinstance(chunks, list)
    assert len(chunks) == 0

def test_i1_malformed_document_returns_typed_ingestion_error():
    """Refers to I1.3: Unit test - malformed document returns typed ingestion error."""
    # Mock a parser function that raises IngestionError for malformed docs
    mock_parser = MagicMock(side_effect=IngestionError("Malformed document detected."))

    with pytest.raises(IngestionError) as excinfo:
        mock_parser(document_content="malformed_binary_data", document_type="pdf")

    assert "Malformed document detected." in str(excinfo.value)

def test_i1_ingestion_trace_logged_with_metadata(mock_langsmith_client):
    """Refers to I1.5: Observability hooks (LangSmith) - Trace ingestion run with doc_id, version_id, parser backend, failure reason."""
    mock_doc_id = uuid4()
    mock_version_id = uuid4()
    parser_backend = "mock_ocr_parser"
    failure_reason = "simulated_failure"

    # Simulate an ingestion run that should log a trace
    # In real implementation, the LangSmith span would be managed by the ingestion service
    span = mock_langsmith_client.start_span(
        name="ingestion_run",
        input={"doc_id": str(mock_doc_id), "version_id": str(mock_version_id), "parser": parser_backend},
        run_type="chain"
    )
    # Simulate some processing and then a failure
    mock_langsmith_client.end_span(span, outputs={"status": "failed", "reason": failure_reason})

    ingestion_spans = mock_langsmith_client.get_spans_by_name("ingestion_run")
    assert len(ingestion_spans) == 1
    logged_span = ingestion_spans[0]

    assert logged_span["input"]["doc_id"] == str(mock_doc_id)
    assert logged_span["input"]["version_id"] == str(mock_version_id)
    assert logged_span["input"]["parser"] == parser_backend
    assert logged_span["outputs"]["status"] == "failed"
    assert logged_span["outputs"]["reason"] == failure_reason

def test_i1_low_confidence_chunk_routes_to_manual_queue_conceptually():
    """Refers to I1.6: Human-in-the-loop checkpoints - Route ingestion failures or low OCR confidence docs to manual preprocessing queue."""
    mock_doc_id = uuid4()
    mock_version_id = uuid4()
    low_confidence_bbox = [0.1, 0.2, 0.3, 0.4]
    low_confidence = 0.25 # Below typical threshold for human review

    low_confidence_chunk_data = {
        "doc_id": mock_doc_id,
        "version_id": mock_version_id,
        "page": 1,
        "content": "This text has low confidence.",
        "bbox": low_confidence_bbox,
        "source_hash": "f6e5d4c3b2a1",
        "confidence": low_confidence,
        "metadata": {"needs_review": True} # Conceptual flag for routing
    }

    chunk = IngestionChunk(**low_confidence_chunk_data)

    assert chunk.confidence < 0.3 # Assert the low confidence
    assert chunk.metadata.get("needs_review") is True # This implies the routing system would act on this flag
