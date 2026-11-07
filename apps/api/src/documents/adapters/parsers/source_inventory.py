"""Source-unit visibility for PDF/DOCX parsing; never claims full extraction.

Independent inventory of what the parser *observed* and what it cannot verify.
Only counts, page labels, and machine-readable limitations leave this module.
No source text, filenames, metadata authors, or OCR errors are persisted.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZipFile

import fitz
from docx import Document as DocxDocument

from src.documents.adapters.parsers.pdf_file_parser import _is_low_quality_text_layer

_OBSERVED = "OBSERVED_ONLY"


def _unavailable() -> dict[str, Any]:
    return {
        "assurance": _OBSERVED,
        "inspection_available": False,
        "limitations": ["source_inventory_unavailable"],
    }


def inspect_pdf_source_inventory(
    path: Path, text_blocks: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compare parsed text blocks with actual PDF page inventory.

    A page with text does not prove that every glyph/table/image was recovered.
    OCR success means only that the OCR returned some characters.
    """
    try:
        with fitz.open(path) as doc:
            page_count = doc.page_count
            mapped = {
                block["page"]
                for block in text_blocks
                if isinstance(block, dict)
                and isinstance(block.get("page"), int)
                and not isinstance(block.get("page"), bool)
                and isinstance(block.get("text"), str)
                and block["text"].strip()
            }
            observed = sorted(page for page in mapped if 1 <= page <= page_count)
            missing = [page for page in range(1, page_count + 1) if page not in mapped]
            ocr_pages = sorted({
                block["page"]
                for block in text_blocks
                if isinstance(block, dict) and block.get("ocr") is True
                and isinstance(block.get("page"), int)
                and 1 <= block["page"] <= page_count
            })
            image_only = []
            unreadable_native = []
            for index in range(page_count):
                page_number = index + 1
                page = doc[index]
                if page_number not in mapped and page.get_images(full=True):
                    image_only.append(page_number)
                native_text = page.get_text("text")
                if (
                    native_text and _is_low_quality_text_layer(native_text)
                    and page_number not in ocr_pages
                ):
                    unreadable_native.append(page_number)
            limitations = []
            if missing:
                limitations.append("text_missing_on_source_pages")
            if image_only:
                limitations.append("image_pages_without_extracted_text")
            if unreadable_native:
                limitations.append("suspect_native_text_not_recovered_by_ocr")
            if mapped - set(observed):
                limitations.append("invalid_parser_page_labels")
            if any(
                not isinstance(block, dict)
                or not isinstance(block.get("page"), int)
                for block in text_blocks
            ):
                limitations.append("unlocated_parser_blocks")
            return {
                "assurance": _OBSERVED,
                "inspection_available": True,
                "source_pages": page_count,
                "pages_with_extracted_text": observed,
                "pages_without_extracted_text": missing,
                "pages_with_images_without_text": image_only,
                "pages_with_suspect_native_text": unreadable_native,
                "pages_using_ocr": ocr_pages,
                "text_block_count": len(text_blocks),
                "limitations": limitations,
            }
    except Exception:
        return _unavailable()


def inspect_docx_source_inventory(
    path: Path, text_blocks: list[dict[str, Any]]
) -> dict[str, Any]:
    """Inventory body elements and package regions outside the DOCX parser.

    Header/footer/footnote/etc. existence is a conservative coverage caveat,
    NOT proof that a legal obligation is present there.
    """
    try:
        document = DocxDocument(str(path))
        body_paragraphs = len(document.paragraphs)
        body_tables = len(document.tables)
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            other_regions = {
                "headers": sum(
                    name.startswith("word/header") and name.endswith(".xml")
                    for name in names
                ),
                "footers": sum(
                    name.startswith("word/footer") and name.endswith(".xml")
                    for name in names
                ),
                "footnotes": int("word/footnotes.xml" in names),
                "endnotes": int("word/endnotes.xml" in names),
                "comments": int("word/comments.xml" in names),
            }
            # This parser only visits body-level paragraphs/tables. Text
            # shapes and nested tables can contain source terms it misses.
            document_xml = archive.getinfo("word/document.xml")
            if document_xml.file_size > 16_000_000:
                return _unavailable()
            body_xml = archive.read("word/document.xml")
            has_textboxes = b"txbxContent" in body_xml
            # count explicit table starts (including nested tables)
            nested_table_hint = body_xml.count(b"<w:tbl>") > body_tables

        limitations: list[str] = []
        if other_regions["headers"] or other_regions["footers"]:
            limitations.append("header_or_footer_part_not_extracted")
        if other_regions["footnotes"] or other_regions["endnotes"]:
            limitations.append("notes_part_not_extracted")
        if other_regions["comments"]:
            limitations.append("comments_part_not_extracted")
        if has_textboxes:
            limitations.append("textbox_content_not_extracted")
        if nested_table_hint:
            limitations.append("nested_tables_not_verified")
        if (body_paragraphs or body_tables) and not text_blocks:
            limitations.append("body_content_not_observed")
        return {
            "assurance": _OBSERVED,
            "inspection_available": True,
            "body_paragraphs": body_paragraphs,
            "body_tables": body_tables,
            "text_block_count": len(text_blocks),
            "omitted_package_regions": other_regions,
            "contains_textboxes": has_textboxes,
            "nested_table_hint": nested_table_hint,
            "limitations": limitations,
        }
    except Exception:
        return _unavailable()
