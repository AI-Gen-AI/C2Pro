from __future__ import annotations

from pathlib import Path

import pytest

import openpyxl

from src.modules.projects.schemas import BOMItemBase
from src.services.ingestion.bc3_parser import Bc3ParserService
from src.services.ingestion.excel_parser import ExcelBudgetParser
from src.services.ingestion.pdf_parser import PdfParserService


def _read_fixture_bytes(path: Path) -> bytes:
    if not path.exists():
        pytest.skip(
            "Missing fixture file. See tests/integration/conftest.py for required filenames."
        )
    return path.read_bytes()


def test_pdf_parser_extracts_text_and_tables(sample_files_path: Path) -> None:
    pdf_path = sample_files_path / "valid_contract.pdf"
    file_bytes = _read_fixture_bytes(pdf_path)

    parser = PdfParserService()
    parsed = parser.extract_text(file_bytes, filename=pdf_path.name)

    assert isinstance(parsed, dict)
    assert parsed.get("full_text")
    assert "CLÁUSULA PRIMERA" in parsed["full_text"]
    assert parsed.get("page_count", 0) > 0
    assert isinstance(parsed.get("tables_data"), list)
    assert len(parsed["tables_data"]) >= 1


def test_excel_parser_detects_header_and_parses_items(sample_files_path: Path) -> None:
    xlsx_path = sample_files_path / "complex_budget.xlsx"
    file_bytes = _read_fixture_bytes(xlsx_path)

    parser = ExcelBudgetParser()
    workbook = openpyxl.load_workbook(
        filename=Path(xlsx_path), read_only=True, data_only=True
    )
    sheet = workbook[workbook.sheetnames[0]]
    header_info = parser._find_header_row(sheet)  # pylint: disable=protected-access
    workbook.close()
    assert header_info is not None
    header_row_index, _ = header_info
    assert header_row_index > 1

    result = parser.parse_budget(file_bytes)
    items = result["items"]

    assert len(items) > 5
    assert isinstance(items[0], BOMItemBase)
    assert isinstance(items[0].unit_price, (int, float))


def test_bc3_parser_handles_legacy_encoding(sample_files_path: Path) -> None:
    bc3_path = sample_files_path / "legacy.bc3"
    file_bytes = _read_fixture_bytes(bc3_path)

    parser = Bc3ParserService()
    items = parser.parse_bc3(file_bytes, filename=bc3_path.name)

    assert len(items) > 0
    assert all(isinstance(item, BOMItemBase) for item in items)
    assert any(
        "Hormigón" in (item.item_name or "") or "Hormigón" in (item.description or "")
        for item in items
    )
