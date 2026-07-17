"""
Coherence Score™ pipeline entry point for LangGraph orchestration.

Thin orchestration layer: derives flags from extracted data, then delegates
to existing CoherenceCalculationService. ZERO new calculation logic.

Refers to TASK-IMPL-010.5.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.core.json_types import JsonDict
from src.analysis.domain.coherence_derivation import (
    CoherenceDerivationInput,
    CoherenceScoringDerivationService,
)
from src.coherence.application.services import CoherenceCalculationService

warnings.warn(
    "ScoreFromExtractionUseCase is deprecated; N8 now delegates to the "
    "canonical coherence graph subgraph. Removal is scheduled for the next sprint.",
    DeprecationWarning,
    stacklevel=2,
)


@dataclass(frozen=True)
class ScoreFromExtractionCommand:
    """Input for Coherence Score™ calculation from extraction results."""

    project_id: UUID
    extracted_risks: list[JsonDict]
    extracted_wbs: list[JsonDict]
    bom_items: list[JsonDict]
    confidence_score: float
    document_text: str


@dataclass(frozen=True)
class ScoreFromExtractionResult:
    """Coherence Score™ result with quality metadata."""

    score: int | float | None
    breakdown: JsonDict
    poor_extraction_quality: bool
    quality_note: str


class ScoreFromExtractionUseCase:
    """Orchestrates Coherence Score™ calculation from extracted analysis data.

    Pipeline: CoherenceDerivationInput → derive flags → calculate score.
    Reuses existing TASK-AI-052..078 infrastructure.
    """

    def __init__(
        self,
        derivation_service: CoherenceScoringDerivationService,
        calculation_service: CoherenceCalculationService,
    ) -> None:
        self._derivation = derivation_service
        self._calculation = calculation_service

    def execute(self, command: ScoreFromExtractionCommand) -> ScoreFromExtractionResult:
        derivation_input = CoherenceDerivationInput(
            extracted_risks=command.extracted_risks,
            extracted_wbs=command.extracted_wbs,
            bom_items=command.bom_items,
            confidence_score=command.confidence_score,
            document_text=command.document_text,
        )
        derivation = self._derivation.derive(derivation_input)

        calc_result = self._calculation.calculate_coherence(
            project_id=command.project_id,
            contract_price=derivation.contract_price,
            bom_items=derivation.bom_items,
            scope_defined=derivation.scope_defined,
            schedule_within_contract=derivation.schedule_within_contract,
            technical_consistent=derivation.technical_consistent,
            legal_compliant=derivation.legal_compliant,
            quality_standard_met=derivation.quality_standard_met,
            document_count=1,
        )

        breakdown: JsonDict = {
            cat.value: sub_score
            for cat, sub_score in calc_result.category_scores.items()
        }

        return ScoreFromExtractionResult(
            score=calc_result.global_score,
            breakdown=breakdown,
            poor_extraction_quality=derivation.poor_extraction_quality,
            quality_note=derivation.quality_note,
        )
