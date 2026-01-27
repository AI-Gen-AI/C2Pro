"""
PDF Parser Adapter.

This adapter provides functionality to extract text and its positional offsets from PDF documents
using PyMuPDF (Fitz), encapsulating external library details.
"""

from pathlib import Path
from typing import Any, List

import fitz  # PyMuPDF


class PDFParsingError(Exception):
    """Custom exception for PDF parsing errors."""
    pass


class PDFFileParser:
    """
    Adapter class for parsing PDF files.
    Encapsulates the logic specific to the PDF format and `PyMuPDF` library.
    """
    async def extract_text_and_offsets(self, pdf_path: Path) -> list[dict[str, Any]]:
        """
        Extracts text blocks and their bounding box offsets from a PDF document.

        Args:
            pdf_path: The path to the PDF file.

        Returns:
            A list of dictionaries, where each dictionary represents a text block
            with its 'text' content and 'bbox' (bounding box) information.
            The bbox is a tuple (x0, y0, x1, y1).

        Raises:
            PDFParsingError: If the PDF file cannot be opened or processed.
        """
        if not pdf_path.exists():
            raise PDFParsingError(f"PDF file not found: {pdf_path}")
        if not pdf_path.suffix.lower() == ".pdf":
            raise PDFParsingError(f"File is not a PDF: {pdf_path}")

        text_blocks = []
        try:
            document = fitz.open(pdf_path)
            for page_num in range(document.page_count):
                page = document.load_page(page_num)
                data = page.get_text("dict")
                for block in data.get("blocks", []):
                    if block["type"] == 0:  # Text block
                        block_text = ""
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                block_text += span["text"]
                            block_text += " " if not block_text.endswith(" ") else ""

                        if block_text.strip():
                            text_blocks.append(
                                {
                                    "text": block_text.strip(),
                                    "bbox": tuple(block["bbox"]),
                                    "page": page_num + 1,
                                }
                            )
            document.close()
        except Exception as e:
            raise PDFParsingError(f"Failed to parse PDF {pdf_path}: {e}")

        return text_blocks
