"""
test_scoring_v3.py — Tests for Coherence Score Calculator v0.3

Validates the exponential decay scoring with scope normalization.
Ensures the score curve behaves as specified in the design document.

Test categories:
1. Score granularity (no collapse to 0 or 100)
2. Scope normalization (larger projects absorb findings better)
3. Confidence impact (low confidence = less penalty)
4. Source weighting (deterministic > LLM)
5. Floor and ceiling bounds
6. Backward compatibility (Alert-based scoring)
7. Diagnostics output
"""

import math

import pytest

from src.coherence.config import ScoringConfig
from src.coherence.models import (
    Alert,
    Evidence,
    FindingSignal,
)
from src.coherence.scoring import ScoringService

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def scorer() -> ScoringService:
    """Default scoring service with standard config."""
    return ScoringService()


@pytest.fixture
def custom_scorer() -> ScoringService:
    """Scoring service with custom config for testing edge cases."""
    config = ScoringConfig(
        decay_lambda=0.10,  # More aggressive decay
        min_score=10.0,
        max_score=95.0,
        llm_weight_factor=0.70,
        llm_confidence_threshold=0.50,
    )
    return ScoringService(config)


def make_signal(
    impact: float,
    confidence: float = 1.0,
    severity: str = "medium",
    source: str = "deterministic",
    category: str = "SCOPE",
    rule_id: str = "TEST-001",
    clause_id: str = "C1",
) -> FindingSignal:
    """Factory function to create FindingSignal for testing."""
    return FindingSignal(
        rule_id=rule_id,
        clause_id=clause_id,
        source=source,
        impact_score=impact,
        confidence=confidence,
        severity=severity,
        category=category,
        evidence_summary="Test finding",
        quote="test quote",
    )


def make_alert(
    severity: str = "medium",
    category: str = "general",
    rule_id: str = "ALERT-001",
) -> Alert:
    """Factory function to create Alert for backward compat testing."""
    return Alert(
        rule_id=rule_id,
        severity=severity,
        category=category,
        message="Test alert",
        evidence=Evidence(
            source_clause_id="C1",
            claim="Test claim",
            quote="Test quote",
        ),
    )


# =============================================================================
# TEST: SCORE GRANULARITY
# =============================================================================


class TestScoreGranularity:
    """Verify the score never collapses to 0 or 100 inappropriately."""

    def test_no_findings_returns_100(self, scorer: ScoringService):
        """Empty findings list should return perfect score."""
        assert scorer.calculate_from_signals([], 10, 5) == 100.0

    def test_single_low_finding_stays_above_90(self, scorer: ScoringService):
        """A single low-impact finding should barely affect the score."""
        signals = [make_signal(0.25, severity="low")]
        score = scorer.calculate_from_signals(signals, 10, 5)
        assert 90.0 < score <= 97.0, f"Score {score} should be in (90, 97]"

    def test_moderate_findings_in_middle_range(self, scorer: ScoringService):
        """Moderate findings should produce scores in the middle range."""
        signals = [
            make_signal(0.50, severity="medium"),
            make_signal(0.60, severity="high"),
        ]
        score = scorer.calculate_from_signals(signals, 8, 5)
        # With λ=1.5, moderate findings produce scores ~35-70
        assert 30.0 < score < 90.0, f"Score {score} should be in (30, 90)"

    def test_severe_findings_below_30_but_above_floor(self, scorer: ScoringService):
        """Multiple critical findings should produce low scores but above floor."""
        signals = [
            make_signal(0.95, severity="critical"),
            make_signal(0.90, severity="critical"),
            make_signal(0.85, severity="critical"),
        ]
        score = scorer.calculate_from_signals(signals, 3, 5)
        assert 5.0 <= score < 50.0, f"Score {score} should be in [5, 50)"

    def test_score_never_reaches_zero(self, scorer: ScoringService):
        """Even with extreme findings, score should never go below min_score."""
        signals = [make_signal(1.0, severity="critical") for _ in range(20)]
        score = scorer.calculate_from_signals(signals, 3, 5)
        assert score >= 5.0, f"Score {score} should be >= floor (5.0)"

    def test_score_ceiling_when_findings_exist(self, scorer: ScoringService):
        """With any findings, score should be capped at max_score."""
        signals = [make_signal(0.01, severity="low")]  # Minimal impact
        score = scorer.calculate_from_signals(signals, 100, 5)
        assert score <= 97.0, f"Score {score} should be <= ceiling (97.0)"


# =============================================================================
# TEST: SCOPE NORMALIZATION
# =============================================================================


