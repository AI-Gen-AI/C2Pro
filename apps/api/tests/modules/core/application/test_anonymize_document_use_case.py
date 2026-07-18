"""
Anonymize Document Use Case Tests (TDD - RED Phase)

Refers to Suite ID: TS-UA-SEC-UC-002.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

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

    @pytest.mark.asyncio
    async def test_execute_awaits_underlying_anonymize_call(self) -> None:
        """BCK-119 regression.

        `execute()` returned `self.anonymization_service.anonymize(...)`
        without `await`, so it handed the caller an un-awaited coroutine
        instead of the anonymized string. Any consumer that trusted the
        declared `-> str` return type would treat that (always truthy)
        coroutine as anonymized text.
        """
        use_case = AnonymizeDocumentUseCase()

        result = await use_case.execute("Contact John Doe at john@example.com")

        assert isinstance(result, str)
