"""Tests for ScoreFromExtractionUseCase.

TASK-IMPL-010.5: Coherence Score™ pipeline entry point.
Thin orchestration over existing CoherenceDerivationService + CoherenceCalculationService.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from src.analysis.domain.coherence_derivation import (
    CoherenceDerivationResult,
    CoherenceScoringDerivationService,
)

# Lazy import to avoid SQLAlchemy mapper chain in unit tests
import importlib


def _import_use_case():
    mod = importlib.import_module(
        "src.coherence.application.use_cases.score_from_extraction"
    )
    return mod.ScoreFromExtractionCommand, mod.ScoreFromExtractionResult, mod.ScoreFromExtractionUseCase


ScoreFromExtractionCommand, ScoreFromExtractionResult, ScoreFromExtractionUseCase = _import_use_case()


def _make_derivation_result(**overrides) -> CoherenceDerivationResult:
    defaults = dict(
        scope_defined=True,
        schedule_within_contract=True,
        technical_consistent=True,
        legal_compliant=True,
        quality_standard_met=True,
        bom_items=[],
        contract_price=0.0,
        has_budget_risks=False,
        poor_extraction_quality=False,
        avg_wbs_confidence=0.9,
        risk_count=0,
        wbs_count=0,
        quality_note="",
    )
    defaults.update(overrides)
    return CoherenceDerivationResult(**defaults)


def _make_command(**overrides) -> ScoreFromExtractionCommand:
    defaults = dict(
        project_id=uuid4(),
        extracted_risks=[{"category": "LEGAL", "impact": "HIGH", "title": "R1"}],
        extracted_wbs=[{"code": "W1", "confidence": 0.9}],
        bom_items=[],
        confidence_score=0.85,
        document_text="Contract text here.",
    )
    defaults.update(overrides)
    return ScoreFromExtractionCommand(**defaults)


class TestScoreFromExtractionUseCase:
    def setup_method(self):
        self.derivation_service = MagicMock(spec=CoherenceScoringDerivationService)
        self.calculation_service = MagicMock()
        self.use_case = ScoreFromExtractionUseCase(
            derivation_service=self.derivation_service,
            calculation_service=self.calculation_service,
        )

    def test_execute_with_risks_returns_score(self):
        self.derivation_service.derive.return_value = _make_derivation_result()
        mock_calc_result = MagicMock()
        mock_calc_result.global_score = 78
        mock_calc_result.category_scores = {}
        self.calculation_service.calculate_coherence.return_value = mock_calc_result

        cmd = _make_command()
        result = self.use_case.execute(cmd)

        assert isinstance(result, ScoreFromExtractionResult)
        assert result.score == 78
        self.derivation_service.derive.assert_called_once()
        self.calculation_service.calculate_coherence.assert_called_once()

    def test_execute_empty_extraction_returns_zero_score(self):
        self.derivation_service.derive.return_value = _make_derivation_result(
            poor_extraction_quality=True,
            quality_note=", LOW QUALITY (conf=0.00)",
        )
        mock_calc_result = MagicMock()
        mock_calc_result.global_score = 0
        mock_calc_result.category_scores = {}
        self.calculation_service.calculate_coherence.return_value = mock_calc_result

        cmd = _make_command(
            extracted_risks=[],
            extracted_wbs=[],
            confidence_score=0.0,
            document_text="",
        )
        result = self.use_case.execute(cmd)

        assert result.score == 0

    def test_derivation_flags_passed_to_calculation(self):
        derivation = _make_derivation_result(
            scope_defined=False,
            legal_compliant=False,
            contract_price=50000.0,
            bom_items=[{"name": "Steel", "amount": 50000.0}],
        )
        self.derivation_service.derive.return_value = derivation
        mock_calc_result = MagicMock()
        mock_calc_result.global_score = 45
        mock_calc_result.category_scores = {}
        self.calculation_service.calculate_coherence.return_value = mock_calc_result

        cmd = _make_command()
        self.use_case.execute(cmd)

        call_kwargs = self.calculation_service.calculate_coherence.call_args
        assert call_kwargs.kwargs["scope_defined"] is False
        assert call_kwargs.kwargs["legal_compliant"] is False
        assert call_kwargs.kwargs["contract_price"] == 50000.0

    def test_quality_metadata_propagated(self):
        self.derivation_service.derive.return_value = _make_derivation_result(
            poor_extraction_quality=True,
            quality_note=", LOW QUALITY (conf=0.30)",
        )
        mock_calc_result = MagicMock()
        mock_calc_result.global_score = 20
        mock_calc_result.category_scores = {}
        self.calculation_service.calculate_coherence.return_value = mock_calc_result

        cmd = _make_command(confidence_score=0.3)
        result = self.use_case.execute(cmd)

        assert result.poor_extraction_quality is True
        assert "LOW QUALITY" in result.quality_note

    def test_breakdown_dict_built_from_category_scores(self):
        from src.coherence.domain.category_weights import CoherenceCategory

        self.derivation_service.derive.return_value = _make_derivation_result()
        mock_calc_result = MagicMock()
        mock_calc_result.global_score = 85
        mock_calc_result.category_scores = {
            CoherenceCategory.LEGAL: 90,
            CoherenceCategory.SCOPE: 80,
        }
        self.calculation_service.calculate_coherence.return_value = mock_calc_result

        cmd = _make_command()
        result = self.use_case.execute(cmd)

        assert isinstance(result.breakdown, dict)
        assert len(result.breakdown) == 2

    def test_execute_with_none_project_id_raises(self):
        """Coherence calculation requires a valid UUID project_id."""
        self.derivation_service.derive.return_value = _make_derivation_result()
        self.calculation_service.calculate_coherence.side_effect = (
            AttributeError("project_id cannot be None")
        )
        cmd = _make_command(project_id=UUID(int=0))
        with pytest.raises(AttributeError):
            self.use_case.execute(cmd)
