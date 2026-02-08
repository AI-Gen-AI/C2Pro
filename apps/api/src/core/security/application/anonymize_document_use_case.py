"""
Anonymize document use case.

Refers to Suite ID: TS-UA-SEC-UC-002.
"""

from __future__ import annotations

from src.core.privacy.anonymizer import AnonymizedResult, get_anonymizer


class AnonymizeDocumentUseCase:
    """Refers to Suite ID: TS-UA-SEC-UC-002."""

    def execute(self, text: str) -> AnonymizedResult:
        anonymizer = get_anonymizer()
        return anonymizer.anonymize_document(text)
