# tests/coherence/test_v3_models.py
"""
Unit tests for Coherence Engine v0.3 foundation components.

Tests:
- FindingSignal model validation
- impact_to_severity function
- EvaluatorConfig thresholds
- ScoringConfig exponential decay parameters

Location: apps/api/tests/coherence/test_v3_models.py
"""

import math

import pytest
from pydantic import ValidationError

from src.coherence.config import (
    DEFAULT_SCORING_CONFIG,
    ScoringConfig,
    get_scoring_config,
)
from src.coherence.models import (
    FindingSignal,
    impact_to_severity,
)
from src.coherence.rules_engine.config import (
    DEFAULT_CONFIG,
    EvaluatorConfig,
    get_config,
)

# ===========================================
# IMPACT_TO_SEVERITY TESTS
# ===========================================


class TestImpactToSeverity:
    """Tests for the impact_to_severity conversion function."""

    @pytest.mark.parametrize(
        "impact,expected_severity",
        [
            # Critical: >= 0.85
            (1.0, "critical"),
            (0.95, "critical"),
            (0.85, "critical"),
            # High: >= 0.60
            (0.84, "high"),
            (0.70, "high"),
            (0.60, "high"),
            # Medium: >= 0.35
            (0.59, "medium"),
            (0.45, "medium"),
            (0.35, "medium"),
            # Low: >= 0.15
            (0.34, "low"),
            (0.20, "low"),
            (0.15, "low"),
            # Info: < 0.15 (TASK-504: 5-level taxonomy)
            (0.14, "info"),
            (0.10, "info"),
            (0.05, "info"),
            (0.0, "info"),
        ],
    )
    def test_severity_thresholds(self, impact: float, expected_severity: str):
        """Test that impact scores map to correct severity levels (TASK-504: 5-level taxonomy)."""
        result = impact_to_severity(impact)
        assert result == expected_severity

    def test_boundary_critical(self):
        """Test boundary at critical threshold (0.85)."""
        assert impact_to_severity(0.85) == "critical"
        assert impact_to_severity(0.8499) == "high"

    def test_boundary_high(self):
        """Test boundary at high threshold (0.60)."""
        assert impact_to_severity(0.60) == "high"
        assert impact_to_severity(0.5999) == "medium"

    def test_boundary_medium(self):
        """Test boundary at medium threshold (0.35)."""
        assert impact_to_severity(0.35) == "medium"
        assert impact_to_severity(0.3499) == "low"

    def test_boundary_low(self):
        """Test boundary at low threshold (0.15) - TASK-504: 5-level taxonomy."""
        assert impact_to_severity(0.15) == "low"
        assert impact_to_severity(0.1499) == "info"

    def test_all_severity_levels_covered(self):
        """Ensure all 5 severity levels are represented (TASK-504)."""
        severities = {
            impact_to_severity(0.90),  # critical
            impact_to_severity(0.70),  # high
            impact_to_severity(0.45),  # medium
            impact_to_severity(0.25),  # low
            impact_to_severity(0.05),  # info
        }
        assert severities == {"critical", "high", "medium", "low", "info"}


# ===========================================
# FINDINGSIGNAL TESTS
# ===========================================


