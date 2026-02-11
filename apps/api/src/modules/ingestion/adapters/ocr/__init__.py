"""
OCR Adapter Implementations for C2Pro Ingestion.

This package contains concrete implementations of the OCRAdapter interface
for various OCR providers.

Available Adapters:
- MockOCRAdapter: Simple mock for testing
- ConfigurableMockOCRAdapter: Mock with configurable confidence
- TesseractOCRAdapter: Tesseract OCR integration (primary provider)
- GoogleVisionOCRAdapter: Google Cloud Vision integration (fallback provider)
- MockGoogleVisionOCRAdapter: Mock Google Vision for testing
"""

from .mock_ocr_adapter import MockOCRAdapter, ConfigurableMockOCRAdapter
from .tesseract_adapter import TesseractOCRAdapter
from .google_vision_adapter import GoogleVisionOCRAdapter, MockGoogleVisionOCRAdapter

__all__ = [
    "MockOCRAdapter",
    "ConfigurableMockOCRAdapter",
    "TesseractOCRAdapter",
    "GoogleVisionOCRAdapter",
    "MockGoogleVisionOCRAdapter",
]
