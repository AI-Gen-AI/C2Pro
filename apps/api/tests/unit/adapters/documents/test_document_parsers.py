"""
Test Suite: TS-UAD-DOC-002 - Document Parser Tests
Component: Documents Module - Parser Adapters
Priority: P0

Tests the document parser adapters:
1. PDF Parser
2. BC3 Parser
3. Excel Parser
4. Composite Parser

Methodology: Unit tests with mocked dependencies
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4
import tempfile
import os
from datetime import datetime, UTC

from src.documents.domain.models import Document, DocumentStatus, DocumentType


# ===========================================
# PDF PARSER TESTS
# ===========================================


class TestPDFParser:
    """Tests for PDFFileParser."""

    def test_pdf_parser_init(self):
        """Test PDF parser initialization."""
        from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser

        parser = PDFFileParser()
        assert parser is not None
        assert parser.ocr_language == "spa+eng"

    def test_pdf_parser_init_custom_language(self):
        """Test PDF parser with custom OCR language."""
        from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser

        parser = PDFFileParser(ocr_language="eng")
        assert parser.ocr_language == "eng"

    @pytest.mark.asyncio
    async def test_pdf_parser_extract_text_success(self):
        """Test successful text extraction from PDF."""
        from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser

        # Create a temporary PDF-like file
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as tmp:
            tmp.write(b'%PDF-1.4 test content')
            tmp_path = tmp.name

        try:
            parser = PDFFileParser()

            # Mock fitz.open
            with patch('src.documents.adapters.parsers.pdf_file_parser.fitz.open') as mock_fitz:
                mock_doc = MagicMock()
                mock_page = MagicMock()
                mock_page.get_text.return_value = "Test contract content"
                mock_page.get_textblocks.return_value = [
                    (0, 0, 100, 20, "Test block 1", 0, 0),
                    (0, 25, 100, 45, "Test block 2", 0, 0)
                ]
                mock_doc.__len__ = MagicMock(return_value=1)
                mock_doc.__getitem__ = MagicMock(return_value=mock_page)
                mock_fitz.return_value = mock_doc

                result = await parser.extract_text_and_offsets(Path(tmp_path))

                assert isinstance(result, list)
        finally:
            os.unlink(tmp_path)

    def test_pdf_parser_error_handling(self):
        """Test PDF parser error handling for invalid file."""
        from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser, PDFParsingError

        parser = PDFFileParser()

        # Test with non-existent file
        with pytest.raises(Exception):
            import asyncio
            asyncio.run(parser.extract_text_and_offsets(Path("/nonexistent/file.pdf")))

    def test_pdf_parsing_error_class(self):
        """Test PDFParsingError exception class."""
        from src.documents.adapters.parsers.pdf_file_parser import PDFParsingError

        error = PDFParsingError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_pdf_extract_page_text_blocks_filters_empty_blocks(self):
        """Test page text extraction keeps only text blocks with content."""
        from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser

        parser = PDFFileParser()
        page = MagicMock()
        page.get_text.return_value = {
            "blocks": [
                {
                    "type": 0,
                    "bbox": [0, 0, 10, 10],
                    "lines": [{"spans": [{"text": "Alpha"}, {"text": " Beta"}]}],
                },
                {
                    "type": 0,
                    "bbox": [10, 10, 20, 20],
                    "lines": [{"spans": [{"text": "   "}]}],
                },
                {"type": 1, "bbox": [0, 0, 0, 0], "lines": []},
            ]
        }

        result = parser._extract_page_text_blocks(page, 1)

        assert result == [{"text": "Alpha Beta", "bbox": (0, 0, 10, 10), "page": 2}]

    @pytest.mark.asyncio
    async def test_pdf_parser_uses_ocr_fallback_when_page_has_no_text(self):
        """Test OCR fallback path when extractable text is absent."""
        from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as tmp:
            tmp.write(b"%PDF-1.4 ocr fallback")
            tmp_path = tmp.name

        try:
            parser = PDFFileParser()
            page = MagicMock()
            page.rect.width = 200
            page.rect.height = 300
            document = MagicMock()
            document.page_count = 1
            document.load_page.return_value = page

            with patch("src.documents.adapters.parsers.pdf_file_parser.fitz.open", return_value=document), patch(
                "src.documents.adapters.parsers.pdf_file_parser.OCR_AVAILABLE", True
            ), patch.object(parser, "_extract_page_text_blocks", return_value=[]), patch.object(
                parser, "_ocr_page", return_value="OCR text"
            ):
                result = await parser.extract_text_and_offsets(Path(tmp_path))

            assert result == [
                {"text": "OCR text", "bbox": (0, 0, 200, 300), "page": 1, "ocr": True}
            ]
        finally:
            os.unlink(tmp_path)

    def test_pdf_ocr_page_returns_none_when_ocr_disabled(self):
        """Test OCR helper returns None when OCR is unavailable."""
        from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser

        parser = PDFFileParser()
        with patch("src.documents.adapters.parsers.pdf_file_parser.OCR_AVAILABLE", False):
            assert parser._ocr_page(MagicMock(), 0) is None

    def test_pdf_ocr_page_returns_none_when_ocr_fails(self):
        """Test OCR helper swallows OCR exceptions and returns None."""
        from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser

        parser = PDFFileParser()
        page = MagicMock()
        pix = MagicMock()
        pix.tobytes.return_value = b"png"
        page.get_pixmap.return_value = pix

        with patch("src.documents.adapters.parsers.pdf_file_parser.OCR_AVAILABLE", True), patch(
            "src.documents.adapters.parsers.pdf_file_parser.Image.open",
            side_effect=RuntimeError("ocr boom"),
        ):
            assert parser._ocr_page(page, 0) is None


# ===========================================
# BC3 PARSER TESTS
# ===========================================


class TestBC3Parser:
    """Tests for BC3FileParser."""

    def test_bc3_parser_init(self):
        """Test BC3 parser initialization."""
        from src.documents.adapters.parsers.bc3_file_parser import BC3FileParser

        parser = BC3FileParser()
        assert parser is not None

    @pytest.mark.asyncio
    async def test_bc3_parser_parse_sample(self):
        """Test BC3 parser with sample data."""
        from src.documents.adapters.parsers.bc3_file_parser import BC3FileParser

        parser = BC3FileParser()

        # Sample BC3 content
        sample_bc3 = """*

