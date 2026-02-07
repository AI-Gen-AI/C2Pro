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

    def test_001_scope_defined_true_has_perfect_score(self):
        """SCOPE=100 when scope_defined=True."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(scope_defined=True))
        assert result.category_scores["SCOPE"] == 100

    def test_002_scope_defined_true_has_no_violations(self):
        """No violations when scope_defined=True."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(scope_defined=True))
        assert result.violations["SCOPE"] == []

    def test_003_scope_undefined_triggers_rule_r11(self):
        """Rule R11 triggered when scope_defined=False."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(scope_defined=False))
        assert "R11" in result.violations["SCOPE"]

    def test_004_scope_undefined_drops_score_to_70(self):
        """SCOPE=70 when scope_defined=False."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(scope_defined=False))
        assert result.category_scores["SCOPE"] == 70

    def test_005_scope_undefined_has_exactly_one_violation(self):
        """Only R11 violation when scope_defined=False."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(scope_defined=False))
        assert len(result.violations["SCOPE"]) == 1
        assert result.violations["SCOPE"][0] == "R11"

    def test_006_scope_violation_does_not_affect_budget_score(self):
        """SCOPE violations are isolated from BUDGET category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(scope_defined=False))
        assert result.category_scores["BUDGET"] == 100

    def test_007_scope_violation_does_not_affect_time_score(self):
        """SCOPE violations are isolated from TIME category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(scope_defined=False))
        assert result.category_scores["TIME"] == 100

    def test_008_scope_violation_does_not_affect_technical_score(self):
        """SCOPE violations are isolated from TECHNICAL category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(scope_defined=False))
        assert result.category_scores["TECHNICAL"] == 100

    def test_009_scope_violation_does_not_affect_legal_score(self):
        """SCOPE violations are isolated from LEGAL category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(scope_defined=False))
        assert result.category_scores["LEGAL"] == 100

    def test_010_scope_violation_does_not_affect_quality_score(self):
        """SCOPE violations are isolated from QUALITY category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(scope_defined=False))
        assert result.category_scores["QUALITY"] == 100

    def test_011_budget_violations_do_not_affect_scope_score(self):
        """BUDGET violations don't impact SCOPE category."""
        engine = CoherenceRulesEngine()
        context = _base_context(
            scope_defined=True,
            contract_price=1000.0,
            bom_items=[{"amount": 1200.0, "budget_line_assigned": True}],
        )
        result = engine.evaluate(context)
        assert result.category_scores["SCOPE"] == 100

    def test_012_time_violations_do_not_affect_scope_score(self):
        """TIME violations don't impact SCOPE category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(scope_defined=True, schedule_within_contract=False))
        assert result.category_scores["SCOPE"] == 100

    def test_013_technical_violations_do_not_affect_scope_score(self):
        """TECHNICAL violations don't impact SCOPE category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(scope_defined=True, technical_consistent=False))
        assert result.category_scores["SCOPE"] == 100

    def test_014_legal_violations_do_not_affect_scope_score(self):
        """LEGAL violations don't impact SCOPE category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(scope_defined=True, legal_compliant=False))
        assert result.category_scores["SCOPE"] == 100

    def test_015_quality_violations_do_not_affect_scope_score(self):
        """QUALITY violations don't impact SCOPE category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(scope_defined=True, quality_standard_met=False))
        assert result.category_scores["SCOPE"] == 100

    def test_016_scope_category_exists_in_result(self):
        """Result always includes SCOPE category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context())
        assert "SCOPE" in result.category_scores
        assert "SCOPE" in result.violations

    def test_017_scope_score_is_integer(self):
        """SCOPE score is always an integer."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(scope_defined=False))
        assert isinstance(result.category_scores["SCOPE"], int)

    def test_018_scope_violations_list_contains_only_strings(self):
        """SCOPE violations are rule ID strings."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(scope_defined=False))
        for violation in result.violations["SCOPE"]:
            assert isinstance(violation, str)


class TestBudgetRules:
    """Refers to Suite ID: TS-UD-COH-RUL-002."""

    def test_001_perfect_budget_match_has_no_violations(self):
        """BUDGET=100 when BOM matches contract price exactly."""
        engine = CoherenceRulesEngine()
        context = _base_context(
            contract_price=1000.0,
            bom_items=[
                {"amount": 600.0, "budget_line_assigned": True},
                {"amount": 400.0, "budget_line_assigned": True},
            ],
        )
        result = engine.evaluate(context)
        assert result.category_scores["BUDGET"] == 100
        assert result.violations["BUDGET"] == []

    def test_002_budget_deviation_below_10_percent_has_no_violations(self):
        """BUDGET=100 when deviation < 10%."""
        engine = CoherenceRulesEngine()
        context = _base_context(
            contract_price=1000.0,
            bom_items=[{"amount": 1090.0, "budget_line_assigned": True}],
        )
        result = engine.evaluate(context)
        assert result.category_scores["BUDGET"] == 100
        assert "R6" not in result.violations["BUDGET"]

    def test_003_budget_deviation_exactly_10_percent_triggers_r6(self):
        """Rule R6 triggered at exactly 10% deviation."""
        engine = CoherenceRulesEngine()
        context = _base_context(
            contract_price=1000.0,
            bom_items=[{"amount": 1100.0, "budget_line_assigned": True}],
        )
        result = engine.evaluate(context)
        assert "R6" in result.violations["BUDGET"]

    def test_004_budget_deviation_over_10_percent_drops_score_to_zero(self):
        """BUDGET=0 when deviation >= 10%."""
        engine = CoherenceRulesEngine()
        context = _base_context(
            contract_price=1000.0,
            bom_items=[{"amount": 1120.0, "budget_line_assigned": True}],
        )
        result = engine.evaluate(context)
        assert result.category_scores["BUDGET"] == 0

    def test_005_budget_underrun_10_percent_triggers_r6(self):
        """Rule R6 triggered for -10% deviation (underrun)."""
        engine = CoherenceRulesEngine()
        context = _base_context(
            contract_price=1000.0,
            bom_items=[{"amount": 900.0, "budget_line_assigned": True}],
        )
        result = engine.evaluate(context)
        assert "R6" in result.violations["BUDGET"]

    def test_006_all_bom_items_assigned_has_no_r15_violation(self):
        """No R15 violation when all BOM items have budget lines."""
        engine = CoherenceRulesEngine()
        context = _base_context(
            bom_items=[
                {"amount": 600.0, "budget_line_assigned": True},
                {"amount": 400.0, "budget_line_assigned": True},
            ],
        )
        result = engine.evaluate(context)
        assert "R15" not in result.violations["BUDGET"]

    def test_007_bom_item_without_budget_line_triggers_r15(self):
        """Rule R15 triggered when BOM item missing budget line."""
        engine = CoherenceRulesEngine()
        context = _base_context(
            bom_items=[
                {"amount": 600.0, "budget_line_assigned": True},
                {"amount": 400.0, "budget_line_assigned": False},
            ],
        )
        result = engine.evaluate(context)
        assert "R15" in result.violations["BUDGET"]

    def test_008_r15_violation_drops_score_to_70(self):
        """BUDGET=70 when R15 triggered."""
        engine = CoherenceRulesEngine()
        context = _base_context(
            bom_items=[{"amount": 1000.0, "budget_line_assigned": False}],
        )
        result = engine.evaluate(context)
        assert result.category_scores["BUDGET"] == 70

    def test_009_empty_bom_with_zero_contract_no_violations(self):
        """Empty BOM with zero contract price has no violations."""
        engine = CoherenceRulesEngine()
        context = _base_context(contract_price=0.0, bom_items=[])
        result = engine.evaluate(context)
        assert result.violations["BUDGET"] == []
        assert result.category_scores["BUDGET"] == 100

    def test_010_zero_contract_price_no_r6_violation(self):
        """R6 not triggered when contract_price=0."""
        engine = CoherenceRulesEngine()
        context = _base_context(
            contract_price=0.0,
            bom_items=[{"amount": 1000.0, "budget_line_assigned": True}],
        )
        result = engine.evaluate(context)
        assert "R6" not in result.violations["BUDGET"]

    def test_011_budget_violations_do_not_affect_scope(self):
        """BUDGET violations isolated from SCOPE category."""
        engine = CoherenceRulesEngine()
        context = _base_context(
            contract_price=1000.0,
            bom_items=[{"amount": 1200.0, "budget_line_assigned": False}],
        )
        result = engine.evaluate(context)
        assert result.category_scores["SCOPE"] == 100

    def test_012_budget_violations_do_not_affect_time(self):
        """BUDGET violations isolated from TIME category."""
        engine = CoherenceRulesEngine()
        context = _base_context(
            contract_price=1000.0,
            bom_items=[{"amount": 1200.0, "budget_line_assigned": False}],
        )
        result = engine.evaluate(context)
        assert result.category_scores["TIME"] == 100

    def test_013_multiple_budget_violations_both_r6_and_r15(self):
        """Both R6 and R15 can trigger simultaneously."""
        engine = CoherenceRulesEngine()
        context = _base_context(
            contract_price=1000.0,
            bom_items=[{"amount": 1200.0, "budget_line_assigned": False}],
        )
        result = engine.evaluate(context)
        assert "R6" in result.violations["BUDGET"]
        assert "R15" in result.violations["BUDGET"]

    def test_014_budget_category_always_in_result(self):
        """Result always includes BUDGET category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context())
        assert "BUDGET" in result.category_scores
        assert "BUDGET" in result.violations

    def test_015_budget_score_is_integer(self):
        """BUDGET score is always an integer."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context())
        assert isinstance(result.category_scores["BUDGET"], int)

    def test_016_bom_item_with_none_amount_treated_as_zero(self):
        """BOM item with amount=None treated as 0."""
        engine = CoherenceRulesEngine()
        context = _base_context(
            contract_price=1000.0,
            bom_items=[
                {"amount": None, "budget_line_assigned": True},
                {"amount": 1000.0, "budget_line_assigned": True},
            ],
        )
        result = engine.evaluate(context)
        assert result.category_scores["BUDGET"] == 100


class TestTimeRules:
    """Refers to Suite ID: TS-UD-COH-RUL-003."""

    def test_001_schedule_within_contract_has_perfect_score(self):
        """TIME=100 when schedule_within_contract=True."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(schedule_within_contract=True))
        assert result.category_scores["TIME"] == 100

    def test_002_schedule_within_contract_has_no_violations(self):
        """No violations when schedule_within_contract=True."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(schedule_within_contract=True))
        assert result.violations["TIME"] == []

    def test_003_schedule_exceeds_contract_triggers_r5(self):
        """Rule R5 triggered when schedule_within_contract=False."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(schedule_within_contract=False))
        assert "R5" in result.violations["TIME"]

    def test_004_schedule_exceeds_contract_drops_score_to_70(self):
        """TIME=70 when schedule_within_contract=False."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(schedule_within_contract=False))
        assert result.category_scores["TIME"] == 70

    def test_005_schedule_violation_has_exactly_one_violation(self):
        """Only R5 violation when schedule_within_contract=False."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(schedule_within_contract=False))
        assert len(result.violations["TIME"]) == 1
        assert result.violations["TIME"][0] == "R5"

    def test_006_time_violation_does_not_affect_scope_score(self):
        """TIME violations isolated from SCOPE category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(schedule_within_contract=False))
        assert result.category_scores["SCOPE"] == 100

    def test_007_time_violation_does_not_affect_budget_score(self):
        """TIME violations isolated from BUDGET category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(schedule_within_contract=False))
        assert result.category_scores["BUDGET"] == 100

    def test_008_time_violation_does_not_affect_technical_score(self):
        """TIME violations isolated from TECHNICAL category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(schedule_within_contract=False))
        assert result.category_scores["TECHNICAL"] == 100

    def test_009_time_violation_does_not_affect_legal_score(self):
        """TIME violations isolated from LEGAL category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(schedule_within_contract=False))
        assert result.category_scores["LEGAL"] == 100

    def test_010_time_violation_does_not_affect_quality_score(self):
        """TIME violations isolated from QUALITY category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(schedule_within_contract=False))
        assert result.category_scores["QUALITY"] == 100

    def test_011_scope_violations_do_not_affect_time_score(self):
        """SCOPE violations don't impact TIME category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(schedule_within_contract=True, scope_defined=False))
        assert result.category_scores["TIME"] == 100

    def test_012_budget_violations_do_not_affect_time_score(self):
        """BUDGET violations don't impact TIME category."""
        engine = CoherenceRulesEngine()
        context = _base_context(
            schedule_within_contract=True,
            contract_price=1000.0,
            bom_items=[{"amount": 1200.0, "budget_line_assigned": True}],
        )
        result = engine.evaluate(context)
        assert result.category_scores["TIME"] == 100

    def test_013_technical_violations_do_not_affect_time_score(self):
        """TECHNICAL violations don't impact TIME category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(schedule_within_contract=True, technical_consistent=False))
        assert result.category_scores["TIME"] == 100

    def test_014_time_category_always_in_result(self):
        """Result always includes TIME category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context())
        assert "TIME" in result.category_scores
        assert "TIME" in result.violations

    def test_015_time_score_is_integer(self):
        """TIME score is always an integer."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(schedule_within_contract=False))
        assert isinstance(result.category_scores["TIME"], int)

    def test_016_time_violations_list_contains_only_strings(self):
        """TIME violations are rule ID strings."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(schedule_within_contract=False))
        for violation in result.violations["TIME"]:
            assert isinstance(violation, str)


