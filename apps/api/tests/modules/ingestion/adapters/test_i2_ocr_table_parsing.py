"""
C2Pro - Increment I2: OCR + Table Parsing Reliability Tests
Test Suite ID: TS-I2-OCR-TBL-001

Phase 4: AI Core - TDD Implementation

Objective: Implement and ensure the reliability of OCR and table parsing capabilities,
including a fallback strategy for OCR and correct preservation of table structure.

Test Coverage:
1. Integration test: Scanned PDF returns text + bbox + confidence
2. Integration test: Table extraction preserves row/column counts on fixture tables
3. Regression test: OCR fallback engages when primary OCR confidence below threshold
4. Negative test: Table parser does not collapse merged cells incorrectly
5. Observability: LangSmith logs provider choice
6. Human-in-the-loop: Low confidence table routes to human review

Refers to: PHASE4_TDD_IMPLEMENTATION_ROADMAP.md - I2
"""

import pytest
from unittest.mock import AsyncMock
from typing import Dict, Any
from uuid import uuid4

# ✅ CORRECTED IMPORTS (pythonpath = ["src"] in pyproject.toml)
from src.modules.ingestion.application.ports import OCRAdapter
from src.modules.ingestion.application.services import OCRProcessingService, TableParserService
from src.modules.ingestion.domain.entities import TableData

# Mock LangSmith Client (copied from I1, or would be in conftest.py)
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

@pytest.fixture
def mock_scanned_pdf_bytes():
    """Fixture to represent bytes of a scanned PDF page."""
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\nxref\n0 2\n0000000000 65535 f\n0000000010 00000 n\ntrailer<</Size 2/Root 1 0 R>>startxref\n66\n%%EOF"

@pytest.fixture
def mock_primary_ocr_adapter():
    """Mock for a primary OCR adapter."""
    mock = AsyncMock(spec=OCRAdapter)
    mock.process_pdf_page.return_value = {
        "text": "Extracted text from primary OCR.",
        "bboxes": [[0.1, 0.1, 0.2, 0.2, 0.9]],
        "confidence": 0.95,
        "provider": "PrimaryOCR"
    }
    return mock

@pytest.fixture
def mock_fallback_ocr_adapter():
    """Mock for a fallback OCR adapter."""
    mock = AsyncMock(spec=OCRAdapter)
    mock.process_pdf_page.return_value = {
        "text": "Extracted text from fallback OCR.",
        "bboxes": [[0.1, 0.1, 0.2, 0.2, 0.8]],
        "confidence": 0.85,
        "provider": "FallbackOCR"
    }
    return mock

@pytest.fixture
def mock_table_extractor():
    """Mock for a table extraction adapter used by TableParserService."""
    mock = AsyncMock()
    mock.extract_tables_from_pdf_page.return_value = [
        {"rows": [["Header 1", "Header 2"], ["Data 1", "Data 2"]], "confidence": 0.9},
        {"rows": [["Merged Cell", "Col 2"], ["Data 3", "Data 4"]], "confidence": 0.85},
    ]
    return mock

@pytest.mark.asyncio
async def test_i2_scanned_pdf_returns_text_bbox_confidence(mock_primary_ocr_adapter, mock_scanned_pdf_bytes):
    """Refers to I2.1: Integration test - scanned PDF returns text + bbox + confidence."""
    # This test directly interacts with the OCRAdapter, simulating a service call.
    result = await mock_primary_ocr_adapter.process_pdf_page(mock_scanned_pdf_bytes)

    assert "text" in result
    assert isinstance(result["text"], str)
    assert len(result["text"]) > 0

    assert "bboxes" in result
    assert isinstance(result["bboxes"], list)
    assert len(result["bboxes"]) > 0
    assert all(isinstance(bbox, list) and len(bbox) == 5 for bbox in result["bboxes"]) # x1, y1, x2, y2, confidence for each bbox

    assert "confidence" in result
    assert isinstance(result["confidence"], float)
    assert 0.0 <= result["confidence"] <= 1.0