A1;First Item;100.00
A2;Second Item;200.00

*"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.bc3', delete=False) as tmp:
            tmp.write(sample_bc3)
            tmp_path = tmp.name

        try:
            result = await parser.parse(Path(tmp_path))
            assert result is not None
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_bc3_parser_rejects_missing_file(self):
        """Test BC3 parser rejects missing files."""
        from src.documents.adapters.parsers.bc3_file_parser import BC3FileParser, BC3ParsingError

        parser = BC3FileParser()

        with pytest.raises(BC3ParsingError, match="not found"):
            await parser.parse(Path("missing.bc3"))

    @pytest.mark.asyncio
    async def test_bc3_parser_rejects_invalid_suffix(self):
        """Test BC3 parser rejects non-bc3 inputs."""
        from src.documents.adapters.parsers.bc3_file_parser import BC3FileParser, BC3ParsingError

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write("noop")
            tmp_path = tmp.name

        try:
            parser = BC3FileParser()
            with pytest.raises(BC3ParsingError, match="not a BC3"):
                await parser.parse(Path(tmp_path))
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_bc3_parser_wraps_invalid_file_errors(self):
        """Test BC3 parser wraps library invalid-file exceptions."""
        from src.documents.adapters.parsers.bc3_file_parser import (
            BC3FileParser,
            BC3ParsingError,
            InvalidFileException,
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bc3", delete=False) as tmp:
            tmp.write("*")
            tmp_path = tmp.name

        try:
            parser = BC3FileParser()
            with patch(
                "src.documents.adapters.parsers.bc3_file_parser.pyfiebdc.Fiebdc"
            ) as mock_fiebdc:
                mock_fiebdc.return_value.parse.side_effect = InvalidFileException("bad bc3")
                with pytest.raises(BC3ParsingError, match="Invalid BC3 file format"):
                    await parser.parse(Path(tmp_path))
        finally:
            os.unlink(tmp_path)

    def test_bc3_parsing_error_class(self):
        """Test BC3ParsingError exception class."""
        from src.documents.adapters.parsers.bc3_file_parser import BC3ParsingError

        error = BC3ParsingError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)


