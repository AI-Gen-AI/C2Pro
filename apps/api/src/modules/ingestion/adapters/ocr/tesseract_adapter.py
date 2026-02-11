"""
Tesseract OCR Adapter Implementation.

Refers to I2: OCR + Table Parsing Reliability.

This adapter provides integration with Tesseract OCR engine for text extraction
from scanned PDFs. Tesseract is typically used as the primary OCR provider
due to its speed and cost-effectiveness.

Dependencies:
    - pytesseract: Python wrapper for Tesseract
    - pdf2image: PDF to image conversion
    - Tesseract OCR engine installed on system

Installation:
    pip install pytesseract pdf2image pillow
    # Install Tesseract OCR binary:
    # Ubuntu/Debian: apt-get install tesseract-ocr
    # macOS: brew install tesseract
    # Windows: Download installer from GitHub
"""

from typing import List, Tuple, Optional
import structlog

from src.modules.ingestion.application.ports import OCRAdapter, OCRResult
from src.modules.ingestion.domain.entities import IngestionError

logger = structlog.get_logger(__name__)


class TesseractOCRAdapter(OCRAdapter):
    """
    Tesseract OCR adapter for document text extraction.

    This adapter integrates with Tesseract OCR engine to extract text
    from scanned PDF pages. It provides:
    - Fast, cost-effective OCR processing
    - Bounding box extraction for layout analysis
    - Confidence scoring for quality assessment
    - Configurable language support

    Typically used as the primary OCR provider in a fallback strategy:
    - Fast processing for high-quality scans (80% of documents)
    - Falls back to premium OCR for low-quality scans

    Args:
        language: Tesseract language code (default: "eng")
        tesseract_path: Optional path to tesseract binary
        dpi: DPI for PDF rendering (higher = better quality, slower)
        confidence_threshold: Minimum word confidence to include (0-100)
    """

    def __init__(
        self,
        language: str = "eng",
        tesseract_path: Optional[str] = None,
        dpi: int = 300,
        confidence_threshold: int = 0,
    ):
        """
        Initialize Tesseract OCR adapter.

        Args:
            language: Tesseract language code (e.g., "eng", "spa", "fra")
            tesseract_path: Path to tesseract binary (auto-detected if None)
            dpi: DPI for PDF rendering (300 recommended for OCR)
            confidence_threshold: Minimum word confidence to include (0-100)
        """
        self.language = language
        self.tesseract_path = tesseract_path
        self.dpi = dpi
        self.confidence_threshold = confidence_threshold

        # Import dependencies (deferred to allow installation without dependencies)
        try:
            import pytesseract
            from pdf2image import convert_from_bytes
            from PIL import Image

            self.pytesseract = pytesseract
            self.convert_from_bytes = convert_from_bytes
            self.Image = Image

            # Configure tesseract path if provided
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path

        except ImportError as e:
            logger.error(
                "tesseract_dependencies_missing",
                error=str(e),
                message="Install dependencies: pip install pytesseract pdf2image pillow",
            )
            raise IngestionError(
                f"Tesseract OCR dependencies not installed: {e}"
            ) from e

        logger.info(
            "tesseract_ocr_adapter_initialized",
            language=language,
            dpi=dpi,
            confidence_threshold=confidence_threshold,
        )

    async def process_pdf_page(self, page_content: bytes) -> OCRResult:
        """
        Process a PDF page with Tesseract OCR.

        Workflow:
        1. Convert PDF bytes to image
        2. Run Tesseract OCR with confidence scoring
        3. Extract text, bounding boxes, and confidence scores
        4. Normalize bounding boxes to 0-1 coordinates
        5. Calculate page-level confidence

        Args:
            page_content: Binary content of a single PDF page

        Returns:
            OCRResult with extracted text, bboxes, and confidence

        Raises:
            IngestionError: If PDF conversion or OCR processing fails
        """
        try:
            # Step 1: Convert PDF to image
            logger.debug(
                "tesseract_converting_pdf",
                page_size_bytes=len(page_content),
                dpi=self.dpi,
            )

            images = self.convert_from_bytes(
                page_content,
                dpi=self.dpi,
                fmt="png",
            )

            if not images:
                raise IngestionError("PDF page conversion resulted in no images")

            # Assume single page
            image = images[0]
            width, height = image.size

            # Step 2: Run Tesseract OCR with detailed data
            logger.debug(
                "tesseract_running_ocr",
                image_size=(width, height),
                language=self.language,
            )

            # Get detailed OCR data including bounding boxes and confidence
            ocr_data = self.pytesseract.image_to_data(
                image,
                lang=self.language,
                output_type=self.pytesseract.Output.DICT,
            )

            # Step 3: Extract text and bounding boxes
            text_parts = []
            bboxes = []
            confidences = []

            for i in range(len(ocr_data["text"])):
                word = ocr_data["text"][i].strip()
                conf = int(ocr_data["conf"][i])

                # Skip empty words or low-confidence words
                if not word or conf < self.confidence_threshold:
                    continue

                # Extract bounding box
                x = ocr_data["left"][i]
                y = ocr_data["top"][i]
                w = ocr_data["width"][i]
                h = ocr_data["height"][i]

                # Normalize to 0-1 coordinates
                x1_norm = x / width
                y1_norm = y / height
                x2_norm = (x + w) / width
                y2_norm = (y + h) / height
                conf_norm = conf / 100.0  # Tesseract uses 0-100, we use 0-1

                bboxes.append([x1_norm, y1_norm, x2_norm, y2_norm, conf_norm])
                text_parts.append(word)
                confidences.append(conf_norm)

            # Combine text
            text = " ".join(text_parts)

            # Calculate overall page confidence
            if confidences:
                overall_confidence = sum(confidences) / len(confidences)
            else:
                overall_confidence = 0.0

            result: OCRResult = {
                "text": text,
                "bboxes": bboxes,
                "confidence": overall_confidence,
                "provider": "TesseractOCR",
            }

            logger.info(
                "tesseract_ocr_complete",
                text_length=len(text),
                bbox_count=len(bboxes),
                confidence=overall_confidence,
            )

            return result

        except Exception as e:
            logger.error(
                "tesseract_ocr_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise IngestionError(f"Tesseract OCR processing failed: {e}") from e
