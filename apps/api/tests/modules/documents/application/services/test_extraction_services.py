"""
Extraction Services Tests (TDD - RED Phase)

Refers to Suite IDs: TS-UA-SVC-EXT-001, TS-UA-SVC-EXT-002.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List
from uuid import uuid4

import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Skeleton DTOs/Entities (tests should run but fail until real code exists)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClauseDTO:
    clause_code: str
    title: str
    content: str
    confidence_score: float


@dataclass(frozen=True)
class MoneyEntity:
    amount: int
    currency: str


@dataclass(frozen=True)
class DateEntity:
    value: date


class ContentParsingException(Exception):
    """Raised when LLM JSON content cannot be parsed."""


class ILLMClientPort:
    """Minimal port interface for mocking."""

    def extract_clauses(self, text: str) -> str:  # returns JSON string
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestClauseExtractionService:
    """Refers to Suite ID: TS-UA-SVC-EXT-001."""

    def test_malformed_json_raises_content_parsing_exception(self):
        from src.documents.application.services.extraction_service import (
            ClauseExtractionService,
        )

        llm_client = MagicMock(spec=ILLMClientPort)
        llm_client.extract_clauses.return_value = '[{"clause_code":"1","title":"T","content":"C"}'

        service = ClauseExtractionService(llm_client=llm_client)

        with pytest.raises(ContentParsingException):
            service.extract(text="Any text")

    def test_valid_json_returns_two_clause_dtos(self):
        from src.documents.application.services.extraction_service import (
            ClauseExtractionService,
        )

        llm_client = MagicMock(spec=ILLMClientPort)
        llm_client.extract_clauses.return_value = (
            '[{"clause_code":"1.1","title":"Scope","content":"Text A","confidence_score":0.9},'
            '{"clause_code":"1.2","title":"Payment","content":"Text B","confidence_score":0.8}]'
        )

        service = ClauseExtractionService(llm_client=llm_client)

        clauses = service.extract(text="Any text")

        assert isinstance(clauses, list)
        assert len(clauses) == 2
        assert clauses[0] == ClauseDTO(
            clause_code="1.1",
            title="Scope",
            content="Text A",
            confidence_score=0.9,
        )
        assert clauses[1] == ClauseDTO(
            clause_code="1.2",
            title="Payment",
            content="Text B",
            confidence_score=0.8,
        )


class TestEntityExtractionService:
    """Refers to Suite ID: TS-UA-SVC-EXT-002."""

    def test_extracts_money_and_date_entities(self):
        from src.documents.application.services.extraction_service import (
            EntityExtractionService,
        )

        service = EntityExtractionService()

        text = "The total penalty is 150.000€ due by 2026-01-01"
        entities = service.extract(text)

        assert entities["money"] == [MoneyEntity(amount=150000, currency="EUR")]
        assert entities["dates"] == [DateEntity(value=date(2026, 1, 1))]