class TestTechnicalRules:
    """Refers to Suite ID: TS-UD-COH-RUL-004."""

    def test_001_technical_consistent_has_perfect_score(self):
        """TECHNICAL=100 when technical_consistent=True."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(technical_consistent=True))
        assert result.category_scores["TECHNICAL"] == 100

    def test_002_technical_consistent_has_no_violations(self):
        """No violations when technical_consistent=True."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(technical_consistent=True))
        assert result.violations["TECHNICAL"] == []

    def test_003_technical_inconsistent_triggers_r3(self):
        """Rule R3 triggered when technical_consistent=False."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(technical_consistent=False))
        assert "R3" in result.violations["TECHNICAL"]

    def test_004_technical_inconsistent_drops_score_to_70(self):
        """TECHNICAL=70 when technical_consistent=False."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(technical_consistent=False))
        assert result.category_scores["TECHNICAL"] == 70

    def test_005_technical_violation_has_exactly_one_violation(self):
        """Only R3 violation when technical_consistent=False."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(technical_consistent=False))
        assert len(result.violations["TECHNICAL"]) == 1

    def test_006_technical_violation_isolated_from_scope(self):
        """TECHNICAL violations don't affect SCOPE."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(technical_consistent=False))
        assert result.category_scores["SCOPE"] == 100

    def test_007_technical_violation_isolated_from_budget(self):
        """TECHNICAL violations don't affect BUDGET."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(technical_consistent=False))
        assert result.category_scores["BUDGET"] == 100

    def test_008_technical_violation_isolated_from_time(self):
        """TECHNICAL violations don't affect TIME."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(technical_consistent=False))
        assert result.category_scores["TIME"] == 100

    def test_009_other_violations_do_not_affect_technical(self):
        """Other category violations don't affect TECHNICAL."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(
            _base_context(
                technical_consistent=True,
                scope_defined=False,
                schedule_within_contract=False,
            )
        )
        assert result.category_scores["TECHNICAL"] == 100

    def test_010_technical_category_always_in_result(self):
        """Result always includes TECHNICAL category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context())
        assert "TECHNICAL" in result.category_scores
        assert "TECHNICAL" in result.violations


