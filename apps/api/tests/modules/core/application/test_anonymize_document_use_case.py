"""
Anonymize Document Use Case Tests (TDD - RED Phase)

Refers to Suite ID: TS-UA-SEC-UC-002.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.security.application.anonymize_document_use_case import (
    AnonymizeDocumentUseCase,
)


@dataclass
class _FakeResult:
    anonymized_text: str
    mapping: dict[str, str]


class _FakeAnonymizer:
    def anonymize_document(self, text: str) -> _FakeResult:
        return _FakeResult(anonymized_text="ANONYMIZED", mapping={"X": "Y"})


class TestAnonymizeDocumentUseCase:
    """Refers to Suite ID: TS-UA-SEC-UC-002."""

    def test_anonymizes_document_text(self, monkeypatch) -> None:
        def _fake_get_anonymizer():
            return _FakeAnonymizer()

        monkeypatch.setattr(
            "src.core.security.application.anonymize_document_use_case.get_anonymizer",
            _fake_get_anonymizer,
        )

        use_case = AnonymizeDocumentUseCase()
        result = use_case.execute("Sensitive content")

        assert result.anonymized_text == "ANONYMIZED"
        assert result.mapping == {"X": "Y"}