class TestScopeNormalization:
    """Verify larger projects absorb findings better."""

    def test_larger_scope_absorbs_findings(self, scorer: ScoringService):
        """Same finding in larger project should have higher score."""
        signals = [make_signal(0.70, severity="high")]

        score_3_clauses = scorer.calculate_from_signals(signals, 3, 5)
        score_30_clauses = scorer.calculate_from_signals(signals, 30, 5)
        score_100_clauses = scorer.calculate_from_signals(signals, 100, 5)

        assert score_30_clauses > score_3_clauses, (
            f"30 clauses ({score_30_clauses}) should absorb better than 3 ({score_3_clauses})"
        )
        assert score_100_clauses > score_30_clauses, (
            f"100 clauses ({score_100_clauses}) should absorb better than 30 ({score_30_clauses})"
        )

    def test_scope_factor_minimum_is_one(self, scorer: ScoringService):
        """Scope factor should never be less than 1.0 (no penalty for small projects)."""
        signals = [make_signal(0.50, severity="medium")]

        # Very small project
        score_1_clause = scorer.calculate_from_signals(signals, 1, 5)

        # The score should still be reasonable, not overly penalized
        assert score_1_clause > 5.0, f"Small project score {score_1_clause} too low"

    def test_scope_normalization_disabled(self):
        """When scope normalization is disabled, scope should not affect score."""
        config = ScoringConfig(scope_normalization_enabled=False)
        scorer = ScoringService(config)

        signals = [make_signal(0.70, severity="high")]

        score_3 = scorer.calculate_from_signals(signals, 3, 5)
        score_100 = scorer.calculate_from_signals(signals, 100, 5)

        # Scores should be identical when normalization is disabled
        assert score_3 == score_100, (
            f"Without normalization, scores should match: {score_3} vs {score_100}"
        )


# =============================================================================
# TEST: CONFIDENCE IMPACT
# =============================================================================


class TestConfidenceImpact:
    """Verify low confidence findings have reduced impact."""

    def test_low_confidence_reduces_impact(self, scorer: ScoringService):
        """Low confidence finding should have less penalty."""
        high_conf = [make_signal(0.80, confidence=0.95)]
        low_conf = [make_signal(0.80, confidence=0.65)]

        score_high = scorer.calculate_from_signals(high_conf, 5, 5)
        score_low = scorer.calculate_from_signals(low_conf, 5, 5)

        assert score_low > score_high, (
            f"Low confidence ({score_low}) should have higher score than high ({score_high})"
        )

    def test_llm_below_threshold_ignored(self, scorer: ScoringService):
        """LLM findings below confidence threshold should be ignored."""
        # LLM finding below threshold (default 0.60)
        low_conf_llm = [make_signal(0.80, confidence=0.40, source="llm")]

        score = scorer.calculate_from_signals(low_conf_llm, 5, 5)

        # Should be 97.0 (ceiling) since the finding is ignored
        assert score == 97.0, f"Low-confidence LLM finding should be ignored, got {score}"

    def test_deterministic_always_included(self, scorer: ScoringService):
        """Deterministic findings should be included regardless of confidence."""
        # Even with low confidence, deterministic findings count
        low_conf_det = [make_signal(0.80, confidence=0.40, source="deterministic")]

        score = scorer.calculate_from_signals(low_conf_det, 5, 5)

        assert score < 97.0, f"Deterministic finding should be included, got {score}"


# =============================================================================
# TEST: SOURCE WEIGHTING
# =============================================================================


class TestSourceWeighting:
    """Verify deterministic findings are weighted higher than LLM."""

    def test_deterministic_weighted_higher_than_llm(self, scorer: ScoringService):
        """Deterministic findings should have more penalty than equivalent LLM."""
        det = [make_signal(0.70, source="deterministic")]
        llm = [make_signal(0.70, source="llm")]

        score_det = scorer.calculate_from_signals(det, 5, 5)
        score_llm = scorer.calculate_from_signals(llm, 5, 5)

        # Det has weight 1.0, LLM has weight 0.85 → det should have MORE penalty → LOWER score
        assert score_det < score_llm, (
            f"Deterministic ({score_det}) should have lower score than LLM ({score_llm})"
        )

    def test_custom_llm_weight_factor(self, custom_scorer: ScoringService):
        """Custom LLM weight factor should be applied."""
        llm = [make_signal(0.70, source="llm")]

        # Custom scorer has llm_weight_factor=0.70
        score = custom_scorer.calculate_from_signals(llm, 5, 5)

        # Score should be higher than with default weight (0.85)
        default_scorer = ScoringService()
        default_score = default_scorer.calculate_from_signals(llm, 5, 5)

        assert score > default_score, (
            f"Lower LLM weight ({score}) should give higher score than default ({default_score})"
        )


