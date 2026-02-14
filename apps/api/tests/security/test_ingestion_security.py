"""
Security tests for ingestion module observability and review-gate integrity.
Test Suite ID: TS-SEC-ING-001
"""

from typing import Any
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from src.modules.ingestion.application.ports import OCRAdapter
from src.modules.ingestion.application.services import OCRProcessingService, TableParserService


class MockLangSmithClient:
    def __init__(self) -> None:
        self.spans: list[dict[str, Any]] = []

    def start_span(self, name: str, input: Any = None, run_type: str = "tool", **kwargs):
        span = {
            "name": name,
            "input": input,
            "run_type": run_type,
            "kwargs": kwargs,
            "id": uuid4(),
            "outputs": None,
        }
        self.spans.append(span)
        return span

    def end_span(self, span: dict[str, Any], outputs: Any = None) -> None:
        for stored in self.spans:
            if stored["id"] == span["id"]:
                stored["outputs"] = outputs
                return

    def get_spans_by_name(self, name: str) -> list[dict[str, Any]]:
        return [s for s in self.spans if s["name"] == name]


@pytest.fixture
def mock_primary_ocr_adapter() -> AsyncMock:
    adapter = AsyncMock(spec=OCRAdapter)
    adapter.process_pdf_page.return_value = {
        "text": "Extracted text from primary OCR.",
        "bboxes": [[0.1, 0.1, 0.2, 0.2, 0.9]],
        "confidence": 0.95,
        "provider": "PrimaryOCR",
    }
    return adapter


@pytest.fixture
def mock_fallback_ocr_adapter() -> AsyncMock:
    adapter = AsyncMock(spec=OCRAdapter)
    adapter.process_pdf_page.return_value = {
        "text": "Extracted text from fallback OCR.",
        "bboxes": [[0.1, 0.1, 0.2, 0.2, 0.8]],
        "confidence": 0.85,
        "provider": "FallbackOCR",
    }
    return adapter


@pytest.mark.asyncio
async def test_i2_langsmith_ocr_trace_does_not_include_raw_page_content(
    mock_primary_ocr_adapter: AsyncMock,
    mock_fallback_ocr_adapter: AsyncMock,
) -> None:
    """TS-SEC-ING-001 - Trace input must not log raw document bytes or OCR text."""
    langsmith = MockLangSmithClient()
    service = OCRProcessingService(mock_primary_ocr_adapter, mock_fallback_ocr_adapter, low_confidence_threshold=0.5)

    raw_pdf = b"%PDF-raw-sensitive-contract-content%"
    await service.process_page_with_fallback(raw_pdf, mock_langsmith=langsmith)

    spans = langsmith.get_spans_by_name("ocr_processing_with_fallback")
    assert len(spans) == 1
    span_input = spans[0]["input"]
    span_outputs = spans[0]["outputs"]

    assert "page_content_len" in span_input
    assert "page_content" not in span_input
    assert "raw_pdf" not in span_input
    assert "text" not in span_outputs


@pytest.mark.asyncio
async def test_i2_low_confidence_table_gate_cannot_be_bypassed_by_metadata() -> None:
    """TS-SEC-ING-001 - Low-confidence tables must be flagged for review regardless of incoming metadata."""
    extractor = AsyncMock()
    extractor.extract_tables_from_pdf_page.return_value = [
        {
            "rows": [["Item", "Qty"], ["Steel", "100"]],
            "confidence": 0.2,
            "metadata": {"needs_human_review": False, "reason": "manual_override_attempt"},
        }
    ]

    service = TableParserService(table_extractor=extractor, low_confidence_threshold=0.5)
    tables = await service.extract_tables_from_pdf_page(b"table-bytes")

    assert len(tables) == 1
    assert tables[0].confidence < 0.5
    assert tables[0].metadata.get("needs_human_review") is True
    assert tables[0].metadata.get("reason") == "low_table_confidence"
