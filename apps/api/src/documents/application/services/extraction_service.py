"""
Extraction Services.
Refers to Suite ID: TS-UA-SVC-EXT-001.
Refers to Suite ID: TS-UA-SVC-EXT-002.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Any


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


class ClauseExtractionService:
    """Refers to Suite ID: TS-UA-SVC-EXT-001."""

    def __init__(self, llm_client: Any) -> None:
        self.llm_client = llm_client

    def extract(self, text: str) -> list[ClauseDTO]:
        raw = self.llm_client.extract_clauses(text)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ContentParsingException("Invalid clause JSON") from exc

        clauses: list[ClauseDTO] = []
        for item in payload:
            clauses.append(
                ClauseDTO(
                    clause_code=item.get("clause_code", ""),
                    title=item.get("title", ""),
                    content=item.get("content", ""),
                    confidence_score=float(item.get("confidence_score", 0.0)),
                )
            )
        return clauses


class EntityExtractionService:
    """Refers to Suite ID: TS-UA-SVC-EXT-002."""

    def extract(self, text: str) -> dict[str, list[Any]]:
        money_entities: list[MoneyEntity] = []
        date_entities: list[DateEntity] = []

        money_match = re.search(r"(\d{1,3}(?:\.\d{3})*)\s*€", text)
        if money_match:
            amount = int(money_match.group(1).replace(".", ""))
            money_entities.append(MoneyEntity(amount=amount, currency="EUR"))

        date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
        if date_match:
            date_entities.append(DateEntity(value=date.fromisoformat(date_match.group(1))))

        return {"money": money_entities, "dates": date_entities}
