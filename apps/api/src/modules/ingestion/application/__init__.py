"""
C2Pro - Ingestion Application Layer

Use cases and orchestration logic for document ingestion.
Defines ports (interfaces) and services that coordinate domain entities.
"""

from src.modules.ingestion.application.ports import OCRAdapter, OCRResult
from src.modules.ingestion.application.services import OCRProcessingService

__all__ = [
    "OCRAdapter",
    "OCRResult",
    "OCRProcessingService",
]
