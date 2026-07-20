"""
Anonymize Document Use Case Tests (TDD - RED Phase)

Refers to Suite ID: TS-UA-SEC-UC-002.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.anonymizer.application.anonymization_service import (
    AnonymizationConfig,
    AnonymizationService,
)
from src.core.security.application.anonymize_document_use_case import (
    AnonymizeDocumentUseCase,
)


class TestAnonymizeDocumentUseCase:
    """Refers to Suite ID: TS-UA-SEC-UC-002."""

    @pytest.mark.asyncio
    async def test_anonymizes_document_text(self) -> None:
        """Uses the injected application-service seam, not the removed global factory."""
        anonymization_service = AsyncMock(spec=AnonymizationService)
        anonymization_service.anonymize.return_value = "ANONYMIZED"
        use_case = AnonymizeDocumentUseCase(anonymization_service=anonymization_service)

        result = await use_case.execute("Sensitive content")

        assert result == "ANONYMIZED"
        anonymization_service.anonymize.assert_awaited_once_with(
            "Sensitive content",
            config=AnonymizationConfig(),
        )

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