class TestFindingSignal:
    """Tests for the FindingSignal model."""

    def test_create_valid_finding_signal(self):
        """Test creating a valid FindingSignal."""
        signal = FindingSignal(
            rule_id="DET-BUD-OVERRUN",
            clause_id="CLAUSE-001",
            source="deterministic",
            impact_score=0.75,
            confidence=1.0,
            severity="high",
            category="BUDGET",
            evidence_summary="Budget exceeded by 15%",
            quote="El presupuesto total excede el estimado",
            raw_data={"budget_actual": 115000, "budget_planned": 100000},
        )
        assert signal.rule_id == "DET-BUD-OVERRUN"
        assert signal.impact_score == 0.75
        assert signal.confidence == 1.0
        assert signal.category == "BUDGET"

    def test_impact_score_bounds_lower(self):
        """Test that impact_score cannot be below 0.0."""
        with pytest.raises(ValidationError) as exc_info:
            FindingSignal(
                rule_id="TEST",
                clause_id="CLAUSE-001",
                impact_score=-0.1,
            )
        assert "impact_score" in str(exc_info.value)

    def test_impact_score_bounds_upper(self):
        """Test that impact_score cannot exceed 1.0."""
        with pytest.raises(ValidationError) as exc_info:
            FindingSignal(
                rule_id="TEST",
                clause_id="CLAUSE-001",
                impact_score=1.1,
            )
        assert "impact_score" in str(exc_info.value)

    def test_confidence_bounds_lower(self):
        """Test that confidence cannot be below 0.0."""
        with pytest.raises(ValidationError) as exc_info:
            FindingSignal(
                rule_id="TEST",
                clause_id="CLAUSE-001",
                impact_score=0.5,
                confidence=-0.1,
            )
        assert "confidence" in str(exc_info.value)

    def test_confidence_bounds_upper(self):
        """Test that confidence cannot exceed 1.0."""
        with pytest.raises(ValidationError) as exc_info:
            FindingSignal(
                rule_id="TEST",
                clause_id="CLAUSE-001",
                impact_score=0.5,
                confidence=1.1,
            )
        assert "confidence" in str(exc_info.value)

    def test_default_values(self):
        """Test that defaults are applied correctly."""
        signal = FindingSignal(
            rule_id="DET-TEST",
            clause_id="CLAUSE-001",
            impact_score=0.5,
        )
        assert signal.source == "deterministic"
        assert signal.confidence == 1.0
        assert signal.severity == "medium"
        assert signal.category == "SCOPE"
        assert signal.evidence_summary == ""
        assert signal.quote == ""
        assert signal.raw_data == {}

    def test_llm_source(self):
        """Test creating a finding from LLM source."""
        signal = FindingSignal(
            rule_id="LLM-SCOPE-AMBIG",
            clause_id="CLAUSE-002",
            source="llm",
            impact_score=0.65,
            confidence=0.82,
            severity="high",
            category="SCOPE",
        )
        assert signal.source == "llm"
        assert signal.confidence == 0.82

    @pytest.mark.parametrize(
        "category",
        ["BUDGET", "TIME", "LEGAL", "SCOPE", "TECHNICAL", "QUALITY", "CROSS"],
    )
    def test_valid_categories(self, category: str):
        """Test all valid coherence categories."""
        signal = FindingSignal(
            rule_id="TEST",
            clause_id="CLAUSE-001",
            impact_score=0.5,
            category=category,
        )
        assert signal.category == category


# ===========================================
# EVALUATORCONFIG TESTS
# ===========================================


class TestEvaluatorConfig:
    """Tests for the EvaluatorConfig dataclass."""

    def test_default_config_values(self):
        """Test that DEFAULT_CONFIG has expected values."""
        config = DEFAULT_CONFIG

        # Budget thresholds
        assert config.budget_overrun_warning_pct == 0.05
        assert config.budget_overrun_critical_pct == 0.25
        assert config.budget_contingency_min_pct == 0.05
        assert config.budget_contingency_max_pct == 0.20

        # Time thresholds
        assert config.schedule_milestone_gap_max_days == 90
        assert config.schedule_buffer_min_days == 7

        # Legal thresholds
        assert config.contract_review_warning_days == 365
        assert config.penalty_cap_max_pct == 0.15

    def test_custom_config_override(self):
        """Test creating config with overrides."""
        config = EvaluatorConfig(
            budget_overrun_warning_pct=0.10,
            budget_overrun_critical_pct=0.30,
        )
        assert config.budget_overrun_warning_pct == 0.10
        assert config.budget_overrun_critical_pct == 0.30
        # Other values should be defaults
        assert config.budget_contingency_min_pct == 0.05

    def test_get_config_helper(self):
        """Test the get_config helper function."""
        config = get_config(budget_overrun_warning_pct=0.08)
        assert config.budget_overrun_warning_pct == 0.08
        assert config.budget_overrun_critical_pct == 0.25  # default

    def test_threshold_relationships(self):
        """Test that threshold relationships are sensible."""
        config = DEFAULT_CONFIG

        # Warning should be less than critical
        assert config.budget_overrun_warning_pct < config.budget_overrun_critical_pct

        # Contingency min should be less than max
        assert config.budget_contingency_min_pct < config.budget_contingency_max_pct

        # Retention min should be less than max
        assert config.retention_min_pct < config.retention_max_pct

        # Notice period min should be less than max
        assert config.notice_period_min_days < config.notice_period_max_days

        # Warranty min should be less than max
        assert config.warranty_min_months < config.warranty_max_months