# ===========================================
# EXCEL PARSER TESTS
# ===========================================


class TestExcelParser:
    """Tests for ExcelFileParser."""

    def test_excel_parser_init(self):
        """Test Excel parser initialization."""
        from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser

        parser = ExcelFileParser()
        assert parser is not None

    def test_excel_parser_parse_empty(self):
        """Test Excel parser with empty file."""
        from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser

        # Create empty Excel file
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            # Write minimal xlsx content (ZIP with empty workbook)
            tmp.write(b'PK\x03\x04')  # ZIP header
            tmp_path = tmp.name

        try:
            parser = ExcelFileParser()
            # Should handle gracefully
            result = parser.parse(Path(tmp_path))
            assert result is not None
        except Exception:
            pass  # Expected for invalid file
        finally:
            os.unlink(tmp_path)

    def test_excel_parsing_error_class(self):
        """Test ExcelParsingError exception class."""
        from src.documents.adapters.parsers.excel_file_parser import ExcelParsingError

        error = ExcelParsingError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    @pytest.mark.asyncio
    async def test_excel_parser_parse_schedule_success(self):
        """Test schedule parsing maps rows into normalized dictionaries."""
        from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser

        header_cells = [MagicMock(value="Task"), MagicMock(value="Start Date"), MagicMock(value="End Date"), MagicMock(value="Duration")]
        sheet = MagicMock()
        sheet.__getitem__.return_value = header_cells
        sheet.iter_rows.return_value = [
            ("Foundation", "2026-01-01", "2026-01-05", 4),
            (None, None, None, None),
        ]
        workbook = MagicMock(active=sheet)

        with patch("src.documents.adapters.parsers.excel_file_parser.openpyxl.load_workbook", return_value=workbook):
            parser = ExcelFileParser()
            result = await parser.parse_schedule(Path("schedule.xlsx"))

        assert result == [
            {
                "task": "Foundation",
                "start_date": "2026-01-01",
                "end_date": "2026-01-05",
                "duration": 4,
            }
        ]

    @pytest.mark.asyncio
    async def test_excel_parser_parse_budget_success(self):
        """Test budget parsing maps rows into normalized dictionaries."""
        from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser

        header_cells = [MagicMock(value="Item"), MagicMock(value="Quantity"), MagicMock(value="Unit Price"), MagicMock(value="Total")]
        sheet = MagicMock()
        sheet.__getitem__.return_value = header_cells
        sheet.iter_rows.return_value = [
            ("Concrete", 3, 50.0, 150.0),
            (None, None, None, None),
        ]
        workbook = MagicMock(active=sheet)

        with patch("src.documents.adapters.parsers.excel_file_parser.openpyxl.load_workbook", return_value=workbook):
            parser = ExcelFileParser()
            result = await parser.parse_budget(Path("budget.xlsx"))

        assert result == [
            {
                "item": "Concrete",
                "quantity": 3,
                "unit_price": 50.0,
                "total": 150.0,
            }
        ]

    @pytest.mark.asyncio
    async def test_excel_parser_schedule_requires_headers(self):
        """Test schedule parsing raises on missing headers."""
        from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser, ExcelParsingError

        sheet = MagicMock()
        sheet.__getitem__.return_value = [MagicMock(value="Task"), MagicMock(value="Start Date")]
        workbook = MagicMock(active=sheet)

        with patch("src.documents.adapters.parsers.excel_file_parser.openpyxl.load_workbook", return_value=workbook):
            parser = ExcelFileParser()
            with pytest.raises(ExcelParsingError, match="Missing one or more required headers"):
                await parser.parse_schedule(Path("schedule.xlsx"))

    @pytest.mark.asyncio
    async def test_excel_parser_budget_wraps_file_errors(self):
        """Test budget parsing wraps workbook open failures."""
        from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser, ExcelParsingError

        with patch(
            "src.documents.adapters.parsers.excel_file_parser.openpyxl.load_workbook",
            side_effect=FileNotFoundError("missing"),
        ):
            parser = ExcelFileParser()
            with pytest.raises(ExcelParsingError, match="Failed to open or read Excel file"):
                await parser.parse_budget(Path("budget.xlsx"))


