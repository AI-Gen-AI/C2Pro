"""Tests for critique evaluation domain service.

TASK-IMPL-010.3: Confidence calc, retry logic, HITL threshold.
Pure domain — no os, langgraph, or langchain imports.
"""

from __future__ import annotations

from src.analysis.domain.critique_evaluation import (
    CritiqueEvaluationResult,
    CritiqueEvaluationService,
)


class TestCalculateConfidence:
    def setup_method(self):
        self.service = CritiqueEvaluationService()

    def test_average_with_mixed_items(self):
        items = [
            {"confidence": 0.9},
            {"confidence": 0.7},
            {"confidence": 0.8},
        ]
        assert abs(self.service.calculate_confidence(items) - 0.8) < 0.01

    def test_empty_list_returns_zero(self):
        assert self.service.calculate_confidence([]) == 0.0

    def test_items_without_confidence_field(self):
        items = [{"title": "Risk A"}, {"title": "Risk B"}]
        # Items exist but no confidence → default 0.9
        assert self.service.calculate_confidence(items) == 0.9

    def test_mixed_valid_and_missing_confidence(self):
        items = [
            {"confidence": 0.6},
            {"title": "no confidence"},
            {"confidence": 0.8},
        ]
        # Only uses valid confidence values: (0.6 + 0.8) / 2 = 0.7
        result = self.service.calculate_confidence(items)
        assert abs(result - 0.7) < 0.01

    def test_non_numeric_confidence_ignored(self):
        items = [
            {"confidence": "high"},
            {"confidence": 0.5},
        ]
        result = self.service.calculate_confidence(items)
        assert result == 0.5


class TestEvaluateCritique:
    def setup_method(self):
        self.service = CritiqueEvaluationService()

    def test_critique_ok_clears_notes(self):
        result = self.service.evaluate_critique(
            critique_status="OK",
            critique_notes="All good",
            confidence=0.9,
            retry_count=0,
        )
        assert isinstance(result, CritiqueEvaluationResult)
        assert result.critique_notes == ""
        assert result.human_approval_required is False
        assert result.retry_count == 0

    def test_critique_retry_increments_count(self):
        result = self.service.evaluate_critique(
            critique_status="RETRY",
            critique_notes="Missing references",
            confidence=0.9,
            retry_count=0,
        )
        assert result.retry_count == 1
        assert result.critique_notes == "Missing references"
        assert result.human_approval_required is False

    def test_hitl_required_low_confidence(self):
        result = self.service.evaluate_critique(
            critique_status="OK",
            confidence=0.7,
            critique_notes="",
            retry_count=0,
        )
        assert result.human_approval_required is True

    def test_hitl_required_retry_exceeded(self):
        result = self.service.evaluate_critique(
            critique_status="RETRY",
            confidence=0.9,
            critique_notes="Still bad",
            retry_count=1,  # Will become 2, which equals max_retries
        )
        assert result.retry_count == 2
        assert result.human_approval_required is True

    def test_skip_hitl_bypasses_approval(self):
        result = self.service.evaluate_critique(
            critique_status="OK",
            confidence=0.3,  # Very low, would normally trigger HITL
            critique_notes="",
            retry_count=0,
            skip_hitl=True,
        )
        assert result.human_approval_required is False

    def test_custom_confidence_threshold(self):
        service = CritiqueEvaluationService(confidence_threshold=0.5)
        result = service.evaluate_critique(
            critique_status="OK",
            confidence=0.6,
            critique_notes="",
            retry_count=0,
        )
        assert result.human_approval_required is False

    def test_confidence_passed_through(self):
        result = self.service.evaluate_critique(
            critique_status="OK",
            confidence=0.85,
            critique_notes="",
            retry_count=0,
        )
        assert result.confidence == 0.85


class TestDetermineNextStep:
    def setup_method(self):
        self.service = CritiqueEvaluationService()

    def test_human_approval_routes_to_interrupt(self):
        result = self.service.determine_next_step(
            human_approval_required=True,
            critique_notes="",
            retry_count=0,
            doc_type="contract",
        )
        assert result == "human_interrupt"

    def test_retry_contract_routes_to_risk(self):
        result = self.service.determine_next_step(
            human_approval_required=False,
            critique_notes="Retry needed",
            retry_count=1,
            doc_type="contract",
        )
        assert result == "risk_extractor"

    def test_retry_budget_routes_to_budget(self):
        result = self.service.determine_next_step(
            human_approval_required=False,
            critique_notes="Retry needed",
            retry_count=1,
            doc_type="budget",
        )
        assert result == "budget_parser"

    def test_retry_technical_spec_routes_to_wbs(self):
        result = self.service.determine_next_step(
            human_approval_required=False,
            critique_notes="Retry needed",
            retry_count=1,
            doc_type="technical_spec",
        )
        assert result == "wbs_extractor"

    def test_no_retry_routes_to_stakeholder(self):
        result = self.service.determine_next_step(
            human_approval_required=False,
            critique_notes="",
            retry_count=0,
            doc_type="contract",
        )
        assert result == "stakeholder_extractor"

    def test_retry_count_over_max_routes_to_stakeholder(self):
        result = self.service.determine_next_step(
            human_approval_required=False,
            critique_notes="Still failing",
            retry_count=3,  # Over max_retries=2
            doc_type="contract",
        )
        assert result == "stakeholder_extractor"