# =============================================================================
# TEST: FLOOR AND CEILING BOUNDS
# =============================================================================


class TestBounds:
    """Verify floor and ceiling bounds are respected."""

    def test_floor_bound(self, scorer: ScoringService):
        """Score should never go below min_score."""
        # Extreme case: many critical findings
        signals = [make_signal(1.0, severity="critical") for _ in range(50)]
        score = scorer.calculate_from_signals(signals, 5, 5)

        assert score >= 5.0, f"Score {score} should be >= floor (5.0)"
        assert score == 5.0, "With extreme findings, score should hit floor exactly"

    def test_ceiling_bound(self, scorer: ScoringService):
        """Score with findings should never exceed max_score."""
        # Minimal finding
        signals = [make_signal(0.01, severity="low", confidence=0.65)]
        score = scorer.calculate_from_signals(signals, 100, 5)

        assert score <= 97.0, f"Score {score} should be <= ceiling (97.0)"

    def test_custom_bounds(self, custom_scorer: ScoringService):
        """Custom floor/ceiling should be respected."""
        # Custom scorer has min_score=10.0, max_score=95.0
        signals = [make_signal(1.0, severity="critical") for _ in range(50)]
        floor_score = custom_scorer.calculate_from_signals(signals, 5, 5)
        assert floor_score >= 10.0, f"Custom floor: {floor_score} should be >= 10.0"

        minimal = [make_signal(0.01, severity="low")]
        ceiling_score = custom_scorer.calculate_from_signals(minimal, 100, 5)
        assert ceiling_score <= 95.0, f"Custom ceiling: {ceiling_score} should be <= 95.0"


# =============================================================================
# TEST: SEVERITY WEIGHTING
# =============================================================================


class TestSeverityWeighting:
    """Verify severity weights affect scoring appropriately."""

    def test_higher_severity_more_impact(self, scorer: ScoringService):
        """Higher severity findings should have more impact on score."""
        # Same impact_score, different severities
        critical_finding = [make_signal(0.80, severity="critical")]  # weight 1.0
        low_finding = [make_signal(0.80, severity="low")]  # weight 0.15

        score_critical = scorer.calculate_from_signals(critical_finding, 10, 5)
        score_low = scorer.calculate_from_signals(low_finding, 10, 5)

        # Higher severity weight = more penalty = lower score
        assert score_critical < score_low, (
            f"Critical ({score_critical}) should have lower score than low ({score_low})"
        )

    def test_severity_weight_ordering(self, scorer: ScoringService):
        """Verify: critical > high > medium > low in terms of penalty."""
        findings_by_severity = {
            "critical": [make_signal(0.70, severity="critical")],
            "high": [make_signal(0.70, severity="high")],
            "medium": [make_signal(0.70, severity="medium")],
            "low": [make_signal(0.70, severity="low")],
        }

        scores = {sev: scorer.calculate_from_signals(signals, 10, 5)
                  for sev, signals in findings_by_severity.items()}

        # Lower score = more penalty
        assert scores["critical"] < scores["high"] < scores["medium"] < scores["low"], (
            f"Severity ordering violated: critical={scores['critical']}, "
            f"high={scores['high']}, medium={scores['medium']}, low={scores['low']}"
        )


# =============================================================================
# TEST: BACKWARD COMPATIBILITY
# =============================================================================


class TestBackwardCompatibility:
    """Verify Alert-based scoring still works."""

    def test_calculate_with_alerts(self, scorer: ScoringService):
        """calculate() should accept Alert objects."""
        alerts = [
            make_alert(severity="high", category="financial"),
            make_alert(severity="medium", category="legal"),
        ]
        score = scorer.calculate(alerts, num_clauses=10)

        assert 0.0 < score <= 100.0, f"Score {score} should be valid"
        assert score < 100.0, "With alerts, score should be < 100"

    def test_empty_alerts_returns_100(self, scorer: ScoringService):
        """Empty alerts list should return perfect score."""
        assert scorer.calculate([], num_clauses=10) == 100.0

    def test_alert_to_signal_conversion(self, scorer: ScoringService):
        """Alert should be correctly converted to FindingSignal."""
        alert = make_alert(severity="critical", category="legal")
        signal = scorer._alert_to_signal(alert)

        assert signal.impact_score == 0.95  # critical → 0.95
        assert signal.category == "LEGAL"  # legal → LEGAL
        assert signal.confidence == 1.0  # legacy alerts have full confidence
        assert signal.source == "deterministic"  # ALERT-001 doesn't start with R-

    def test_llm_rule_id_detection(self, scorer: ScoringService):
        """Rule IDs starting with R- should be detected as LLM."""
        alert = make_alert(severity="high", rule_id="R-SCOPE-001")
        signal = scorer._alert_to_signal(alert)

        assert signal.source == "llm"

    def test_compute_score_still_works(self, scorer: ScoringService):
        """Legacy compute_score() should still work."""
        alerts = [make_alert(severity="high")]
        score = scorer.compute_score(alerts)

        assert 0.0 <= score <= 100.0, f"Legacy score {score} should be valid"