# ===========================================
# SCORINGCONFIG TESTS
# ===========================================


class TestScoringConfig:
    """Tests for the ScoringConfig dataclass."""

    def test_default_config_values(self):
        """Test that DEFAULT_SCORING_CONFIG has expected values."""
        config = DEFAULT_SCORING_CONFIG

        # λ=1.5 calibrated for target score curve (CE-27)
        assert config.decay_lambda == 1.5
        assert config.min_score == 5.0
        assert config.max_score == 97.0
        assert config.scope_normalization_enabled is True
        assert config.scope_normalization_k == 0.12
        assert config.llm_weight_factor == 0.85
        assert config.llm_confidence_threshold == 0.60

    def test_severity_weights_values(self):
        """Test that default severity weights have expected values (TASK-504: 5-level taxonomy)."""
        config = DEFAULT_SCORING_CONFIG
        assert config.severity_weights["critical"] == 1.0
        assert config.severity_weights["high"] == 0.7
        assert config.severity_weights["medium"] == 0.4
        assert config.severity_weights["low"] == 0.15
        assert config.severity_weights["info"] == 0.05

    def test_all_severity_levels_have_weights(self):
        """Test that all 5 severity levels have weights defined (TASK-504)."""
        config = DEFAULT_SCORING_CONFIG
        expected_severities = {"critical", "high", "medium", "low", "info"}
        assert set(config.severity_weights.keys()) == expected_severities

    def test_all_categories_have_weights(self):
        """Test that all 7 categories have weights defined."""
        config = DEFAULT_SCORING_CONFIG
        expected_categories = {"BUDGET", "TIME", "LEGAL", "SCOPE", "TECHNICAL", "QUALITY", "CROSS"}
        assert set(config.category_weights.keys()) == expected_categories

    def test_get_normalized_weights(self):
        """Test weight normalization."""
        config = ScoringConfig(
            category_weights={
                "BUDGET": 2.0,
                "TIME": 1.0,
                "LEGAL": 2.0,
                "SCOPE": 1.0,
                "TECHNICAL": 1.0,
                "QUALITY": 1.0,
                "CROSS": 0.5,
            }
        )
        normalized = config.get_normalized_weights()
        total = sum(normalized.values())
        assert abs(total - 1.0) < 0.001

    def test_get_normalized_weights_zero_sum(self):
        """Test weight normalization with zero sum (edge case)."""
        config = ScoringConfig(
            category_weights={
                "BUDGET": 0.0,
                "TIME": 0.0,
                "LEGAL": 0.0,
                "SCOPE": 0.0,
                "TECHNICAL": 0.0,
                "QUALITY": 0.0,
                "CROSS": 0.0,
            }
        )
        normalized = config.get_normalized_weights()
        # Should fallback to equal weights
        assert len(normalized) == 7
        assert abs(sum(normalized.values()) - 1.0) < 0.001

    def test_compute_scope_factor_disabled(self):
        """Test scope factor when normalization is disabled."""
        config = ScoringConfig(scope_normalization_enabled=False)
        assert config.compute_scope_factor(100) == 1.0
        assert config.compute_scope_factor(1000) == 1.0

    def test_compute_scope_factor_small_project(self):
        """Test scope factor for small projects."""
        # Default scope_normalization_k=0.12
        # scope_factor = max(1.0, clauses * k)
        config = ScoringConfig()
        # Small project (8 clauses * 0.12 = 0.96 < 1.0) → factor = 1.0
        factor = config.compute_scope_factor(8)
        assert factor == 1.0

    def test_compute_scope_factor_large_project(self):
        """Test scope factor for large projects."""
        # Default scope_normalization_k=0.12
        config = ScoringConfig()
        # Large project: 100 * 0.12 = 12.0
        factor_100 = config.compute_scope_factor(100)
        # Very large: 200 * 0.12 = 24.0
        factor_200 = config.compute_scope_factor(200)
        assert factor_100 == 12.0
        assert factor_200 == 24.0
        assert factor_200 > factor_100

    def test_compute_scope_factor_zero_clauses(self):
        """Test scope factor with zero clauses (edge case)."""
        config = DEFAULT_SCORING_CONFIG
        factor = config.compute_scope_factor(0)
        assert factor == 1.0

    def test_compute_scope_factor_negative_clauses(self):
        """Test scope factor with negative clauses (edge case)."""
        config = DEFAULT_SCORING_CONFIG
        factor = config.compute_scope_factor(-10)
        assert factor == 1.0

    def test_get_scoring_config_helper(self):
        """Test the get_scoring_config helper function."""
        config = get_scoring_config(decay_lambda=0.08, min_score=10.0)
        assert config.decay_lambda == 0.08
        assert config.min_score == 10.0
        assert config.max_score == 97.0  # default

    def test_severity_thresholds_order(self):
        """Test that severity thresholds are in descending order."""
        config = DEFAULT_SCORING_CONFIG
        assert config.critical_threshold > config.high_threshold
        assert config.high_threshold > config.medium_threshold

    def test_severity_thresholds_match_function(self):
        """Test that config thresholds match impact_to_severity function."""
        config = DEFAULT_SCORING_CONFIG
        # These should match the hardcoded values in impact_to_severity
        assert config.critical_threshold == 0.85
        assert config.high_threshold == 0.60
        assert config.medium_threshold == 0.35


