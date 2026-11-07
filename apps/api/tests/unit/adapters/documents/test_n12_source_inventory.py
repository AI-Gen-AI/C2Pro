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


@pytest.mark.asyncio
async def test_pdf_ocr_unavailable_is_distinguished_from_failed(tmp_path, monkeypatch):
    from src.documents.adapters.parsers import pdf_file_parser
    path = tmp_path / "blank-scanned.pdf"
    with fitz.open() as doc:
        doc.new_page()
        doc.save(path)
    monkeypatch.setattr(pdf_file_parser, "OCR_AVAILABLE", False)
    payload = await CompositeFileParser.create().parse_document_file(
        SimpleNamespace(file_format=".pdf", document_type=DocumentType.CONTRACT), path
    )
    inventory = payload["document_coverage"]["source_inventory"]
    assert inventory["pages_ocr_unavailable"] == [1]
    assert inventory["pages_ocr_failed"] == []
    assert inventory["pages_ocr_empty_result"] == []
    assert "ocr_unavailable_for_candidate_pages" in inventory["limitations"]
    assert payload["document_coverage"]["status"] == "UNVERIFIED"


@pytest.mark.asyncio
async def test_pdf_ocr_processing_exception_does_not_leak_exception_text(tmp_path, monkeypatch):
    from src.documents.adapters.parsers import pdf_file_parser
    path = tmp_path / "blank-scanned.pdf"
    with fitz.open() as doc:
        doc.new_page()
        doc.save(path)

    def broken_open(_):
        raise RuntimeError("CONFIDENTIAL EXCEPTION PAYLOAD")

    monkeypatch.setattr(pdf_file_parser, "OCR_AVAILABLE", True)
    monkeypatch.setattr(pdf_file_parser.Image, "open", broken_open)
    payload = await CompositeFileParser.create().parse_document_file(
        SimpleNamespace(file_format=".pdf", document_type=DocumentType.CONTRACT), path
    )
    inventory = payload["document_coverage"]["source_inventory"]
    assert inventory["pages_ocr_failed"] == [1]
    assert inventory["pages_ocr_unavailable"] == []
    assert "ocr_processing_failed" in inventory["limitations"]
    assert "CONFIDENTIAL" not in repr(inventory)


@pytest.mark.asyncio
async def test_pdf_ocr_empty_result_is_not_reported_as_processing_failure(tmp_path, monkeypatch):
    from src.documents.adapters.parsers import pdf_file_parser
    path = tmp_path / "blank-scanned.pdf"
    with fitz.open() as doc:
        doc.new_page()
        doc.save(path)
    monkeypatch.setattr(pdf_file_parser, "OCR_AVAILABLE", True)
    monkeypatch.setattr(pdf_file_parser.pytesseract, "image_to_string", lambda *a, **k: "  ")
    inventory = (
        await CompositeFileParser.create().parse_document_file(
            SimpleNamespace(file_format=".pdf", document_type=DocumentType.CONTRACT), path
        )
    )["document_coverage"]["source_inventory"]
    assert inventory["pages_ocr_empty_result"] == [1]
    assert inventory["pages_ocr_failed"] == []
    assert "ocr_returned_no_text" in inventory["limitations"]


def test_docx_nested_table_observation_uses_xml_elements_not_literal_tag(tmp_path):
    path = tmp_path / "nested.docx"
    document = Document()
    parent = document.add_table(rows=1, cols=1)
    parent.cell(0, 0).text = "Parent"
    nested = parent.cell(0, 0).add_table(rows=1, cols=1)
    nested.cell(0, 0).text = "Nested terms"
    document.save(path)
    inventory = inspect_docx_source_inventory(path, [{"text": "Parent"}])
    assert inventory["body_tables"] == 1
    assert inventory["nested_table_hint"] is True
    assert inventory["all_body_table_elements"] >= 2
    assert "nested_tables_not_verified" in inventory["limitations"]
    assert "Nested terms" not in repr(inventory)


def test_docx_textbox_marked_when_element_has_attributes(tmp_path):
    from docx.oxml import OxmlElement
    path = tmp_path / "textbox.docx"
    document = Document()
    paragraph = document.add_paragraph("Plain text")
    inline = OxmlElement("w:txbxContent")
    inline.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    paragraph._p.append(inline)
    document.save(path)
    inventory = inspect_docx_source_inventory(path, [{"text": "Plain text"}])
    assert inventory["contains_textboxes"] is True
    assert "textbox_content_not_extracted" in inventory["limitations"]
