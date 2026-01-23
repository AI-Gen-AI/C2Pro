"""
C2Pro - PDF Parser Module

This module provides functionality to extract text and its positional offsets from PDF documents
using PyMuPDF (Fitz).
"""

from pathlib import Path
from typing import Any

import fitz  # PyMuPDF


class PDFParsingError(Exception):
    """Custom exception for PDF parsing errors."""

    pass


def extract_text_and_offsets(pdf_path: Path) -> list[dict[str, Any]]:
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
            # 'get_text("dict")' provides a detailed structure including blocks, lines, spans
            # 'get_text("words")' provides words and their bounding boxes
            # We'll use get_text("dict") for richer info and iterate through its blocks

            # Using get_text("dict") and then processing blocks
            data = page.get_text("dict")
            for block in data.get("blocks", []):
                if block["type"] == 0:  # Text block
                    block_text = ""
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            block_text += span["text"]
                        # Add a space or newline between lines, depending on desired output
                        block_text += " " if not block_text.endswith(" ") else ""

                    if block_text.strip():
                        # The bbox is usually (x0, y0, x1, y1)
                        # We use the bbox of the block for the overall block position
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


# Example Usage (for testing purposes, if run directly)
if __name__ == "__main__":
    # Placeholder for actual PDF files
    # In a real scenario, you would have 10 actual PDF files for testing.
    # For now, we simulate success or failure based on a dummy path.
    dummy_pdf_paths = [Path(f"tests/data/sample_doc_{i}.pdf") for i in range(1, 11)]

    print("--- Simulating PDF Parsing Tests ---")
    for _i, pdf_path in enumerate(dummy_pdf_paths):
        print(f"\nProcessing {pdf_path.name}...")
        try:
            # Create a dummy PDF file for testing (not a real PDF, just to avoid file not found)
            # In CI/CD, these would be actual files.
            with open(pdf_path, "w") as f:
                f.write(
                    f"%PDF-1.4\n1 0 obj <</Type/Catalog/Pages 2 0 R>> endobj 2 0 obj <</Type/Pages/Count 1/Kids[3 0 R]>> endobj 3 0 obj <</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>> endobj 4 0 obj <</Length 35>>stream BT /F1 24 Tf 100 700 Td ({pdf_path.name} - Test Content) Tj ET endstream endobj xref 0 5 0000000000 65535 f 0000000009 00000 n 0000000074 00000 n 0000000139 00000 n 0000000287 00000 n trailer <</Size 5/Root 1 0 R>> startxref 373 %%EOF"
                )

            extracted_data = extract_text_and_offsets(pdf_path)
            if extracted_data:
                print(f"  SUCCESS: Extracted {len(extracted_data)} text blocks.")
                for block in extracted_data[:2]:  # Print first 2 blocks for brevity
                    print(
                        f"    Page {block['page']}, BBox: {block['bbox']}, Text: '{block['text'][:50]}...'"
                    )
            else:
                print("  WARNING: No text blocks extracted.")
        except PDFParsingError as e:
            print(f"  ERROR: {e}")
        except Exception as e:
            print(f"  UNEXPECTED ERROR: {e}")
        finally:
            # Clean up dummy file
            if pdf_path.exists():
                pdf_path.unlink()
