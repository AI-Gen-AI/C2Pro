"""
Application use case: run the LLM critique and evaluate its result.

Wraps `CritiqueExtractionService` (LLM call) + `CritiqueEvaluationService`
(pure domain math) behind a single predictable output consumed by the
LangGraph critique node and its outgoing conditional edge.

Refers to EPIC-CORE-DECOUPLE / TASK-IMPL-010 Phase 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.analysis.domain.ai_extraction import (
    AIExtractionPort,
    CritiqueExtractionService,
)
from src.analysis.domain.critique_evaluation import CritiqueEvaluationService


@dataclass(frozen=True)
class CritiqueExtractionCommand:
    extracted_risks: list[dict[str, Any]]
    extracted_wbs: list[dict[str, Any]]
    doc_type: str | None
    retry_count: int


@dataclass(frozen=True)
class CritiqueExtractionResult:
    status: str               # "OK" | "RETRY"
    notes_raw: str            # the critique note as returned by the LLM
    confidence: float
    retry_count: int
    human_approval_required: bool
    critique_notes: str       # possibly cleared by evaluation (OK → "")


@dataclass(frozen=True)
class CritiqueExtractionUseCase:
    ai: AIExtractionPort
    extraction_service: CritiqueExtractionService = field(
        default_factory=CritiqueExtractionService
    )
    evaluation_service: CritiqueEvaluationService = field(
        default_factory=CritiqueEvaluationService
    )

    async def execute(self, cmd: CritiqueExtractionCommand) -> CritiqueExtractionResult:
        items = cmd.extracted_risks if cmd.extracted_risks else cmd.extracted_wbs
        confidence = self.evaluation_service.calculate_confidence(items)

        critique = await self.extraction_service.extract(
            items=items,
            doc_type=cmd.doc_type or "unknown",
            ai=self.ai,
        )

        evaluation = self.evaluation_service.evaluate_critique(
            critique_status=critique.status,
            critique_notes=critique.notes,
            confidence=confidence,
            retry_count=cmd.retry_count,
        )

        return CritiqueExtractionResult(
            status=critique.status,
            notes_raw=critique.notes,
            confidence=confidence,
            retry_count=evaluation.retry_count,
            human_approval_required=evaluation.human_approval_required,
            critique_notes=evaluation.critique_notes,
        )
