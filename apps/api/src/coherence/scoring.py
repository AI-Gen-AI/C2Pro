"""
scoring.py — Coherence Score Calculator v0.3

Implements exponential decay scoring with scope normalization.
Replaces the linear deduction model with a curve that:
  - Never reaches exactly 0 (floor = 5.0)
  - Never reaches 100 when findings exist (ceiling = 97.0)
  - Absorbs findings better in larger projects (scope normalization)
  - Weights deterministic findings higher than LLM findings

The scoring formula is:
    score = 100 × e^(-λ × penalty_density)

Where:
    penalty_density = weighted_penalty_sum / scope_factor
    weighted_penalty_sum = Σ(impact × confidence × category_weight × source_weight)

Location: apps/api/src/coherence/scoring.py
"""

from __future__ import annotations

import math
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from functools import total_ordering
from typing import Any

# Temporarily add the parent directory to sys.path to allow relative imports when run directly
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(
    os.path.join(script_dir, "../../../../../")
)
sys.path.insert(0, project_root)

from src.coherence.config import (  # noqa: E402
    DECAY_FACTOR,
    DEFAULT_SCORING_CONFIG,
    RULE_WEIGHT_OVERRIDES,
    SEVERITY_WEIGHTS,
    ScoringConfig,
)
from src.coherence.models import (  # noqa: E402
    Alert,
    CategoryBreakdown,
    Evidence,
    FindingSignal,
    SeverityCount,
)

# =============================================================================
# SCORING RESULT DATACLASS
# =============================================================================


@dataclass
@total_ordering
class ScoringResult:
    """
    Score contract returned by the canonical Coherence v1 scoring path.

    Refers to Suite ID: TS-UA-COH-UC-001.
    """

    score: float | None
    reason: str | None = None
    missing_dimensions: list[str] | None = None

    def _numeric_score(self) -> float:
        if self.score is None:
            raise TypeError("insufficient evidence result has no numeric score")
        return self.score

    def __float__(self) -> float:
        return self._numeric_score()

    def __round__(self, ndigits: int | None = None) -> float:
        return round(self._numeric_score(), ndigits) if ndigits is not None else round(self._numeric_score())

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, ScoringResult):
            return (
                self.score == other.score
                and self.reason == other.reason
                and self.missing_dimensions == other.missing_dimensions
            )
        if isinstance(other, int | float):
            return self.score == float(other)
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, ScoringResult):
            if other.score is None:
                raise TypeError("cannot compare against insufficient evidence result")
            return self._numeric_score() < other.score
        if isinstance(other, int | float):
            return self._numeric_score() < float(other)
        return NotImplemented


@dataclass
class ScoringDiagnostics:
    """
    Detailed breakdown of how the score was calculated.

    Useful for debugging, dashboards, and score curve validation.
    """
    score: float | None
    total_findings: int
    deterministic_findings: int
    llm_findings: int
    severity_distribution: dict[str, int]
    avg_impact: float
    avg_confidence: float
    scope_factor: float
    penalty_density: float
    raw_penalty_sum: float
    category_contributions: dict[str, float]
    reason: str | None = None
    missing_dimensions: list[str] | None = None
    category_scores: dict[str, float | None] | None = None
    audit_coverage: dict[str, float] | None = None


@dataclass
class BaselineContext:
    """Signals about the rest of the document used to flex the baseline."""

    total_findings_other_categories: int
    total_assessed_categories: int
    avg_impact_other_categories: float
    num_clauses: int


class HeuristicBaselineProvider:
    """
    Inherent-risk baseline for an assessed-but-clean category.

    Band [80, 90]. Clean elsewhere -> 90; heavily alerted elsewhere -> 80.
    Interface-isolated so a trained regression model can replace it later.
    """

    LOW = 80.0
    HIGH = 90.0
    _RISK_GAIN = 1.5

    def baseline_for(self, category: str, ctx: BaselineContext) -> float:  # noqa: ARG002
        if ctx.total_assessed_categories <= 1:
            return self.HIGH
        global_risk = min(1.0, max(0.0, ctx.avg_impact_other_categories * self._RISK_GAIN))
        return self.HIGH - (self.HIGH - self.LOW) * global_risk