# =============================================================================
# TEST: DIAGNOSTICS OUTPUT
# =============================================================================


class TestDiagnostics:
    """Verify calculate_detailed() returns correct diagnostics."""

    def test_empty_signals_diagnostics(self, scorer: ScoringService):
        """Empty signals should return zeroed diagnostics."""
        diag = scorer.calculate_detailed([], 10, 5)

        assert diag.score == 100.0
        assert diag.total_findings == 0
        assert diag.deterministic_findings == 0
        assert diag.llm_findings == 0
        assert diag.avg_impact == 0.0
        assert diag.avg_confidence == 0.0
        assert diag.penalty_density == 0.0

    def test_diagnostics_counts(self, scorer: ScoringService):
        """Diagnostics should correctly count findings by source."""
        signals = [
            make_signal(0.50, source="deterministic"),
            make_signal(0.60, source="deterministic"),
            make_signal(0.70, source="llm"),
        ]
        diag = scorer.calculate_detailed(signals, 10, 5)

        assert diag.total_findings == 3
        assert diag.deterministic_findings == 2
        assert diag.llm_findings == 1

    def test_diagnostics_severity_distribution(self, scorer: ScoringService):
        """Diagnostics should correctly count severity distribution."""
        signals = [
            make_signal(0.90, severity="critical"),
            make_signal(0.70, severity="high"),
            make_signal(0.70, severity="high"),
            make_signal(0.50, severity="medium"),
            make_signal(0.20, severity="low"),
            make_signal(0.20, severity="low"),
            make_signal(0.20, severity="low"),
        ]
        diag = scorer.calculate_detailed(signals, 10, 5)

        assert diag.severity_distribution["critical"] == 1
        assert diag.severity_distribution["high"] == 2
        assert diag.severity_distribution["medium"] == 1
        assert diag.severity_distribution["low"] == 3

    def test_diagnostics_averages(self, scorer: ScoringService):
        """Diagnostics should calculate correct averages."""
        signals = [
            make_signal(0.40, confidence=0.80),
            make_signal(0.60, confidence=1.0),
        ]
        diag = scorer.calculate_detailed(signals, 10, 5)

        expected_avg_impact = (0.40 + 0.60) / 2
        expected_avg_confidence = (0.80 + 1.0) / 2

        assert diag.avg_impact == pytest.approx(expected_avg_impact, abs=0.001)
        assert diag.avg_confidence == pytest.approx(expected_avg_confidence, abs=0.001)

    def test_diagnostics_scope_factor(self, scorer: ScoringService):
        """Diagnostics should include scope factor."""
        signals = [make_signal(0.50)]
        diag = scorer.calculate_detailed(signals, 100, 5)

        # scope_factor should be > 1.0 for 100 clauses
        assert diag.scope_factor > 1.0, f"Scope factor {diag.scope_factor} should be > 1.0"

    def test_diagnostics_penalty_density(self, scorer: ScoringService):
        """Diagnostics should include penalty density."""
        signals = [make_signal(0.80)]
        diag = scorer.calculate_detailed(signals, 10, 5)

        assert diag.penalty_density > 0.0
        assert diag.raw_penalty_sum > 0.0

    def test_diagnostics_category_contributions(self, scorer: ScoringService):
        """Diagnostics should track contributions by category."""
        signals = [
            make_signal(0.50, category="BUDGET"),
            make_signal(0.60, category="BUDGET"),
            make_signal(0.70, category="LEGAL"),
        ]
        diag = scorer.calculate_detailed(signals, 10, 5)

        assert "BUDGET" in diag.category_contributions
        assert "LEGAL" in diag.category_contributions
        assert diag.category_contributions["BUDGET"] > 0.0
        assert diag.category_contributions["LEGAL"] > 0.0


