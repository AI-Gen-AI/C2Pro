# Path: apps/api/src/documents/tests/integration/test_i2_ocr_and_table_parsing.py
import pytest
from unittest.mock import MagicMock, AsyncMock

# TDD: These imports will fail until the application services and ports are created.
# These components are expected to be in `src.documents.application.*` or similar.
try:
    from src.documents.application.services import OCRProcessingService, TableParsingService
    from src.documents.application.ports import OCRAdapter, TableParser
    from src.documents.application.dtos import OCRResult, TableData
except ImportError:
    # Define dummy classes to allow the test file to be parsed before implementation
    OCRProcessingService = type("OCRProcessingService", (), {})
    TableParsingService = type("TableParsingService", (), {})
    OCRAdapter = type("OCRAdapter", (), {})
    TableParser = type("TableParser", (), {})
    OCRResult = type("OCRResult", (), {})
    TableData = type("TableData", (), {})


@pytest.fixture
def mock_scanned_pdf_page() -> bytes:
    """Provides a fixture representing the binary content of a scanned PDF page."""
    return b"%PDF-1.4-SCAN-CONTENT"


@pytest.fixture
def mock_pdf_page_with_table() -> bytes:
    """Provides a fixture representing a PDF page containing a table."""
    return b"%PDF-1.4-TABLE-CONTENT"


@pytest.fixture
def mock_primary_ocr_adapter() -> OCRAdapter:
    """A mock for the primary, high-speed OCR adapter."""
    mock = AsyncMock(spec=OCRAdapter)
    # This mock will be configured per-test.
    return mock


@pytest.fixture
def mock_fallback_ocr_adapter() -> OCRAdapter:
    """A mock for the secondary, high-accuracy OCR adapter."""
    mock = AsyncMock(spec=OCRAdapter)
    mock.process_page.return_value = OCRResult(
        text="Text from fallback OCR", confidence=0.85, provider="fallback-ocr"
    )
    return mock


@pytest.fixture
def ocr_service(
    mock_primary_ocr_adapter: OCRAdapter, mock_fallback_ocr_adapter: OCRAdapter
) -> OCRProcessingService:
    """
    TDD: This fixture expects an `OCRProcessingService` that orchestrates
    primary and fallback adapters. The service itself does not exist yet.
    """
    # The service is expected to take adapters and a confidence threshold.
    return OCRProcessingService(
        primary_adapter=mock_primary_ocr_adapter,
        fallback_adapter=mock_fallback_ocr_adapter,
        confidence_threshold=0.7,
    )


@pytest.mark.integration
@pytest.mark.tdd
class TestOcrAndTableParsing:
    """
    Test suite for I2 - OCR + Table Parsing Reliability.
    """

    @pytest.mark.asyncio
    async def test_i2_01_scanned_pdf_returns_structured_ocr_result(
        self, ocr_service: OCRProcessingService, mock_scanned_pdf_page: bytes
    ):
        """
        [TEST-I2-01] Verifies an OCR service returns text, coordinates, and confidence.
        """
        # Arrange: Configure the primary OCR to return a successful, high-confidence result.
        ocr_service.primary_adapter.process_page.return_value = OCRResult(
            text="Sample OCR text", confidence=0.95, provider="primary-ocr"
        )

        # Act: This call will fail until the service and its methods are implemented.
        result: OCRResult = await ocr_service.process_page(mock_scanned_pdf_page)

        # Assert
        assert isinstance(result, OCRResult)
        assert hasattr(result, "text") and result.text == "Sample OCR text"
        assert hasattr(result, "confidence") and result.confidence == 0.95
        assert hasattr(result, "provider") and result.provider == "primary-ocr"

    @pytest.mark.asyncio
    async def test_i2_02_table_parser_preserves_row_and_column_counts(
        self, mock_pdf_page_with_table: bytes
    ):
        """
        [TEST-I2-02] Verifies a table parser preserves row/column counts.
        """
        # Arrange: This test expects a `TableParsingService` to exist.
        table_service = TableParsingService(parser=MagicMock(spec=TableParser))
        table_service.parser.extract_tables.return_value = [
            TableData(rows=[["H1", "H2"], ["R1C1", "R1C2"]], confidence=0.99)
        ]

        # Act
        tables: list[TableData] = await table_service.parse_tables_from_page(mock_pdf_page_with_table)

        # Assert
        assert len(tables) == 1
        table = tables[0]
        assert len(table.rows) == 2, "Should have 2 rows (header + data)"
        assert len(table.rows[0]) == 2, "Should have 2 columns"

    @pytest.mark.asyncio
    async def test_i2_03_ocr_fallback_engages_on_low_confidence(
        self, ocr_service: OCRProcessingService, mock_scanned_pdf_page: bytes
    ):
        """
        [TEST-I2-03] Verifies the fallback OCR is used when primary confidence is low.
        """
        # Arrange: Configure primary OCR to return a low-confidence result.
        ocr_service.primary_adapter.process_page.return_value = OCRResult(
            text="Garbled text", confidence=0.4, provider="primary-ocr"
        )

        # Act
        result: OCRResult = await ocr_service.process_page(mock_scanned_pdf_page)

        # Assert
        assert result.provider == "fallback-ocr", "Fallback provider should have been used."
        assert result.confidence > 0.7, "Result should be from the high-confidence fallback."
        ocr_service.primary_adapter.process_page.assert_called_once()
        ocr_service.fallback_adapter.process_page.assert_called_once()

    @pytest.mark.xfail(reason="[TDD] Drives implementation of merged cell normalization.", strict=True)
    @pytest.mark.asyncio
    async def test_i2_04_table_parser_handles_merged_cells(self):
        """
        [TEST-I2-04] Verifies the table parser does not collapse merged cells incorrectly.
        This test is expected to fail until the normalization logic is implemented.
        """
        # Arrange
        # A more sophisticated test would use a real PDF fixture and a real parser,
        # but for TDD, we can assert that a hypothetical 'normalize' method is called.
        mock_parser = MagicMock(spec=TableParser)
        mock_parser.normalize_merged_cells = MagicMock(
            side_effect=NotImplementedError("Merged cell logic not implemented")
        )
        table_service = TableParsingService(parser=mock_parser)

        # Act & Assert
        with pytest.raises(NotImplementedError):
             await table_service.parse_tables_from_page(b"pdf-with-merged-cells")

        # This test will pass once the `normalize_merged_cells` method is implemented
        # and no longer raises a NotImplementedError.
        assert False, "Remove this line once the above logic is implemented."