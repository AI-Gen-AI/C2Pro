"""
C2Pro - Ingestion Application Ports

Defines abstract interfaces (ports) for external dependencies.
Following Hexagonal Architecture, these interfaces are implemented by adapters.

Increment I2: OCR + Table Parsing Reliability
- OCRAdapter: Abstract interface for OCR providers (primary/fallback strategy)
- OCRResult: TypedDict for structured OCR output
"""

from abc import ABC, abstractmethod
from typing import TypedDict


class OCRResult(TypedDict):
    """
    Structured output from OCR processing.

    Refers to I2.1: Integration test - scanned PDF returns text + bbox + confidence.

    This TypedDict ensures all OCR adapters return consistent data structure
    for downstream processing and observability.

    Fields:
        text: Extracted text content from the page
        bboxes: List of bounding boxes [x1, y1, x2, y2, confidence] for each text segment
        confidence: Overall page-level confidence score (0.0-1.0)
        provider: Name of the OCR provider used (e.g., "PrimaryOCR", "FallbackOCR")
    """

    text: str
    bboxes: list[list[float]]  # Each bbox: [x1, y1, x2, y2, confidence_score]
    confidence: float          # Overall page confidence
    provider: str              # Name of the OCR provider used


class OCRAdapter(ABC):
    """
    Abstract Base Class for OCR adapters (Port).

    Refers to I2.3: OCR adapter interface.

    This port defines the contract that all OCR implementations must follow,
    enabling the system to switch between different OCR providers
    (Tesseract, Google Vision, AWS Textract, etc.) transparently.

    The adapter pattern allows for:
    - Primary/fallback OCR strategy (reliability)
    - Provider-agnostic business logic
    - Easy testing with mock implementations
    - Future provider additions without changing core logic

    Implementations should:
    1. Handle provider-specific authentication and configuration
    2. Convert provider-specific output to OCRResult format
    3. Raise IngestionError for unrecoverable failures
    4. Log provider-specific metrics for observability
    """

    @abstractmethod
    async def process_pdf_page(self, page_content: bytes) -> OCRResult:
        """
        Processes a single PDF page (as bytes) using OCR.

        This method should be implemented by concrete OCR adapters
        (TesseractOCRAdapter, GoogleVisionOCRAdapter, etc.).

        Args:
            page_content: The binary content of a single PDF page.

        Returns:
            OCRResult dictionary containing:
            - text: The extracted text
            - bboxes: List of bounding boxes for each text segment, with confidence
            - confidence: Overall confidence score for the page (0.0-1.0)
            - provider: The name of the OCR provider used

        Raises:
            IngestionError: If OCR processing fails unrecoverably
                (malformed PDF, provider API error, etc.)

        Example:
            ```python
            adapter = TesseractOCRAdapter()
            result = await adapter.process_pdf_page(pdf_bytes)
            print(f"Extracted text: {result['text']}")
            print(f"Confidence: {result['confidence']}")
            print(f"Provider: {result['provider']}")
            ```
        """
        raise NotImplementedError("OCR adapters must implement process_pdf_page()")
