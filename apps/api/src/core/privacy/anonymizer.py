"""Test Suite ID: TS-SEC-PII-FALLBACK-001.

Compatibility privacy anonymizer with deterministic regex fallback.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

PRESIDIO_AVAILABLE = False


@dataclass(frozen=True)
class AnonymizedResult:
    """Anonymized text plus token-to-original mapping."""

    anonymized_text: str
    mapping: dict[str, str]


class PiiAnonymizerService:
    """Small singleton-compatible anonymizer used by legacy privacy imports."""

    _instance: PiiAnonymizerService | None = None
    _initialized = False

    _EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    _SPANISH_ID_RE = re.compile(r"\b\d{8}[A-Za-z]\b")

    def __new__(cls) -> PiiAnonymizerService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def anonymize_document(self, text: str) -> AnonymizedResult:
        """Replace supported PII with stable placeholder tokens."""
        mapping: dict[str, str] = {}
        anonymized = text

        for index, match in enumerate(self._EMAIL_RE.findall(text), start=1):
            token = f"<EMAIL_ADDRESS_{index}>"
            mapping[token] = match
            anonymized = anonymized.replace(match, token, 1)

        for index, match in enumerate(self._SPANISH_ID_RE.findall(text), start=1):
            token = f"<SPANISH_ID_{index}>"
            mapping[token] = match
            anonymized = anonymized.replace(match, token, 1)

        return AnonymizedResult(anonymized_text=anonymized, mapping=mapping)


def get_anonymizer() -> PiiAnonymizerService:
    """Return the privacy anonymizer service."""
    return PiiAnonymizerService()


def anonymize_text_simple(text: str) -> str:
    """Anonymize text and return only the anonymized payload."""
    return get_anonymizer().anonymize_document(text).anonymized_text


def deanonymize_text_simple(text: str, mapping: dict[str, str] | None = None) -> str:
    """Restore placeholders using a caller-provided mapping."""
    restored = text
    for token, original in (mapping or {}).items():
        restored = restored.replace(token, original)
    return restored
