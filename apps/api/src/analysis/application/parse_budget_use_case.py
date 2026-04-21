"""
Application use case: parse a budget document into BOM items and derive
a confidence score.

Refers to EPIC-CORE-DECOUPLE / TASK-IMPL-010 Phase 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from src.analysis.domain.ai_extraction import (
    AIExtractionPort,
    BudgetExtractionService,
)

logger = structlog.get_logger()


@dataclass(frozen=True)
class ParseBudgetCommand:
    text: str


@dataclass(frozen=True)
class ParseBudgetResult:
    bom_items: list[dict[str, Any]]
    confidence_score: float


@dataclass(frozen=True)
class ParseBudgetUseCase:
    ai: AIExtractionPort
    service: BudgetExtractionService = field(default_factory=BudgetExtractionService)

    async def execute(self, cmd: ParseBudgetCommand) -> ParseBudgetResult:
        try:
            bom_items = await self.service.extract_bom(text=cmd.text, ai=self.ai)
        except Exception:
            logger.warning("parse_budget_use_case_failed", exc_info=True)
            bom_items = []

        confidence_score = 0.7 if bom_items else 0.0
        return ParseBudgetResult(bom_items=bom_items, confidence_score=confidence_score)
