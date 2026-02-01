"""
Coherence Engine v2 Rules Engine Tests (TDD - RED Phase)

Refers to Suite ID: TS-UD-COH-RUL-001 to TS-UD-COH-RUL-006.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.coherence.domain.rules_engine import (
    CoherenceContext,
    CoherenceRulesEngine,
    ScoreCalculator,
)
from src.coherence.domain.anti_gaming import AlertEvent, AntiGamingDetector


def _base_context(**overrides):
    context = CoherenceContext(
        contract_price=1000.0,
        bom_items=[
            {"amount": 600.0, "budget_line_assigned": True},
            {"amount": 400.0, "budget_line_assigned": True},
        ],
        scope_defined=True,
        schedule_within_contract=True,
        technical_consistent=True,
        legal_compliant=True,
        quality_standard_met=True,
    )
    return context.model_copy(update=overrides)


class TestScopeRules:
    """Refers to Suite ID: TS-UD-COH-RUL-001."""

    def test_scope_defined_has_no_violations(self):
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(scope_defined=True))
        assert result.category_scores["SCOPE"] == 100


class TestBudgetRules:
    """Refers to Suite ID: TS-UD-COH-RUL-002."""

    def test_rule_r6_budget_deviation_10_percent_drops_score(self):
        engine = CoherenceRulesEngine()
        context = _base_context(
            contract_price=1000.0,
            bom_items=[
                {"amount": 1100.0, "budget_line_assigned": True},
            ],
        )
        result = engine.evaluate(context)
        assert "R6" in result.violations["BUDGET"]
        assert result.category_scores["BUDGET"] <= 70

    def test_rule_r15_bom_item_without_budget_line_is_violation(self):
        engine = CoherenceRulesEngine()
        context = _base_context(
            bom_items=[
                {"amount": 600.0, "budget_line_assigned": True},
                {"amount": 400.0, "budget_line_assigned": False},
            ],
        )
        result = engine.evaluate(context)
        assert "R15" in result.violations["BUDGET"]


class TestTimeRules:
    """Refers to Suite ID: TS-UD-COH-RUL-003."""

    def test_schedule_within_contract_has_no_violations(self):
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(schedule_within_contract=True))
        assert result.category_scores["TIME"] == 100


class TestTechnicalRules:
    """Refers to Suite ID: TS-UD-COH-RUL-004."""

    def test_technical_inconsistency_drops_score(self):
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(technical_consistent=False))
        assert result.category_scores["TECHNICAL"] < 100


class TestLegalRules:
    """Refers to Suite ID: TS-UD-COH-RUL-005."""

    def test_legal_non_compliance_drops_score(self):
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(legal_compliant=False))
        assert result.category_scores["LEGAL"] < 100


class TestQualityRules:
    """Refers to Suite ID: TS-UD-COH-RUL-006."""

    def test_quality_missing_standard_drops_score(self):
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(quality_standard_met=False))
        assert result.category_scores["QUALITY"] < 100


class TestScoreCalculator:
    """Refers to Suite ID: TS-UD-COH-SCR-001."""

    def test_score_perfect_params_is_100(self):
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context())
        calculator = ScoreCalculator()
        score = calculator.calculate(result.category_scores)
        assert score == 100

    def test_score_budget_deviation_over_10_percent_drops_significantly(self):
        engine = CoherenceRulesEngine()
        context = _base_context(
            contract_price=1000.0,
            bom_items=[{"amount": 1120.0, "budget_line_assigned": True}],
        )
        result = engine.evaluate(context)
        calculator = ScoreCalculator()
        score = calculator.calculate(result.category_scores)
        assert score <= 80

    def test_score_changes_with_custom_weights(self):
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(legal_compliant=False))
        calculator = ScoreCalculator()
        weights = {"BUDGET": 0.50, "SCOPE": 0.10, "TIME": 0.10, "TECHNICAL": 0.10, "LEGAL": 0.10, "QUALITY": 0.10}
        score = calculator.calculate(result.category_scores, weights=weights)
        assert score != calculator.calculate(result.category_scores)


class TestAntiGamingRules:
    """Refers to Suite ID: TS-UD-COH-GAM-001."""

    def test_detects_more_than_10_changes_per_hour(self):
        now = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
        user_id = uuid4()
        signature = "alert:coherence:budget_deviation"

        events = [
            AlertEvent(type="updated", user_id=user_id, signature=signature, timestamp=now + timedelta(minutes=i * 5))
            for i in range(11)
        ]

        detector = AntiGamingDetector(window_minutes=60, repeat_threshold=10)
        result = detector.detect(events)

        assert result.is_gaming is True
        assert result.reason == "mass_changes"