# =============================================================================
# SCORING SERVICE V0.3
# =============================================================================


class ScoringService:
    """
    Service responsible for computing a coherence score based on findings.

    v0.3 implements exponential decay with scope normalization:
        score = 100 × e^(-λ × penalty_density)

    The score represents: "What percentage of this project's coherence is intact?"

        100   = No issues detected
        80+   = Minor issues, project is well-structured
        60-80 = Moderate issues requiring attention
        40-60 = Significant coherence problems
        20-40 = Severe issues, high risk
        <20   = Critical incoherence across the project

    Backward compatible: compute_score() still works with Alert objects.
    New API: calculate_from_signals() accepts FindingSignal objects.
    """

    def __init__(self, config: ScoringConfig | None = None):
        """
        Initialize the scoring service.

        Args:
            config: ScoringConfig for tuning decay, bounds, and weights.
                    If None, uses DEFAULT_SCORING_CONFIG.
        """
        self.config = config or DEFAULT_SCORING_CONFIG
        self._normalized_weights: dict[str, float] | None = None

    @property
    def normalized_weights(self) -> dict[str, float]:
        """Lazily compute normalized category weights."""
        if self._normalized_weights is None:
            self._normalized_weights = self.config.get_normalized_weights()
        return self._normalized_weights

    # =========================================================================
    # V0.3 API — FindingSignal-based scoring
    # =========================================================================

    def calculate_from_signals(
        self,
        signals: list[FindingSignal],
        num_clauses: int = 1,
        num_rules: int = 5,  # noqa: ARG002
        poor_extraction_quality: bool = False,
        missing_dimensions: list[str] | None = None,
    ) -> ScoringResult:
        """
        Calculate coherence score from FindingSignal objects.

        This is the primary v0.3 method that Agent C (Scoring Arbiter) calls.
        Uses exponential decay with scope normalization.

        Args:
            signals: List of FindingSignal objects from evaluators
            num_clauses: Number of clauses in the project context
            num_rules: Number of rules evaluated (for diagnostics)

        Returns:
            ScoringResult: score contract with nullable score on insufficient evidence.
        """
        _ = num_rules
        if not signals or poor_extraction_quality:
            return ScoringResult(
                score=None,
                reason="insufficient_evidence",
                missing_dimensions=missing_dimensions or ["schedule", "budget"],
            )

        # Step 1: Calculate raw weighted penalty sum
        raw_penalty = 0.0
        for signal in signals:
            contribution = self._compute_signal_contribution(signal)
            raw_penalty += contribution

        # Step 2: Scope normalization
        scope_factor = self.config.compute_scope_factor(num_clauses)
        penalty_density = raw_penalty / scope_factor

        # Step 3: Exponential decay
        # score = 100 × e^(-λ × density)
        raw_score = 100.0 * math.exp(-self.config.decay_lambda * penalty_density)

        # Step 4: Apply ceiling (when findings exist, score cannot reach 100)
        raw_score = min(raw_score, self.config.max_score)

        # Step 5: Apply floor (score cannot go below min_score)
        score = max(raw_score, self.config.min_score)

        # Round to 1 decimal for clean API output
        return ScoringResult(score=round(score, 1))

    def calculate_detailed(
        self,
        signals: list[FindingSignal],
        num_clauses: int = 1,
        num_rules: int = 5,  # noqa: ARG002
        poor_extraction_quality: bool = False,
        missing_dimensions: list[str] | None = None,
        coverage_map: dict[str, bool] | None = None,
    ) -> ScoringDiagnostics:
        """
        Calculate score with full diagnostic breakdown.

        Returns detailed information about how the score was computed,
        useful for debugging and dashboard display.

        Args:
            signals: List of FindingSignal objects from evaluators
            num_clauses: Number of clauses in the project context
            num_rules: Number of rules evaluated
            coverage_map: when provided, use the coverage-aware path

        Returns:
            ScoringDiagnostics with score and breakdown
        """
        _ = num_rules
        if coverage_map is not None:
            return self._calculate_detailed_with_coverage(
                signals, num_clauses, coverage_map, poor_extraction_quality
            )
        # ---- legacy path below (UNCHANGED) ----
        if not signals or poor_extraction_quality:
            return ScoringDiagnostics(
                score=None,
                total_findings=0,
                deterministic_findings=0,
                llm_findings=0,
                severity_distribution={"critical": 0, "high": 0, "medium": 0, "low": 0},
                avg_impact=0.0,
                avg_confidence=0.0,
                scope_factor=1.0,
                penalty_density=0.0,
                raw_penalty_sum=0.0,
                category_contributions={},
                reason="insufficient_evidence",
                missing_dimensions=missing_dimensions or ["schedule", "budget"],
            )

        # Compute raw penalty and track category contributions
        raw_penalty = 0.0
        category_contributions: dict[str, float] = defaultdict(float)

        for signal in signals:
            contribution = self._compute_signal_contribution(signal)
            raw_penalty += contribution
            category_contributions[signal.category] += contribution

        # Scope factor and penalty density
        scope_factor = self.config.compute_scope_factor(num_clauses)
        penalty_density = raw_penalty / scope_factor

        # Final score calculation
        raw_score = 100.0 * math.exp(-self.config.decay_lambda * penalty_density)
        raw_score = min(raw_score, self.config.max_score)
        score = max(raw_score, self.config.min_score)

        # Compute aggregates
        det_signals = [s for s in signals if s.source == "deterministic"]
        llm_signals = [s for s in signals if s.source == "llm"]
        avg_impact = sum(s.impact_score for s in signals) / len(signals)
        avg_confidence = sum(s.confidence for s in signals) / len(signals)

        return ScoringDiagnostics(
            score=round(score, 1),
            total_findings=len(signals),
            deterministic_findings=len(det_signals),
            llm_findings=len(llm_signals),
            severity_distribution=self._severity_distribution_signals(signals),
            avg_impact=round(avg_impact, 3),
            avg_confidence=round(avg_confidence, 3),
            scope_factor=round(scope_factor, 3),
            penalty_density=round(penalty_density, 3),
            raw_penalty_sum=round(raw_penalty, 3),
            category_contributions=dict(category_contributions),
            missing_dimensions=missing_dimensions,
        )

    _ALL_CATEGORIES = ("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY")

    def _calculate_detailed_with_coverage(
        self,
        signals: list[FindingSignal],
        num_clauses: int,
        coverage_map: dict[str, bool],
        poor_extraction_quality: bool,
    ) -> ScoringDiagnostics:
        assessed = [c for c in self._ALL_CATEGORIES if coverage_map.get(c, False)]
        unassessed = [c for c in self._ALL_CATEGORIES if not coverage_map.get(c, False)]

        if not assessed or poor_extraction_quality:
            return ScoringDiagnostics(
                score=None, total_findings=0, deterministic_findings=0,
                llm_findings=0,
                severity_distribution={"critical": 0, "high": 0, "medium": 0, "low": 0},
                avg_impact=0.0, avg_confidence=0.0, scope_factor=1.0,
                penalty_density=0.0, raw_penalty_sum=0.0,
                category_contributions={}, reason="insufficient_evidence",
                missing_dimensions=unassessed,
                category_scores={c: None for c in self._ALL_CATEGORIES},
                audit_coverage={"assessed": len(assessed), "total": 6,
                                "pct": round(len(assessed) / 6 * 100, 1)},
            )

        provider = HeuristicBaselineProvider()
        scope_factor = self.config.compute_scope_factor(num_clauses)

        cat_penalty: dict[str, float] = defaultdict(float)
        for s in signals:
            cat_penalty[s.category] += self._compute_signal_contribution(s)

        total_findings = len(signals)
        category_scores: dict[str, float | None] = {c: None for c in self._ALL_CATEGORIES}

        for category in assessed:
            other = [s for s in signals if s.category != category]
            ctx = BaselineContext(
                total_findings_other_categories=len(other),
                total_assessed_categories=len(assessed),
                avg_impact_other_categories=(
                    sum(o.impact_score for o in other) / len(other) if other else 0.0
                ),
                num_clauses=num_clauses,
            )
            baseline = provider.baseline_for(category, ctx)
            density = cat_penalty[category] / scope_factor
            raw = baseline * math.exp(-self.config.decay_lambda * density)
            category_scores[category] = round(
                max(self.config.min_score, min(raw, baseline)), 1
            )

        assessed_vals = [category_scores[c] for c in assessed]
        mean_assessed = sum(assessed_vals) / len(assessed_vals)
        coverage_ratio = len(assessed) / 6.0
        global_score = round(mean_assessed * coverage_ratio, 1)

        sev = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for s in signals:
            if s.severity in sev:
                sev[s.severity] += 1

        return ScoringDiagnostics(
            score=global_score,
            total_findings=total_findings,
            deterministic_findings=sum(1 for s in signals if s.source == "deterministic"),
            llm_findings=sum(1 for s in signals if s.source == "llm"),
            severity_distribution=sev,
            avg_impact=round(
                sum(s.impact_score for s in signals) / total_findings, 3
            ) if total_findings else 0.0,
            avg_confidence=round(
                sum(s.confidence for s in signals) / total_findings, 3
            ) if total_findings else 0.0,
            scope_factor=round(scope_factor, 3),
            penalty_density=round(sum(cat_penalty.values()) / scope_factor, 4),
            raw_penalty_sum=round(sum(cat_penalty.values()), 4),
            category_contributions=dict(cat_penalty),
            reason=None if total_findings else "assessed_clean",
            missing_dimensions=unassessed,
            category_scores=category_scores,
            audit_coverage={"assessed": len(assessed), "total": 6,
                            "pct": round(len(assessed) / 6 * 100, 1)},
        )

    def _compute_signal_contribution(self, signal: FindingSignal) -> float:
        """
        Compute the penalty contribution of a single FindingSignal.

        Formula (from design doc):
            contribution = impact_score × confidence × severity_weight × source_weight

        The impact_score already encodes the "how bad" aspect (0.0-1.0),
        while severity_weight scales it by categorical importance.
        """
        # Severity weight (critical=1.0, high=0.7, medium=0.4, low=0.15)
        severity_weight = self.config.severity_weights.get(signal.severity, 0.4)

        # Source weight (deterministic = 1.0, LLM = config.llm_weight_factor)
        if signal.source == "llm":
            source_weight = self.config.llm_weight_factor
            # Skip LLM findings below confidence threshold
            if signal.confidence < self.config.llm_confidence_threshold:
                return 0.0
        else:
            source_weight = 1.0

        return signal.impact_score * signal.confidence * severity_weight * source_weight

    @staticmethod
    def _severity_distribution_signals(signals: list[FindingSignal]) -> dict[str, int]:
        """Count findings by severity level."""
        dist = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for s in signals:
            if s.severity in dist:
                dist[s.severity] += 1
        return dist

    # =========================================================================
    # BACKWARD-COMPAT API — Alert-based scoring with v0.3 formula
    # =========================================================================

    def calculate(
        self,
        alerts: list[Alert],
        num_clauses: int = 1,
        num_rules: int = 5,
    ) -> ScoringResult:
        """
        Backward-compatible scoring from Alert objects using v0.3 formula.

        Converts alerts to FindingSignals and delegates to calculate_from_signals().

        Args:
            alerts: List of Alert objects
            num_clauses: Number of clauses in the project
            num_rules: Number of rules evaluated

        Returns:
            ScoringResult: score contract with nullable score on insufficient evidence.
        """
        if not alerts:
            return ScoringResult(
                score=None,
                reason="insufficient_evidence",
                missing_dimensions=["schedule", "budget"],
            )

        signals = [self._alert_to_signal(alert) for alert in alerts]
        return self.calculate_from_signals(signals, num_clauses, num_rules)

    def _alert_to_signal(self, alert: Alert) -> FindingSignal:
        """Convert a legacy Alert to a FindingSignal."""
        # Map severity to impact_score
        impact = self._severity_to_impact(alert.severity)

        # Infer source from rule_id pattern
        source = "llm" if alert.rule_id.startswith("R-") else "deterministic"

        # Map category
        category = self._alert_category_to_coherence_category(alert.category)

        return FindingSignal(
            rule_id=alert.rule_id,
            clause_id=alert.evidence.source_clause_id if alert.evidence else "unknown",
            source=source,
            impact_score=impact,
            confidence=1.0,  # Legacy alerts assumed high confidence
            severity=alert.severity.lower(),
            category=category,
            evidence_summary=alert.message,
            quote=alert.evidence.quote if alert.evidence else "",
        )

    @staticmethod
    def _severity_to_impact(severity: str) -> float:
        """Map categorical severity to default continuous impact score."""
        mapping = {
            "critical": 0.95,
            "high": 0.75,
            "medium": 0.50,
            "low": 0.25,
        }
        return mapping.get(severity.lower(), 0.50)

    @staticmethod
    def _alert_category_to_coherence_category(category: str) -> str:
        """Map legacy alert categories to v0.3 coherence categories."""
        mapping = {
            "financial": "BUDGET",
            "legal": "LEGAL",
            "technical": "TECHNICAL",
            "schedule": "TIME",
            "scope": "SCOPE",
            "quality": "QUALITY",
            "general": "SCOPE",
        }
        return mapping.get(category.lower(), "SCOPE")

    # =========================================================================
    # V0.2 LEGACY API — Linear deduction (kept for backward compatibility)
    # =========================================================================

    def compute_score(self, alerts: list[Alert]) -> float:
        """
        Calculates the coherence score based on a more nuanced model.

        1.  Checks for rule-specific weight overrides.
        2.  Applies a decay factor for multiple alerts of the same severity (for non-overridden rules).
        3.  Clamps the final score between 0 and 100.
        """
        base_score = 100.0
        total_deduction = 0.0

        severity_counts: dict[str, int] = {}

        for alert in alerts:
            # 1. Check for a rule-specific override first
            if alert.rule_id in RULE_WEIGHT_OVERRIDES:
                total_deduction += RULE_WEIGHT_OVERRIDES[alert.rule_id]
                continue  # Overridden rules do not contribute to diminishing returns count

            # 2. If no override, use severity weight with diminishing returns
            base_penalty = SEVERITY_WEIGHTS.get(alert.severity, 0.0)

            if base_penalty == 0.0:
                continue

            severity = alert.severity
            count = severity_counts.get(severity, 0)

            decayed_penalty = base_penalty * (DECAY_FACTOR**count)

            total_deduction += decayed_penalty

            # Increment the count for this severity
            severity_counts[severity] = count + 1

        final_score = base_score - total_deduction

        # Clamp the score between 0 and 100 and round to 2 decimal places
        return max(0.0, min(100.0, round(final_score, 2)))

    def compute_category_breakdown(self, alerts: list[Alert]) -> list[CategoryBreakdown]:
        """
        Computes the coherence score breakdown by category.

        Args:
            alerts: List of alerts to analyze

        Returns:
            List of CategoryBreakdown objects, one per category with alerts
        """
        # Group alerts by category
        category_alerts: dict[str, list[Alert]] = defaultdict(list)
        for alert in alerts:
            category_alerts[alert.category].append(alert)

        # Calculate overall score and total deduction for impact percentages
        overall_score = self.compute_score(alerts)
        total_deduction = 100.0 - overall_score

        breakdown_list: list[CategoryBreakdown] = []

        for category, cat_alerts in category_alerts.items():
            # Calculate score for this category
            category_score = self._compute_category_score(cat_alerts)

            # Calculate category deduction
            category_deduction = 100.0 - category_score

            # Calculate impact percentage (what percentage of total deduction comes from this category)
            if total_deduction > 0:
                impact_percentage = round((category_deduction / total_deduction) * 100, 2)
            else:
                impact_percentage = 0.0

            # Count alerts by severity
            severity_breakdown = self._count_severity(cat_alerts)

            breakdown_list.append(
                CategoryBreakdown(
                    category=category,
                    score=category_score,
                    alert_count=len(cat_alerts),
                    severity_breakdown=severity_breakdown,
                    impact_percentage=impact_percentage
                )
            )

        # Sort by impact percentage (highest first)
        breakdown_list.sort(key=lambda x: x.impact_percentage, reverse=True)

        return breakdown_list

    def _compute_category_score(self, alerts: list[Alert]) -> float:
        """
        Computes the coherence score for a specific category of alerts.

        Args:
            alerts: List of alerts in a single category

        Returns:
            Score for this category (0-100)
        """
        base_score = 100.0
        total_deduction = 0.0

        severity_counts: dict[str, int] = {}

        for alert in alerts:
            # Check for rule-specific override
            if alert.rule_id in RULE_WEIGHT_OVERRIDES:
                total_deduction += RULE_WEIGHT_OVERRIDES[alert.rule_id]
                continue

            # Use severity weight with diminishing returns
            base_penalty = SEVERITY_WEIGHTS.get(alert.severity, 0.0)

            if base_penalty == 0.0:
                continue

            severity = alert.severity
            count = severity_counts.get(severity, 0)

            decayed_penalty = base_penalty * (DECAY_FACTOR**count)

            total_deduction += decayed_penalty

            severity_counts[severity] = count + 1

        final_score = base_score - total_deduction

        return max(0.0, min(100.0, round(final_score, 2)))

    def _count_severity(self, alerts: list[Alert]) -> SeverityCount:
        """
        Counts alerts by severity level.

        Args:
            alerts: List of alerts to count

        Returns:
            SeverityCount object with counts by severity
        """
        counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0
        }

        for alert in alerts:
            severity = alert.severity.lower()
            if severity in counts:
                counts[severity] += 1

        return SeverityCount(**counts)


