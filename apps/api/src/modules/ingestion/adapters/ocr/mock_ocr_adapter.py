"""
Mock OCR Adapter for Testing and Development.

Refers to I2: OCR + Table Parsing Reliability.

This adapter provides a simple mock implementation of the OCRAdapter interface
for testing and development purposes. It generates synthetic OCR results
without calling an actual OCR provider.
"""

import hashlib
from typing import Optional
import structlog

from src.modules.ingestion.application.ports import OCRAdapter, OCRResult

logger = structlog.get_logger(__name__)


class MockOCRAdapter(OCRAdapter):
    """
    Mock implementation of OCRAdapter for testing.

    This adapter generates synthetic OCR results without calling
    an actual OCR provider. Useful for:
    - Unit testing OCR processing logic
    - Integration testing without external dependencies
    - Development environments without OCR provider credentials
    - Performance testing with predictable results

    Args:
        provider_name: Name to use in the provider field (e.g., "MockPrimaryOCR", "MockFallbackOCR")
        default_confidence: Default confidence score to return (0.0-1.0)
        simulate_low_confidence: If True, returns low confidence scores for testing fallback
    """

    def __init__(
        self,
        provider_name: str = "MockOCR",
        default_confidence: float = 0.95,
        simulate_low_confidence: bool = False,
    ):
        """
        Initialize the mock OCR adapter.

        Args:
            provider_name: Provider name to include in results
            default_confidence: Default confidence score (0.0-1.0)
            simulate_low_confidence: If True, returns confidence < 0.5
        """
        self.provider_name = provider_name
        self.default_confidence = default_confidence
        self.simulate_low_confidence = simulate_low_confidence

        logger.info(
            "mock_ocr_adapter_initialized",
            provider=provider_name,
            default_confidence=default_confidence,
            simulate_low_confidence=simulate_low_confidence,
        )

    async def process_pdf_page(self, page_content: bytes) -> OCRResult:
        """
        Process a PDF page with mock OCR.

        Generates synthetic OCR results based on the page content hash.
        This provides consistent results for the same input without
        calling an actual OCR provider.

        Args:
            page_content: Binary content of the PDF page

        Returns:
            OCRResult with synthetic text, bboxes, and confidence
        """
        # Generate deterministic text based on content hash
        content_hash = hashlib.md5(page_content).hexdigest()[:8]
        text = f"Mock OCR extracted text from page (hash: {content_hash})"

        # Generate synthetic bounding boxes
        # Format: [x1, y1, x2, y2, confidence]
        bboxes = [
            [0.1, 0.1, 0.9, 0.2, 0.95],  # Header region
            [0.1, 0.25, 0.9, 0.5, 0.92],  # Body region 1
            [0.1, 0.55, 0.9, 0.8, 0.88],  # Body region 2
        ]

        # Determine confidence score
        if self.simulate_low_confidence:
            confidence = 0.3  # Force low confidence for fallback testing
        else:
            confidence = self.default_confidence

        result: OCRResult = {
            "text": text,
            "bboxes": bboxes,
            "confidence": confidence,
            "provider": self.provider_name,
        }

        logger.debug(
            "mock_ocr_processed_page",
            provider=self.provider_name,
            page_size_bytes=len(page_content),
            confidence=confidence,
            text_length=len(text),
            bbox_count=len(bboxes),
        )

        return result


class ConfigurableMockOCRAdapter(OCRAdapter):
    """
    Configurable mock OCR adapter with per-call confidence control.

    This adapter allows setting confidence scores on a per-call basis,
    useful for testing scenarios with varying OCR quality.

    Example:
        ```python
        adapter = ConfigurableMockOCRAdapter("PrimaryOCR")
        adapter.set_next_confidence(0.3)  # Next call will return low confidence
        result = await adapter.process_pdf_page(pdf_bytes)
        assert result["confidence"] == 0.3
        ```
    """

    def __init__(self, provider_name: str = "ConfigurableMockOCR"):
        """Initialize the configurable mock OCR adapter."""
        self.provider_name = provider_name
        self._next_confidence: Optional[float] = None
        self._call_count = 0

        logger.info(
            "configurable_mock_ocr_adapter_initialized",
            provider=provider_name,
        )

    def set_next_confidence(self, confidence: float) -> None:
        """
        Set the confidence score for the next process_pdf_page call.

        Args:
            confidence: Confidence score to return (0.0-1.0)
        """
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {confidence}")

        self._next_confidence = confidence
        logger.debug(
            "mock_ocr_confidence_set",
            provider=self.provider_name,
            next_confidence=confidence,
        )

    async def process_pdf_page(self, page_content: bytes) -> OCRResult:
        """
        Process a PDF page with configurable mock OCR.

        Uses the confidence set by set_next_confidence(), or defaults to 0.95.

        Args:
            page_content: Binary content of the PDF page

        Returns:
            OCRResult with synthetic text, bboxes, and configured confidence
        """
        self._call_count += 1

        # Use configured confidence or default
        confidence = self._next_confidence if self._next_confidence is not None else 0.95

        # Reset confidence for next call
        self._next_confidence = None

        # Generate deterministic text
        content_hash = hashlib.md5(page_content).hexdigest()[:8]
        text = f"Configurable mock OCR text (hash: {content_hash}, call: {self._call_count})"

        # Generate synthetic bboxes
        bboxes = [
            [0.1, 0.1, 0.9, 0.3, confidence],
            [0.1, 0.35, 0.9, 0.65, confidence * 0.95],
            [0.1, 0.7, 0.9, 0.9, confidence * 0.9],
        ]

        result: OCRResult = {
            "text": text,
            "bboxes": bboxes,
            "confidence": confidence,
            "provider": self.provider_name,
        }

        logger.debug(
            "configurable_mock_ocr_processed_page",
            provider=self.provider_name,
            page_size_bytes=len(page_content),
            confidence=confidence,
            call_count=self._call_count,
        )

        return result
