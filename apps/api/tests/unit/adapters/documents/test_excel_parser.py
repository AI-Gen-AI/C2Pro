"""
Test Suite: Excel Parser Additional Tests
Component: Documents Module - Excel Parser Adapter
Priority: P0

Additional tests to improve Excel parser coverage.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from openpyxl import Workbook


class TestExcelParserSchedule:
    """Tests for ExcelFileParser.parse_schedule method."""

    @pytest.mark.asyncio
    async def test_parse_schedule_success(self):
        """Test successful schedule parsing."""
        from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser

        parser = ExcelFileParser()

        # Create mock workbook
        mock_workbook = MagicMock()
        mock_sheet = MagicMock()
        mock_sheet.__getitem__ = MagicMock(side_effect=[
            [MagicMock(value="Task"), MagicMock(value="Start Date"), MagicMock(value="End Date"), MagicMock(value="Duration")],
            [MagicMock(value="Task 1"), MagicMock(value="2024-01-01"), MagicMock(value="2024-01-31"), MagicMock(value=30)],
            [MagicMock(value="Task 2"), MagicMock(value="2024-02-01"), MagicMock(value="2024-02-28"), MagicMock(value=27)],
        ])
        mock_sheet.iter_rows = MagicMock(return_value=[
            ["Task 1", "2024-01-01", "2024-01-31", 30],
            ["Task 2", "2024-02-01", "2024-02-28", 27],
        ])
        mock_workbook.active = mock_sheet

        with patch('src.documents.adapters.parsers.excel_file_parser.openpyxl.load_workbook', return_value=mock_workbook):
            # Create temp file path (not actual file)
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
                tmp_path = tmp.name

            try:
                result = await parser.parse_schedule(Path(tmp_path))
                assert isinstance(result, list)
            finally:
                os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_parse_schedule_missing_headers(self):
        """Test schedule parsing with missing required headers."""
        from src.documents.adapters.parsers.excel_file_parser import (
            ExcelFileParser,
            ExcelParsingError,
        )

        parser = ExcelFileParser()

        mock_workbook = MagicMock()
        mock_sheet = MagicMock()
        mock_sheet.__getitem__ = MagicMock(side_effect=[
            [MagicMock(value="Task"), MagicMock(value="Wrong")],  # Missing Start Date, End Date
        ])
        mock_workbook.active = mock_sheet

        with patch('src.documents.adapters.parsers.excel_file_parser.openpyxl.load_workbook', return_value=mock_workbook):
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
                tmp_path = tmp.name

            try:
                with pytest.raises(ExcelParsingError) as exc_info:
                    await parser.parse_schedule(Path(tmp_path))
                assert "Missing one or more required headers" in str(exc_info.value)
            finally:
                os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_parse_schedule_invalid_file(self):
        """Test schedule parsing with invalid file."""
        from src.documents.adapters.parsers.excel_file_parser import (
            ExcelFileParser,
            ExcelParsingError,
        )

        parser = ExcelFileParser()

        with patch('src.documents.adapters.parsers.excel_file_parser.openpyxl.load_workbook', side_effect=FileNotFoundError("File not found")):
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
                tmp_path = tmp.name

            try:
                with pytest.raises(ExcelParsingError):
                    await parser.parse_schedule(Path(tmp_path))
            finally:
                os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_parse_schedule_discovers_spanish_header_row_after_title_block(self):
        """TS-UD-DOC-XLS-001: realistic Spanish schedules parse after title rows."""
        from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser

        parser = ExcelFileParser()
        workbook = Workbook()
        sheet = workbook.active
        sheet["A1"] = "1. CRONOGRAMA DETALLADO"
        sheet.append([])
        sheet.append([])
        sheet.append(["ID", "WBS", "Actividad", "Duración (días)", "Inicio", "Fin", "Predecesoras"])
        sheet.append(["1.1", None, "Firma del contrato", 1, "2024-01-01", "2024-01-01", "–"])

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name
        workbook.save(tmp_path)
        workbook.close()

        result = await parser.parse_schedule(Path(tmp_path))

        assert result == [
            {
                "task": "Firma del contrato",
                "start_date": "2024-01-01",
                "end_date": "2024-01-01",
                "duration": 1,
                "wbs": None,
                "predecessors": "–",
            }
        ]


class TestExcelParserBudget:
    """Tests for ExcelFileParser.parse_budget method."""

    @pytest.mark.asyncio
    async def test_parse_budget_success(self):
        """Test successful budget parsing."""
        from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser

        parser = ExcelFileParser()

        mock_workbook = MagicMock()
        mock_sheet = MagicMock()
        # Header row
        header_cells = [MagicMock(value="Item"), MagicMock(value="Quantity"), MagicMock(value="Unit Price"), MagicMock(value="Total")]
        mock_sheet.__getitem__ = MagicMock(return_value=header_cells)
        mock_sheet.iter_rows = MagicMock(return_value=[
            ["Item 1", 10, 100, 1000],
            ["Item 2", 5, 200, 1000],
        ])
        mock_workbook.active = mock_sheet

        with patch('src.documents.adapters.parsers.excel_file_parser.openpyxl.load_workbook', return_value=mock_workbook):
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
                tmp_path = tmp.name

            try:
                result = await parser.parse_budget(Path(tmp_path))
                assert isinstance(result, list)
            finally:
                os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_parse_budget_missing_headers(self):
        """Test budget parsing with missing required headers."""
        from src.documents.adapters.parsers.excel_file_parser import (
            ExcelFileParser,
            ExcelParsingError,
        )

        parser = ExcelFileParser()

        mock_workbook = MagicMock()
        mock_sheet = MagicMock()
        mock_sheet.__getitem__ = MagicMock(side_effect=[
            [MagicMock(value="Item")],  # Missing Quantity, Unit Price, Total
        ])
        mock_workbook.active = mock_sheet

        with patch('src.documents.adapters.parsers.excel_file_parser.openpyxl.load_workbook', return_value=mock_workbook):
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
                tmp_path = tmp.name

            try:
                with pytest.raises(ExcelParsingError) as exc_info:
                    await parser.parse_budget(Path(tmp_path))
                assert "Missing one or more required headers" in str(exc_info.value)
            finally:
                os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_parse_budget_invalid_file(self):
        """Test budget parsing with invalid file."""
        from src.documents.adapters.parsers.excel_file_parser import (
            ExcelFileParser,
            ExcelParsingError,
        )

        parser = ExcelFileParser()

        with patch('src.documents.adapters.parsers.excel_file_parser.openpyxl.load_workbook', side_effect=FileNotFoundError("File not found")):
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
                tmp_path = tmp.name

            try:
                with pytest.raises(ExcelParsingError):
                    await parser.parse_budget(Path(tmp_path))
            finally:
                os.unlink(tmp_path)


class TestExcelParserEdgeCases:
    """Edge case tests for ExcelFileParser."""

    @pytest.mark.asyncio
    async def test_parse_schedule_empty_rows(self):
        """Test schedule parsing with empty rows."""
        from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser

        parser = ExcelFileParser()

        mock_workbook = MagicMock()
        mock_sheet = MagicMock()
        header_cells = [MagicMock(value="Task"), MagicMock(value="Start Date"), MagicMock(value="End Date"), MagicMock(value="Duration")]
        mock_sheet.__getitem__ = MagicMock(return_value=header_cells)
        mock_sheet.iter_rows = MagicMock(return_value=[
            ["Task 1", "2024-01-01", "2024-01-31", 30],
            [None, None, None, None],  # Empty row
            ["Task 2", "2024-02-01", "2024-02-28", 27],
        ])
        mock_workbook.active = mock_sheet

        with patch('src.documents.adapters.parsers.excel_file_parser.openpyxl.load_workbook', return_value=mock_workbook):
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
                tmp_path = tmp.name

            try:
                result = await parser.parse_schedule(Path(tmp_path))
                # Empty rows should be filtered out
                assert len(result) == 2
            finally:
                os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_parse_budget_empty_rows(self):
        """Test budget parsing with empty rows."""
        from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser

        parser = ExcelFileParser()

        mock_workbook = MagicMock()
        mock_sheet = MagicMock()
        header_cells = [MagicMock(value="Item"), MagicMock(value="Quantity"), MagicMock(value="Unit Price"), MagicMock(value="Total")]
        mock_sheet.__getitem__ = MagicMock(return_value=header_cells)
        mock_sheet.iter_rows = MagicMock(return_value=[
            ["Item 1", 10, 100, 1000],
            [None, None, None, None],  # Empty row
            ["Item 2", 5, 200, 1000],
        ])
        mock_workbook.active = mock_sheet

        with patch('src.documents.adapters.parsers.excel_file_parser.openpyxl.load_workbook', return_value=mock_workbook):
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
                tmp_path = tmp.name

            try:
                result = await parser.parse_budget(Path(tmp_path))
                # Empty rows should be filtered out
                assert len(result) == 2
            finally:
                os.unlink(tmp_path)
