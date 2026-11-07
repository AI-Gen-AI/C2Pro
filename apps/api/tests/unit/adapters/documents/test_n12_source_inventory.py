"""Observed source coverage is diagnostics, never automatic completeness."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest
from docx import Document

from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser
from src.documents.adapters.parsers.source_inventory import (
    inspect_docx_source_inventory,
    inspect_pdf_source_inventory,
)
from src.documents.domain.models import DocumentType


def _pdf(path: Path) -> None:
    with fitz.open() as pdf:
        page1 = pdf.new_page()
        page1.insert_text((72, 72), "EPC-05 The contractor shall deliver on time.")
        pdf.new_page()  # parsed PDF but no extractable words on this page
        pdf.save(path)


def test_pdf_inventory_counts_source_pages_and_empty_page_without_faking_complete(tmp_path):
    path = tmp_path / "contract.pdf"
    _pdf(path)
    inventory = inspect_pdf_source_inventory(path, [
        {"page": 1, "text": "EPC-05 The contractor shall deliver on time."},
    ])
    assert inventory["source_pages"] == 2
    assert inventory["pages_with_extracted_text"] == [1]
    assert inventory["pages_without_extracted_text"] == [2]
    assert "text_missing_on_source_pages" in inventory["limitations"]
    assert inventory["assurance"] == "OBSERVED_ONLY"
    assert "EPC-05" not in repr(inventory)


def test_pdf_inventory_fails_closed_if_file_cannot_be_inspected(tmp_path):
    inventory = inspect_pdf_source_inventory(tmp_path / "not-a-pdf.pdf", [])
    assert inventory["assurance"] == "OBSERVED_ONLY"
    assert "source_inventory_unavailable" in inventory["limitations"]


def test_docx_inventory_reports_header_not_in_body_extraction(tmp_path):
    path = tmp_path / "contract.docx"
    document = Document()
    document.add_paragraph("Clause 3 - Payment")
    document.sections[0].header.paragraphs[0].text = "Contract header obligation"
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "Clause 4 - Insurance"
    document.save(path)

    inventory = inspect_docx_source_inventory(path, [
        {"text": "Clause 3 - Payment"}, {"text": "Clause 4 - Insurance"}
    ])
    assert inventory["body_paragraphs"] >= 1
    assert inventory["body_tables"] == 1
    assert "header_or_footer_part_not_extracted" in inventory["limitations"]
    assert inventory["assurance"] == "OBSERVED_ONLY"
    assert "Insurance" not in repr(inventory)
    assert "Contract header obligation" not in repr(inventory)


@pytest.mark.asyncio
async def test_composite_pdf_coverage_contains_observations_but_remains_unverified(tmp_path):
    path = tmp_path / "source.pdf"
    _pdf(path)
    parser = CompositeFileParser.create()
    payload = await parser.parse_document_file(
        SimpleNamespace(file_format=".pdf", document_type=DocumentType.CONTRACT), path
    )
    coverage = payload["document_coverage"]
    assert coverage["status"] == "UNVERIFIED"
    assert coverage["origin"] == "pdf_file_parser"
    assert coverage["source_inventory"]["source_pages"] == 2
    assert coverage["source_inventory"]["pages_without_extracted_text"] == [2]
    assert "text_missing_on_source_pages" in coverage["limitations"]
    assert coverage.get("text_coverage_assurance") != "verified_full_source_text"


@pytest.mark.asyncio
async def test_composite_docx_reports_unextracted_header_and_remains_unverified(tmp_path):
    path = tmp_path / "source.docx"
    doc = Document()
    doc.add_paragraph("The employer shall pay.")
    doc.sections[0].header.paragraphs[0].text = "Insurance clause in header"
    doc.save(path)
    parser = CompositeFileParser.create()
    payload = await parser.parse_document_file(
        SimpleNamespace(file_format=".docx", document_type=DocumentType.CONTRACT), path
    )
    assert payload["document_coverage"]["status"] == "UNVERIFIED"
    assert "header_or_footer_part_not_extracted" in payload["document_coverage"]["limitations"]
    assert payload["document_coverage"]["source_inventory"]["assurance"] == "OBSERVED_ONLY"