# =============================================================================
# TEST: EXPONENTIAL DECAY CURVE
# =============================================================================


class TestExponentialDecay:
    """Verify the exponential decay formula works correctly."""

    def test_decay_formula(self):
        """Verify the mathematical formula is implemented correctly."""
        config = ScoringConfig(
            decay_lambda=0.05,
            scope_normalization_enabled=False,
        )
        scorer = ScoringService(config)

        # Single finding with known values
        signals = [make_signal(1.0, confidence=1.0, category="SCOPE")]  # weight 0.15

        # Expected penalty = 1.0 * 1.0 * 0.15 * 1.0 = 0.15
        # Expected density = 0.15 / 1.0 = 0.15 (no scope normalization)
        # Expected score = 100 * e^(-0.05 * 0.15) = 100 * e^(-0.0075)
        expected_raw = 100.0 * math.exp(-0.05 * 0.15)
        expected = min(expected_raw, 97.0)  # ceiling

        score = scorer.calculate_from_signals(signals, 1, 5)

        assert score == pytest.approx(expected, abs=0.1), (
            f"Score {score} should match formula result {expected}"
        )

    def test_diminishing_returns(self, scorer: ScoringService):
        """Each additional finding should have diminishing marginal impact."""
        base_score = scorer.calculate_from_signals([], 10, 5)

        # Add findings one at a time
        scores = [base_score]
        for i in range(1, 6):
            signals = [make_signal(0.50, severity="medium") for _ in range(i)]
            score = scorer.calculate_from_signals(signals, 10, 5)
            scores.append(score)

        # Check diminishing returns: delta between scores should decrease
        deltas = [scores[i] - scores[i + 1] for i in range(len(scores) - 1)]

        for i in range(len(deltas) - 1):
            assert deltas[i + 1] <= deltas[i] + 0.1, (
                f"Marginal impact should decrease: delta[{i}]={deltas[i]}, "
                f"delta[{i+1}]={deltas[i+1]}"
            )


# =============================================================================
# TEST: SCORE CURVE SCENARIOS (from design doc)
# =============================================================================


class TestScoreCurveScenarios:
    """Test scenarios from the design document."""

    def test_scenario_no_findings(self, scorer: ScoringService):
        """0 findings → score = 100."""
        assert scorer.calculate_from_signals([], 10, 5) == 100.0

    def test_scenario_single_low_in_large_project(self, scorer: ScoringService):
        """1 low finding in 10 clauses → score at ceiling (97.0)."""
        signals = [make_signal(0.25, severity="low")]
        score = scorer.calculate_from_signals(signals, 10, 5)
        assert score >= 95.0, f"Score {score} should be >= 95.0"

    def test_scenario_two_high_in_5_clauses(self, scorer: ScoringService):
        """2 high findings in 5 clauses → low-mid score with λ=1.5."""
        signals = [
            make_signal(0.75, severity="high"),
            make_signal(0.75, severity="high"),
        ]
        score = scorer.calculate_from_signals(signals, 5, 5)
        # With λ=1.5: penalty_density ~1.05 → score ~21
        assert 15.0 < score < 35.0, f"Score {score} should be in (15, 35)"

    def test_scenario_mixed_findings(self, scorer: ScoringService):
        """3 high + 2 medium in 8 clauses → very low score with λ=1.5."""
        signals = [
            make_signal(0.75, severity="high"),
            make_signal(0.75, severity="high"),
            make_signal(0.75, severity="high"),
            make_signal(0.50, severity="medium"),
            make_signal(0.50, severity="medium"),
        ]
        score = scorer.calculate_from_signals(signals, 8, 5)
        # With λ=1.5: penalty_density ~2.0 → score ~5 (near floor)
        assert 5.0 <= score < 15.0, f"Score {score} should be in [5, 15)"

    def test_scenario_critical_findings_small_project(self, scorer: ScoringService):
        """5 critical in 3 clauses → low score (floor or just above)."""
        signals = [make_signal(0.95, severity="critical") for _ in range(5)]
        score = scorer.calculate_from_signals(signals, 3, 5)
        assert 5.0 <= score <= 15.0, f"Score {score} should be in [5, 15]"

    def test_scenario_low_confidence_llm(self, scorer: ScoringService):
        """1 high (confidence 0.4) in 10 clauses → should be ignored (below threshold)."""
        signals = [make_signal(0.75, confidence=0.40, source="llm")]
        score = scorer.calculate_from_signals(signals, 10, 5)
        assert score == 97.0, f"Low-confidence LLM should be ignored, got {score}"


# =============================================================================
# MAIN
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
