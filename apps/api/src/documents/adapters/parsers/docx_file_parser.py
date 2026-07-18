"""
DOCX Parser Adapter.

Refers to Suite ID: TS-UAD-DOC-002.

This adapter extracts text blocks from Microsoft Word .docx files.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from docx import Document as DocxDocument
from docx.opc.exceptions import PackageNotFoundError
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph


class DocxParsingError(Exception):
    """Custom exception for DOCX parsing errors."""


class DocxFileParser:
    """Adapter class for parsing DOCX files into text blocks."""

    async def extract_text_and_offsets(self, docx_path: Path) -> list[dict[str, Any]]:
        """
        Extract paragraphs and table cell text from a DOCX file in document order.

        DOCX does not expose stable page coordinates, so the return shape mirrors
        the PDF parser with bbox set to None and page defaulted to 1.
        """
        if not docx_path.exists():
            raise DocxParsingError(f"DOCX file not found: {docx_path}")
        if docx_path.suffix.lower() != ".docx":
            raise DocxParsingError(f"File is not a DOCX: {docx_path}")

        try:
            document = DocxDocument(str(docx_path))
        except PackageNotFoundError as exc:
            raise DocxParsingError(f"Failed to open DOCX {docx_path}: {exc}") from exc

        text_blocks: list[dict[str, Any]] = []
        for text in self._iter_text_in_document_order(document):
            cleaned = text.strip()
            if cleaned:
                text_blocks.append({"text": cleaned, "bbox": None, "page": 1})
        return text_blocks

    @classmethod
    def _iter_text_in_document_order(cls, document: Any) -> list[str]:
        texts: list[str] = []
        for block in cls._iter_block_items(document):
            if isinstance(block, Paragraph):
                texts.append(block.text)
            elif isinstance(block, Table):
                for row in block.rows:
                    for cell in row.cells:
                        texts.extend(paragraph.text for paragraph in cell.paragraphs)
        return texts

    @staticmethod
    def _iter_block_items(document: Any) -> Iterator[Paragraph | Table]:
        body = document.element.body
        for child in body.iterchildren():
            if isinstance(child, CT_P):
                yield Paragraph(child, document)
            elif isinstance(child, CT_Tbl):
                yield Table(child, document)