# ===========================================
# EXPONENTIAL DECAY FORMULA TESTS
# ===========================================


class TestExponentialDecayFormula:
    """Tests for the exponential decay scoring formula concept."""

    def test_formula_no_penalties(self):
        """Test score = 100 when no penalties."""
        lambda_val = 0.05
        weighted_penalty_density = 0.0
        score = 100 * math.exp(-lambda_val * weighted_penalty_density)
        assert score == 100.0

    def test_formula_small_penalty(self):
        """Test score with small penalty density."""
        lambda_val = 0.05
        weighted_penalty_density = 1.0
        score = 100 * math.exp(-lambda_val * weighted_penalty_density)
        # Should be close to 95 (100 * e^-0.05 ≈ 95.12)
        assert 94 < score < 96

    def test_formula_medium_penalty(self):
        """Test score with medium penalty density."""
        lambda_val = 0.05
        weighted_penalty_density = 10.0
        score = 100 * math.exp(-lambda_val * weighted_penalty_density)
        # Should be around 60 (100 * e^-0.5 ≈ 60.65)
        assert 59 < score < 62

    def test_formula_high_penalty(self):
        """Test score with high penalty density."""
        lambda_val = 0.05
        weighted_penalty_density = 50.0
        score = 100 * math.exp(-lambda_val * weighted_penalty_density)
        # Should be around 8 (100 * e^-2.5 ≈ 8.21)
        assert 7 < score < 10

    def test_formula_extreme_penalty(self):
        """Test score with extreme penalty density."""
        lambda_val = 0.05
        weighted_penalty_density = 100.0
        score = 100 * math.exp(-lambda_val * weighted_penalty_density)
        # Should be very low (100 * e^-5 ≈ 0.67)
        assert 0 < score < 2

    def test_lambda_sensitivity(self):
        """Test that higher lambda causes faster decay."""
        weighted_penalty_density = 10.0

        score_low_lambda = 100 * math.exp(-0.03 * weighted_penalty_density)
        score_mid_lambda = 100 * math.exp(-0.05 * weighted_penalty_density)
        score_high_lambda = 100 * math.exp(-0.08 * weighted_penalty_density)

        assert score_low_lambda > score_mid_lambda > score_high_lambda

    def test_formula_with_scope_factor(self):
        """Test score calculation with scope factor normalization."""
        lambda_val = 0.05
        raw_penalties = 10.0
        scope_factor = 2.0  # Large project

        effective_density = raw_penalties / scope_factor
        score = 100 * math.exp(-lambda_val * effective_density)

        # With scope_factor=2, effective density is halved
        # score ≈ 100 * e^(-0.05 * 5) ≈ 77.88
        assert 76 < score < 80


