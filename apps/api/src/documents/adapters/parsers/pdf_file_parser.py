"""
PDF Parser Adapter.

Refers to Suite ID: TS-UAD-DOC-002.

This adapter provides functionality to extract text and its positional offsets from PDF documents
using PyMuPDF (Fitz), with OCR fallback for scanned documents using Tesseract.
"""

import io
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import structlog

logger = structlog.get_logger()

# OCR imports - optional, will be None if not available. `pytesseract` and
# `Image` stay public module attributes: tests patch pdf_file_parser.Image.
pytesseract: Any = None
Image: Any = None
OCR_AVAILABLE = False

try:
    import pytesseract as _pytesseract_imported
    from PIL import Image as _PILImage_imported
    pytesseract = _pytesseract_imported
    Image = _PILImage_imported
    OCR_AVAILABLE = True
except ImportError:
    logger.warning("ocr_not_available", message="pytesseract/Pillow not installed, OCR disabled")


class PDFParsingError(Exception):
    """Custom exception for PDF parsing errors."""
    pass


class PDFFileParser:
    """
    Adapter class for parsing PDF files.
    Encapsulates the logic specific to the PDF format and `PyMuPDF` library.
    Includes OCR fallback for scanned/image-based PDFs.
    """

    def __init__(self, ocr_language: str = "spa+eng"):
        """
        Initialize PDF parser.

        Args:
            ocr_language: Tesseract language code(s) for OCR. Default is Spanish + English.
        """
        self.ocr_language = ocr_language

    async def extract_text_and_offsets(self, pdf_path: Path) -> list[dict[str, Any]]:
        """
        Extracts text blocks and their bounding box offsets from a PDF document.
        Falls back to OCR for pages with no extractable text.

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
        ocr_pages = 0

        try:
            document = fitz.open(pdf_path)
            total_pages = document.page_count

            for page_num in range(total_pages):
                page = document.load_page(page_num)
                page_text_blocks = self._extract_page_text_blocks(page, page_num)

                # If no text found and OCR is available, try OCR
                if not page_text_blocks and OCR_AVAILABLE:
                    ocr_text = self._ocr_page(page, page_num)
                    if ocr_text:
                        page_text_blocks = [{
                            "text": ocr_text,
                            "bbox": (0, 0, page.rect.width, page.rect.height),
                            "page": page_num + 1,
                            "ocr": True,
                        }]
                        ocr_pages += 1

                text_blocks.extend(page_text_blocks)

            document.close()

            if ocr_pages > 0:
                logger.info(
                    "pdf_ocr_applied",
                    file=str(pdf_path.name),
                    total_pages=total_pages,
                    ocr_pages=ocr_pages,
                )

        except Exception as e:
            raise PDFParsingError(f"Failed to parse PDF {pdf_path}: {e}")

        return text_blocks

    def _extract_page_text_blocks(self, page: fitz.Page, page_num: int) -> list[dict[str, Any]]:
        """Extract text blocks from a PDF page using PyMuPDF."""
        blocks = []
        data = page.get_text("dict")

        for block in data.get("blocks", []):
            if block["type"] == 0:  # Text block
                block_text = ""
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        block_text += span["text"]
                    block_text += " " if not block_text.endswith(" ") else ""

                if block_text.strip():
                    blocks.append({
                        "text": block_text.strip(),
                        "bbox": tuple(block["bbox"]),
                        "page": page_num + 1,
                    })

        return blocks

    def _ocr_page(self, page: fitz.Page, page_num: int) -> str | None:
        """Apply OCR to a PDF page to extract text from images."""
        if not OCR_AVAILABLE:
            return None
        if pytesseract is None:
            return None

        try:
            # Render page to image at 200 DPI for good OCR quality
            mat = fitz.Matrix(200 / 72, 200 / 72)  # 200 DPI
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))

            # Run OCR
            ocr_text: str = pytesseract.image_to_string(image, lang=self.ocr_language)

            # Clean up
            ocr_text = ocr_text.strip()
            if ocr_text:
                logger.debug("ocr_page_success", page=page_num + 1, chars=len(ocr_text))
                return ocr_text

        except Exception as e:
            logger.warning("ocr_page_failed", page=page_num + 1, error=str(e))

        return None
