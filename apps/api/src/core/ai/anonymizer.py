"""
Legacy shim for anonymizer.
Canonical implementation lives in src.core.privacy.anonymizer.
"""

from src.anonymizer.application.anonymization_service import AnonymizationService
from src.anonymizer.domain.pii_detector_service import PiiDetectorService


def get_anonymizer() -> AnonymizationService:
    return AnonymizationService(pii_detector=PiiDetectorService())