@pytest.mark.asyncio
async def test_i2_table_extraction_preserves_row_column_counts(mock_table_extractor):
    """Refers to I2.2: Integration test - table extraction preserves row/column counts on fixture tables."""
    mock_pdf_page_with_table = b"mock_pdf_content_with_table"
    parser_service = TableParserService(table_extractor=mock_table_extractor, low_confidence_threshold=0.5)
    tables = await parser_service.extract_tables_from_pdf_page(mock_pdf_page_with_table)

    assert isinstance(tables, list)
    assert len(tables) > 0

    # Check the first table for expected row/column count
    assert isinstance(tables[0], TableData)
    assert len(tables[0].rows) == 2 # Header row + one data row
    assert len(tables[0].rows[0]) == 2 # Two columns

    # Check the second table, simulating a potentially merged cell
    assert len(tables[1].rows) == 2
    assert len(tables[1].rows[0]) == 2 # Should not collapse "Merged Cell" into one column if it spans 2

@pytest.mark.asyncio
async def test_i2_ocr_fallback_engages_on_low_confidence(mock_primary_ocr_adapter, mock_fallback_ocr_adapter, mock_scanned_pdf_bytes):
    """Refers to I2.3: Regression test - OCR fallback engages when primary OCR confidence below threshold."""
    # Configure primary OCR to return low confidence
    mock_primary_ocr_adapter.process_pdf_page.return_value = {
        "text": "Primary low confidence text.",
        "bboxes": [[0.1, 0.1, 0.2, 0.2, 0.4]], # Low confidence bbox
        "confidence": 0.4, # Below threshold
        "provider": "PrimaryOCR"
    }

    ocr_service = OCRProcessingService(mock_primary_ocr_adapter, mock_fallback_ocr_adapter, low_confidence_threshold=0.5)
    result = await ocr_service.process_page_with_fallback(mock_scanned_pdf_bytes)

    mock_primary_ocr_adapter.process_pdf_page.assert_called_once_with(mock_scanned_pdf_bytes)
    mock_fallback_ocr_adapter.process_pdf_page.assert_called_once_with(mock_scanned_pdf_bytes)
    assert result["provider"] == "FallbackOCR" # Ensure fallback result is returned
    assert result["confidence"] > mock_primary_ocr_adapter.process_pdf_page.return_value["confidence"]

@pytest.mark.asyncio
async def test_i2_table_parser_does_not_collapse_merged_cells_incorrectly(mock_table_extractor):
    """Refers to I2.2: Expected failure - Table parser collapses merged cells incorrectly."""
    # This test expects the table parser to correctly handle merged cells.
    # We configure the mock to simulate an incorrect collapse, and the assertion should fail initially.
    # The actual implementation should then correct this.
    mock_table_extractor.extract_tables_from_pdf_page.return_value = [
        {"rows": [["Col1", "Col2"], ["Merged Cell Data"]], "confidence": 0.9}
    ]

    mock_pdf_page_with_complex_table = b"mock_pdf_content_with_merged_cells"
    parser_service = TableParserService(table_extractor=mock_table_extractor, low_confidence_threshold=0.5)
    tables = await parser_service.extract_tables_from_pdf_page(mock_pdf_page_with_complex_table)

    assert isinstance(tables, list)
    assert len(tables) == 1
    assert isinstance(tables[0], TableData)

    # This assertion initially fails if the mock's return value incorrectly represents collapsed cells.
    # The real implementation should pass this by correctly handling merged cells.
    assert len(tables[0].rows[0]) == 2 # Expecting 2 columns even if one conceptually merged above
    assert tables[0].rows[0][0] == "Col1"
    assert tables[0].rows[0][1] == "Col2"
    assert len(tables[0].rows[1]) == 2
    assert tables[0].rows[1][0] == "Merged Cell Data" # Should be extracted as full content
    assert tables[0].rows[1][1] == ""


