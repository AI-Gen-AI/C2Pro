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


def _tesseract_binary_available() -> bool:
    """Probe whether the `tesseract` *system* binary is actually runnable.

    `pytesseract` is a thin wrapper around that binary — importing the
    Python package succeeding does not mean OCR will work. Without this
    probe, a missing binary is only discovered per-page, deep inside
    `_ocr_page`'s broad except-and-swallow, and scanned PDFs would silently
    yield empty text with no operator-visible signal of why. Extracted as
    its own function (rather than inline at import time) so it stays unit
    testable without reloading this module — reloading would rebind
    `PDFParsingError` to a new class object and break `except`/`isinstance`
    checks in modules that imported the pre-reload class (e.g.
    composite_file_parser.py).
    """
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception as exc:
        logger.warning(
            "ocr_tesseract_binary_missing",
            message=(
                "pytesseract is installed but the 'tesseract' system binary "
                "was not found (or failed to run). OCR is disabled — scanned "
                "PDFs will yield no text for image-only pages. Install the "
                "tesseract-ocr system package (see Dockerfile) to fix."
            ),
            error=str(exc),
        )
        return False


if OCR_AVAILABLE:
    OCR_AVAILABLE = _tesseract_binary_available()


# A scanned PDF can carry a NON-EMPTY but corrupt embedded text layer: a broken
# ToUnicode CMap yields U+FFFD replacement chars, and per-glyph positioning makes
# PyMuPDF emit mostly single-character tokens (e.g. "P a r t e s c o n t r a t").
# Such a layer must be re-OCR'd — otherwise every downstream step (clause
# extraction, coherence) runs on garbage. The previous code only OCR'd pages with
# NO text at all, so these corrupt-but-present layers slipped straight through.
_REPLACEMENT_CHAR = "�"


def _is_low_quality_text_layer(text: str) -> bool:
    """Heuristic: True when an extracted text layer looks corrupt and should be OCR'd."""
    stripped = text.strip()
    if len(stripped) < 40:
        # Too little to judge; the empty-page branch already handles the no-text case.
        return False
    if text.count(_REPLACEMENT_CHAR) / len(text) > 0.01:
        return True
    tokens = stripped.split()
    if not tokens:
        return True
    single_char_tokens = sum(1 for token in tokens if len(token) == 1)
    return single_char_tokens / len(tokens) > 0.5


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

                # OCR fallback fires when the page has NO extractable text, OR when
                # the extracted text layer is present but corrupt (scanned PDF with a
                # broken embedded text layer). In the corrupt case OCR replaces the
                # garbage blocks so downstream steps see real text.
                page_text = " ".join(block["text"] for block in page_text_blocks)
                if OCR_AVAILABLE and (
                    not page_text_blocks or _is_low_quality_text_layer(page_text)
                ):
                    ocr_text = self._ocr_page(page, page_num)
                    if ocr_text:
                        page_text_blocks = [
                            {
                                "text": ocr_text,
                                "bbox": (0, 0, page.rect.width, page.rect.height),
                                "page": page_num + 1,
                                "ocr": True,
                            }
                        ]
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
                    blocks.append(
                        {
                            "text": block_text.strip(),
                            "bbox": tuple(block["bbox"]),
                            "page": page_num + 1,
                        }
                    )

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