if __name__ == "__main__":
    # Example usage and testing for the new ScoringService

    # Create dummy alerts for testing
    high_alert_1 = Alert(
        rule_id="HIGH-001",
        severity="high",
        message="",
        evidence=Evidence(source_clause_id="c1", claim="", quote=""),
    )
    high_alert_2 = Alert(
        rule_id="HIGH-002",
        severity="high",
        message="",
        evidence=Evidence(source_clause_id="c2", claim="", quote=""),
    )

    # This rule has a weight override in config.py (20.0)
    budget_overrun_alert = Alert(
        rule_id="project-budget-overrun-10",
        severity="high",
        message="",
        evidence=Evidence(source_clause_id="c3", claim="", quote=""),
    )

    medium_alert = Alert(
        rule_id="MED-001",
        severity="medium",
        message="",
        evidence=Evidence(source_clause_id="c4", claim="", quote=""),
    )

    service = ScoringService()

    print("--- Testing Advanced Scoring ---")

    # Test case 1: Single high alert (no decay)
    score1 = service.compute_score([high_alert_1])
    print(f"Score with one 'high' alert: {score1}")
    # Expected: 100 - 15 = 85.0

    # Test case 2: Two high alerts (diminishing returns)
    score2 = service.compute_score([high_alert_1, high_alert_2])
    deduction2 = 15.0 * (DECAY_FACTOR**0) + 15.0 * (DECAY_FACTOR**1)
    print(f"Score with two 'high' alerts: {score2} (Expected: {100 - deduction2})")

    # Test case 3: Rule-specific weight override
    score3 = service.compute_score([budget_overrun_alert])
    print(f"Score with overridden rule 'project-budget-overrun-10': {score3}")
    # Expected: 100 - 20.0 = 80.0

    # Test case 4: Mixed alerts with override and diminishing returns
    alerts = [high_alert_1, high_alert_2, budget_overrun_alert, medium_alert]
    # 'high_alert_1' is a 'high' alert (count 1)
    # 'high_alert_2' is a 'high' alert (count 2)
    # 'budget_overrun_alert' is also 'high', but uses its override (20.0), so it doesn't affect the 'high' count for decay
    # Let's refine the logic to count based on the *final* weight source for fairness.
    # For now, let's assume the count is by severity string.
    # high_alert_1 penalty = 15 * (0.85**0) = 15
    # high_alert_2 penalty = 15 * (0.85**1) = 12.75
    # budget_overrun_alert penalty = 20.0 (override)
    # medium_alert penalty = 5 * (0.85**0) = 5
    # Total deduction = 15 + 12.75 + 20 + 5 = 52.75
    score4 = service.compute_score(alerts)
    print(f"Score with mixed alerts: {score4} (Expected: {100 - 52.75})")