class TestLegalRules:
    """Refers to Suite ID: TS-UD-COH-RUL-005."""

    def test_001_legal_compliant_has_perfect_score(self):
        """LEGAL=100 when legal_compliant=True."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(legal_compliant=True))
        assert result.category_scores["LEGAL"] == 100

    def test_002_legal_compliant_has_no_violations(self):
        """No violations when legal_compliant=True."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(legal_compliant=True))
        assert result.violations["LEGAL"] == []

    def test_003_legal_non_compliant_triggers_r1(self):
        """Rule R1 triggered when legal_compliant=False."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(legal_compliant=False))
        assert "R1" in result.violations["LEGAL"]

    def test_004_legal_non_compliant_drops_score_to_70(self):
        """LEGAL=70 when legal_compliant=False."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(legal_compliant=False))
        assert result.category_scores["LEGAL"] == 70

    def test_005_legal_violation_has_exactly_one_violation(self):
        """Only R1 violation when legal_compliant=False."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(legal_compliant=False))
        assert len(result.violations["LEGAL"]) == 1

    def test_006_legal_violation_isolated_from_scope(self):
        """LEGAL violations don't affect SCOPE."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(legal_compliant=False))
        assert result.category_scores["SCOPE"] == 100

    def test_007_legal_violation_isolated_from_budget(self):
        """LEGAL violations don't affect BUDGET."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(legal_compliant=False))
        assert result.category_scores["BUDGET"] == 100

    def test_008_legal_violation_isolated_from_time(self):
        """LEGAL violations don't affect TIME."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(legal_compliant=False))
        assert result.category_scores["TIME"] == 100

    def test_009_other_violations_do_not_affect_legal(self):
        """Other category violations don't affect LEGAL."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(
            _base_context(
                legal_compliant=True,
                scope_defined=False,
                technical_consistent=False,
            )
        )
        assert result.category_scores["LEGAL"] == 100

    def test_010_legal_category_always_in_result(self):
        """Result always includes LEGAL category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context())
        assert "LEGAL" in result.category_scores
        assert "LEGAL" in result.violations