# ===========================================
# RULEEVALUATOR BASE CLASS TESTS
# ===========================================


class TestRuleEvaluatorBase:
    """Tests for the RuleEvaluator base class v0.3 features."""

    def test_class_attributes_exist(self):
        """Test that class-level attributes are defined."""
        from src.coherence.rules_engine.base import RuleEvaluator

        assert hasattr(RuleEvaluator, "rule_id")
        assert hasattr(RuleEvaluator, "rule_name")
        assert hasattr(RuleEvaluator, "category")

    def test_default_class_attributes(self):
        """Test default values for class attributes."""
        from src.coherence.rules_engine.base import RuleEvaluator

        assert RuleEvaluator.rule_id == "UNKNOWN"
        assert RuleEvaluator.rule_name == "Unknown Rule"
        assert RuleEvaluator.category == "SCOPE"

    def test_concrete_evaluator_with_evaluate_v3(self):
        """Test concrete evaluator implementing evaluate_v3."""
        from src.coherence.models import Clause
        from src.coherence.rules_engine.base import Finding, RuleEvaluator

        class TestBudgetEvaluator(RuleEvaluator):
            rule_id = "DET-BUD-TEST"
            rule_name = "Test Budget Rule"
            category = "BUDGET"

            def evaluate(self, clause: Clause) -> Finding | None:
                if clause.data.get("over_budget"):
                    return Finding(
                        triggered_clause=clause,
                        raw_data={"overrun_pct": 0.15},
                    )
                return None

        evaluator = TestBudgetEvaluator()
        clause = Clause(
            id="CLAUSE-001",
            text="Budget exceeded",
            data={"over_budget": True},
        )

        # Test evaluate_v3 wrapper
        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert signal.rule_id == "DET-BUD-TEST"
        assert signal.category == "BUDGET"
        assert signal.source == "deterministic"
        assert signal.confidence == 1.0
        assert signal.impact_score == 0.50  # Default for legacy findings

    def test_evaluate_v3_returns_none_when_no_finding(self):
        """Test evaluate_v3 returns None when no issue found."""
        from src.coherence.models import Clause
        from src.coherence.rules_engine.base import Finding, RuleEvaluator

        class TestEvaluator(RuleEvaluator):
            rule_id = "DET-TEST"
            rule_name = "Test Rule"
            category = "SCOPE"

            def evaluate(self, clause: Clause) -> Finding | None:
                return None  # No issue found

        evaluator = TestEvaluator()
        clause = Clause(id="CLAUSE-001", text="All good", data={})

        signal = evaluator.evaluate_v3(clause)
        assert signal is None

    def test_evaluate_v3_preserves_raw_data(self):
        """Test that evaluate_v3 preserves raw_data from Finding."""
        from src.coherence.models import Clause
        from src.coherence.rules_engine.base import Finding, RuleEvaluator

        class TestEvaluator(RuleEvaluator):
            rule_id = "DET-TEST"
            rule_name = "Test Rule"
            category = "TECHNICAL"

            def evaluate(self, clause: Clause) -> Finding | None:
                return Finding(
                    triggered_clause=clause,
                    raw_data={"key": "value", "count": 42},
                )

        evaluator = TestEvaluator()
        clause = Clause(id="CLAUSE-001", text="Test text", data={})

        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert signal.raw_data == {"key": "value", "count": 42}

    def test_evaluate_v3_truncates_long_quote(self):
        """Test that evaluate_v3 truncates long clause text for quote."""
        from src.coherence.models import Clause
        from src.coherence.rules_engine.base import Finding, RuleEvaluator

        class TestEvaluator(RuleEvaluator):
            rule_id = "DET-TEST"
            rule_name = "Test Rule"
            category = "LEGAL"

            def evaluate(self, clause: Clause) -> Finding | None:
                return Finding(triggered_clause=clause, raw_data={})

        evaluator = TestEvaluator()
        long_text = "A" * 500  # 500 characters
        clause = Clause(id="CLAUSE-001", text=long_text, data={})

        signal = evaluator.evaluate_v3(clause)
        assert signal is not None
        assert len(signal.quote) == 200  # Truncated to 200 chars

    def test_custom_evaluate_v3_override(self):
        """Test that subclasses can override evaluate_v3 for continuous scoring."""
        from src.coherence.models import Clause, FindingSignal
        from src.coherence.rules_engine.base import Finding, RuleEvaluator

        class ContinuousBudgetEvaluator(RuleEvaluator):
            rule_id = "DET-BUD-OVERRUN"
            rule_name = "Budget Overrun Detector"
            category = "BUDGET"

            def evaluate(self, clause: Clause) -> Finding | None:
                # Legacy method - not used when evaluate_v3 is overridden
                raise NotImplementedError("Use evaluate_v3")

            def evaluate_v3(self, clause: Clause) -> FindingSignal | None:
                overrun_pct = clause.data.get("overrun_pct", 0)
                if overrun_pct <= 0.05:
                    return None

                # Continuous scoring: higher overrun = higher impact
                impact = min(1.0, overrun_pct / 0.25)  # Normalize to 0.25 = 100%

                return FindingSignal(
                    rule_id=self.rule_id,
                    clause_id=clause.id,
                    source="deterministic",
                    impact_score=impact,
                    confidence=1.0,
                    severity="high" if impact >= 0.6 else "medium",
                    category=self.category,
                    evidence_summary=f"Budget overrun: {overrun_pct:.1%}",
                    quote=clause.text[:200],
                    raw_data={"overrun_pct": overrun_pct},
                )

        evaluator = ContinuousBudgetEvaluator()

        # Test with 10% overrun
        clause_10 = Clause(
            id="CLAUSE-001",
            text="Budget section",
            data={"overrun_pct": 0.10},
        )
        signal_10 = evaluator.evaluate_v3(clause_10)
        assert signal_10 is not None
        assert signal_10.impact_score == 0.4  # 0.10 / 0.25 = 0.4

        # Test with 20% overrun
        clause_20 = Clause(
            id="CLAUSE-002",
            text="Budget section",
            data={"overrun_pct": 0.20},
        )
        signal_20 = evaluator.evaluate_v3(clause_20)
        assert signal_20 is not None
        assert signal_20.impact_score == 0.8  # 0.20 / 0.25 = 0.8

        # Test with no overrun
        clause_ok = Clause(
            id="CLAUSE-003",
            text="Budget section",
            data={"overrun_pct": 0.03},
        )
        signal_ok = evaluator.evaluate_v3(clause_ok)
        assert signal_ok is None  # Below threshold