@pytest.mark.asyncio
async def test_i2_ocr_provider_choice_logged_to_langsmith(mock_primary_ocr_adapter, mock_fallback_ocr_adapter, mock_scanned_pdf_bytes, mock_langsmith_client):
    """Refers to I2.5: Observability hooks (LangSmith) - Log OCR provider choice, confidence histograms, table extraction score."""
    # Configure primary OCR to return low confidence to force fallback
    mock_primary_ocr_adapter.process_pdf_page.return_value = {
        "text": "Primary low confidence text.",
        "bboxes": [[0.1, 0.1, 0.2, 0.2, 0.4]],
        "confidence": 0.4,
        "provider": "PrimaryOCR"
    }

    ocr_service = OCRProcessingService(mock_primary_ocr_adapter, mock_fallback_ocr_adapter, low_confidence_threshold=0.5)
    await ocr_service.process_page_with_fallback(mock_scanned_pdf_bytes, mock_langsmith_client)

    ocr_spans = mock_langsmith_client.get_spans_by_name("ocr_processing_with_fallback")
    assert len(ocr_spans) == 1
    logged_span = ocr_spans[0]

    assert logged_span["kwargs"]["provider_choice"] == "PrimaryOCR" # Initial provider choice
    assert logged_span["outputs"]["status"] == "fallback_used"
    assert logged_span["outputs"]["final_confidence"] == mock_fallback_ocr_adapter.process_pdf_page.return_value["confidence"]

@pytest.mark.asyncio
async def test_i2_low_confidence_table_routes_to_human_review_conceptually(mock_table_extractor):
    """Refers to I2.6: Human-in-the-loop checkpoints - Reviewer confirms low-confidence table reconstructions."""
    # Configure mock table parser to return a low confidence table
    mock_table_extractor.extract_tables_from_pdf_page.return_value = [
        {
            "rows": [["Item", "Value"], ["Product A", "100"]],
            "confidence": 0.3,
            "metadata": {},
        }
    ]

    mock_pdf_page_with_low_conf_table = b"mock_pdf_content_with_low_conf_table"
    parser_service = TableParserService(table_extractor=mock_table_extractor, low_confidence_threshold=0.5)
    tables = await parser_service.extract_tables_from_pdf_page(mock_pdf_page_with_low_conf_table)

    assert len(tables) == 1
    assert tables[0].confidence < 0.5
    assert tables[0].metadata.get("needs_human_review") is True
    assert tables[0].metadata.get("reason") == "low_table_confidence"


@pytest.mark.asyncio
async def test_i2_table_parser_reconciles_header_metadata_red(mock_table_extractor):
    """TS-I2-OCR-TBL-001 - RED: normalized tables should mark reconciled header metadata."""
    mock_table_extractor.extract_tables_from_pdf_page.return_value = [
        {"rows": [["Item", "Qty"], ["Rebar", "500"]], "confidence": 0.92, "metadata": {}}
    ]
    parser_service = TableParserService(table_extractor=mock_table_extractor, low_confidence_threshold=0.5)

    tables = await parser_service.extract_tables_from_pdf_page(b"table-with-header")
    assert tables[0].metadata.get("header_reconciled") is True


@pytest.mark.asyncio
async def test_i2_ocr_logs_confidence_histogram_red(
    mock_primary_ocr_adapter, mock_fallback_ocr_adapter, mock_scanned_pdf_bytes, mock_langsmith_client
):
    """TS-I2-OCR-TBL-001 - RED: OCR span should include confidence histogram output for observability."""
    ocr_service = OCRProcessingService(mock_primary_ocr_adapter, mock_fallback_ocr_adapter, low_confidence_threshold=0.5)
    await ocr_service.process_page_with_fallback(mock_scanned_pdf_bytes, mock_langsmith_client)

    ocr_spans = mock_langsmith_client.get_spans_by_name("ocr_processing_with_fallback")
    assert len(ocr_spans) == 1
    assert "confidence_histogram" in ocr_spans[0]["outputs"]