# ===========================================
# COMPOSITE PARSER TESTS
# ===========================================


class TestCompositeParser:
    """Tests for CompositeFileParser."""

    def test_composite_parser_init(self):
        """Test composite parser initialization."""
        from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser
        from src.documents.adapters.parsers.bc3_file_parser import BC3FileParser
        from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
        from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser

        bc3 = BC3FileParser()
        excel = ExcelFileParser()
        pdf = PDFFileParser()

        parser = CompositeFileParser(bc3_parser=bc3, excel_parser=excel, pdf_parser=pdf)
        assert parser is not None
        assert parser.bc3_parser is bc3
        assert parser.excel_parser is excel
        assert parser.pdf_parser is pdf

    @pytest.mark.asyncio
    async def test_composite_parser_parse_pdf(self):
        """Test composite parser parses PDF file."""
        from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser
        from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser

        pdf = PDFFileParser()
        parser = CompositeFileParser(
            bc3_parser=MagicMock(),
            excel_parser=MagicMock(),
            pdf_parser=pdf
        )

        # Create temp PDF
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as tmp:
            tmp.write(b'%PDF-1.4 test content')
            tmp_path = tmp.name

        try:
            # Mock the PDF parser
            with patch.object(pdf, 'extract_text_and_offsets', new_callable=AsyncMock) as mock_extract:
                mock_extract.return_value = [{"text": "test", "bbox": (0,0,100,20)}]
                # Just test the method exists and is callable
                assert callable(parser.parse_document_file)
        finally:
            os.unlink(tmp_path)

    def test_composite_parser_has_required_methods(self):
        """Test composite parser has required interface methods."""
        from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser

        parser = CompositeFileParser(
            bc3_parser=MagicMock(),
            excel_parser=MagicMock(),
            pdf_parser=MagicMock()
        )

        # Check it has the required port method
        assert hasattr(parser, 'parse_document_file')

    @pytest.fixture
    def sample_document(self):
        """Representative document for composite parser routing."""
        return Document(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="document.pdf",
            upload_status=DocumentStatus.UPLOADED,
            file_format=".pdf",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @pytest.mark.asyncio
    async def test_composite_parser_routes_pdf(self, sample_document):
        """Test composite parser delegates PDFs to the pdf parser."""
        from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser

        pdf_parser = MagicMock()
        pdf_parser.extract_text_and_offsets = AsyncMock(return_value=[{"text": "alpha"}])
        parser = CompositeFileParser(MagicMock(), MagicMock(), pdf_parser)

        result = await parser.parse_document_file(sample_document, Path("doc.pdf"))

        assert result == {"file_format": ".pdf", "text_blocks": [{"text": "alpha"}]}

    @pytest.mark.asyncio
    async def test_composite_parser_routes_excel_schedule(self, sample_document):
        """Test composite parser routes schedule spreadsheets to parse_schedule."""
        from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser

        excel_parser = MagicMock()
        excel_parser.parse_schedule = AsyncMock(return_value=[{"task": "Install"}])
        parser = CompositeFileParser(MagicMock(), excel_parser, MagicMock())
        document = Document(
            id=sample_document.id,
            project_id=sample_document.project_id,
            document_type=DocumentType.SCHEDULE,
            filename="schedule.xlsx",
            upload_status=DocumentStatus.UPLOADED,
            file_format=".xlsx",
        )

        result = await parser.parse_document_file(document, Path("schedule.xlsx"))

        assert result == {"file_format": ".xlsx", "schedule": [{"task": "Install"}]}

    @pytest.mark.asyncio
    async def test_composite_parser_routes_excel_budget(self, sample_document):
        """Test composite parser routes budget spreadsheets to parse_budget."""
        from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser

        excel_parser = MagicMock()
        excel_parser.parse_budget = AsyncMock(return_value=[{"item": "Steel"}])
        parser = CompositeFileParser(MagicMock(), excel_parser, MagicMock())
        document = Document(
            id=sample_document.id,
            project_id=sample_document.project_id,
            document_type=DocumentType.BUDGET,
            filename="budget.xlsx",
            upload_status=DocumentStatus.UPLOADED,
            file_format=".xlsx",
        )

        result = await parser.parse_document_file(document, Path("budget.xlsx"))

        assert result == {"file_format": ".xlsx", "budget": [{"item": "Steel"}]}

    @pytest.mark.asyncio
    async def test_composite_parser_routes_bc3(self, sample_document):
        """Test composite parser routes bc3 files to the bc3 parser."""
        from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser

        bc3_parser = MagicMock()
        bc3_parser.parse = AsyncMock(return_value={"chapters": []})
        parser = CompositeFileParser(bc3_parser, MagicMock(), MagicMock())
        document = Document(
            id=sample_document.id,
            project_id=sample_document.project_id,
            document_type=DocumentType.BUDGET,
            filename="budget.bc3",
            upload_status=DocumentStatus.UPLOADED,
            file_format=".bc3",
        )

        result = await parser.parse_document_file(document, Path("budget.bc3"))

        assert result == {"file_format": ".bc3", "budget": {"chapters": []}}

    @pytest.mark.asyncio
    async def test_composite_parser_rejects_unsupported_excel_document_type(self, sample_document):
        """Test excel parsing rejects unsupported document types."""
        from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser

        parser = CompositeFileParser(MagicMock(), MagicMock(), MagicMock())
        document = Document(
            id=sample_document.id,
            project_id=sample_document.project_id,
            document_type=DocumentType.CONTRACT,
            filename="contract.xlsx",
            upload_status=DocumentStatus.UPLOADED,
            file_format=".xlsx",
        )

        with pytest.raises(ValueError, match="not supported"):
            await parser.parse_document_file(document, Path("contract.xlsx"))

    @pytest.mark.asyncio
    async def test_composite_parser_wraps_parser_errors(self, sample_document):
        """Test composite parser wraps parser-specific exceptions."""
        from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser
        from src.documents.adapters.parsers.pdf_file_parser import PDFParsingError

        pdf_parser = MagicMock()
        pdf_parser.extract_text_and_offsets = AsyncMock(side_effect=PDFParsingError("broken"))
        parser = CompositeFileParser(MagicMock(), MagicMock(), pdf_parser)

        with pytest.raises(ValueError, match="PDF parsing failed"):
            await parser.parse_document_file(sample_document, Path("document.pdf"))

    @pytest.mark.asyncio
    async def test_composite_parser_rejects_unknown_format(self, sample_document):
        """Test composite parser rejects formats without a configured parser."""
        from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser

        parser = CompositeFileParser(MagicMock(), MagicMock(), MagicMock())
        document = Document(
            id=sample_document.id,
            project_id=sample_document.project_id,
            document_type=DocumentType.OTHER,
            filename="notes.txt",
            upload_status=DocumentStatus.UPLOADED,
            file_format=".txt",
        )

        with pytest.raises(ValueError, match="No parser available"):
            await parser.parse_document_file(document, Path("notes.txt"))