class TestQualityRules:
    """Refers to Suite ID: TS-UD-COH-RUL-006."""

    def test_001_quality_standard_met_has_perfect_score(self):
        """QUALITY=100 when quality_standard_met=True."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(quality_standard_met=True))
        assert result.category_scores["QUALITY"] == 100

    def test_002_quality_standard_met_has_no_violations(self):
        """No violations when quality_standard_met=True."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(quality_standard_met=True))
        assert result.violations["QUALITY"] == []

    def test_003_quality_standard_not_met_triggers_r17(self):
        """Rule R17 triggered when quality_standard_met=False."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(quality_standard_met=False))
        assert "R17" in result.violations["QUALITY"]

    def test_004_quality_standard_not_met_drops_score_to_70(self):
        """QUALITY=70 when quality_standard_met=False."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(quality_standard_met=False))
        assert result.category_scores["QUALITY"] == 70

    def test_005_quality_violation_has_exactly_one_violation(self):
        """Only R17 violation when quality_standard_met=False."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(quality_standard_met=False))
        assert len(result.violations["QUALITY"]) == 1

    def test_006_quality_violation_isolated_from_scope(self):
        """QUALITY violations don't affect SCOPE."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(quality_standard_met=False))
        assert result.category_scores["SCOPE"] == 100

    def test_007_quality_violation_isolated_from_budget(self):
        """QUALITY violations don't affect BUDGET."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(quality_standard_met=False))
        assert result.category_scores["BUDGET"] == 100

    def test_008_quality_violation_isolated_from_time(self):
        """QUALITY violations don't affect TIME."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context(quality_standard_met=False))
        assert result.category_scores["TIME"] == 100

    def test_009_other_violations_do_not_affect_quality(self):
        """Other category violations don't affect QUALITY."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(
            _base_context(
                quality_standard_met=True,
                scope_defined=False,
                legal_compliant=False,
            )
        )
        assert result.category_scores["QUALITY"] == 100

    def test_010_quality_category_always_in_result(self):
        """Result always includes QUALITY category."""
        engine = CoherenceRulesEngine()
        result = engine.evaluate(_base_context())
        assert "QUALITY" in result.category_scores
        assert "QUALITY" in result.violations


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
