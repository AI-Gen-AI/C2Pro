"""
Anonymize document use case.

Refers to Suite ID: TS-UA-SEC-UC-002.
"""

from __future__ import annotations

from src.anonymizer.application.anonymization_service import AnonymizationService
from src.anonymizer.domain.pii_detector_service import PiiDetectorService


class AnonymizeDocumentUseCase:
    def __init__(self, anonymization_service: AnonymizationService | None = None):
        self.anonymization_service = anonymization_service or AnonymizationService(pii_detector=PiiDetectorService())

    def execute(self, text: str) -> AnonymizedResult:
        # Assuming AnonymizationService.anonymize returns AnonymizedResult or a compatible type
        # You may need to adjust the return type based on the actual AnonymizationService implementation
        return self.anonymization_service.anonymize(text, config=AnonymizationConfig())
