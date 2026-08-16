"""
Per-category aggregator: turns evidence + conflicts + rule signals into a
fully-typed `CategoryV2` (ADR-009 §6, §10, §13).

Scoring is delegated to the single canonical model (`coherence.canonical`): a hard
conflict is placed in its severity band by certainty × materiality — graduated,
monotonic, never 0 and never the "falsehood" ~8 (ADR-009 2026-08-16 amendment
§B/§D). Per the binding separation of concerns (§C) the per-category scorer sees
ONLY this category's evidence; the global critical-risk envelope lives in
`GlobalAggregatorV2` / `canonical.aggregate_global`.

Refers to Suite ID: TS-UA-COH-V2-CATAGG-001.
"""

from __future__ import annotations

from typing import cast

from src.coherence.application.dtos.coherence_v2_dtos import (
    BudgetReconciliation,
    CategoryStatus,
    CategoryV2,
    ScoreExplanation,
)
from src.coherence.canonical.category import (
    CategoryScoreInput,
    ConflictInput,
    Severity,
    score_category,
)
from src.coherence.domain.category_state_machine import CategoryStateMachine
from src.coherence.domain.v2_constants import MIN_EVIDENCE_BY_CATEGORY
from src.coherence.services.v2.conflict_service import ConflictReport
from src.coherence.services.v2.evidence_service import EvidenceBundle

_CANONICAL_SEVERITIES: frozenset[str] = frozenset({"low", "medium", "high", "critical"})


def _to_canonical_severity(severity: str) -> Severity:
    """Map a ConflictReport severity to the canonical Severity (fallback: high)."""
    return cast(Severity, severity) if severity in _CANONICAL_SEVERITIES else "high"


# Interim (§B, calibratable): a discrepancy whose |delta| reaches this fraction of the
# compared magnitude is treated as fully material (⇒ band floor). Smaller gaps sit
# nearer the band ceiling.
_MATERIALITY_SATURATION_RATIO = 0.5


def _materiality_from_conflict(conflict: ConflictReport) -> float | None:
    """Normalized discrepancy materiality in [0, 1] from the conflict's compared values.

    Larger relative gap ⇒ higher materiality ⇒ nearer the band floor. Returns None
    when the conflict carries no numeric basis (⇒ the canonical model treats it as
    fully material). `base` is deliberately NOT consulted (§B/§C).
    """
    ratios: list[float] = []
    for candidate in conflict.conflict_set:
        if not isinstance(candidate, dict):
            continue
        values = candidate.get("compared_values")
        delta = candidate.get("delta")
        if not isinstance(values, dict) or not isinstance(delta, int | float):
            continue
        denom = max(
            (abs(float(v)) for v in values.values() if isinstance(v, int | float)),
            default=0.0,
        )
        if denom > 0:
            ratios.append(abs(float(delta)) / denom)
    if not ratios:
        return None
    return min(1.0, max(ratios) / _MATERIALITY_SATURATION_RATIO)


class CategoryAggregator:
    def __init__(self, state_machine: CategoryStateMachine | None = None) -> None:
        self._sm = state_machine or CategoryStateMachine()

    def aggregate(
        self,
        category: str,
        evidence: EvidenceBundle,
        conflict: ConflictReport,
        rule_signals: list[tuple[str, float]],
        applicable: bool,
        applicability_reason: str | None = None,
        assessed: bool = True,
        budget_reconciliation: BudgetReconciliation | None = None,  # TASK-BCK-093
    ) -> CategoryV2:
        if not applicable:
            return CategoryV2(
                category=category,
                status=CategoryStatus.NOT_APPLICABLE,
                coherence_score=None,
                evidence_coverage=evidence.evidence_coverage,
                technical_reliability=evidence.avg_technical_reliability,
                evidence_freshness=evidence.evidence_freshness,
                applicability_reason=applicability_reason,
                evidence_count=evidence.count,
                evidence_references=list(evidence.references),
                budget_reconciliation=budget_reconciliation,
            )

        if evidence.count == 0:
            return CategoryV2(
                category=category,
                status=CategoryStatus.PENDING_DOCUMENTS,
                coherence_score=None,
                evidence_coverage=0.0,
                technical_reliability=0.0,
                evidence_freshness=0.0,
                missing_evidence=list(evidence.missing_required),
                evidence_count=0,
                budget_reconciliation=budget_reconciliation,
            )

        threshold = MIN_EVIDENCE_BY_CATEGORY.get(category, 1)
        if evidence.count < threshold:
            return CategoryV2(
                category=category,
                status=CategoryStatus.INSUFFICIENT_EVIDENCE,
                coherence_score=None,
                evidence_coverage=evidence.evidence_coverage,
                technical_reliability=evidence.avg_technical_reliability,
                evidence_freshness=evidence.evidence_freshness,
                evidence_count=evidence.count,
                evidence_references=list(evidence.references),
                missing_evidence=list(evidence.missing_required),
                budget_reconciliation=budget_reconciliation,
            )

        base = self._aggregate_rule_signals(rule_signals)
        if base is None:
            if not assessed:
                return CategoryV2(
                    category=category,
                    status=CategoryStatus.INSUFFICIENT_EVIDENCE,
                    coherence_score=None,
                    evidence_coverage=evidence.evidence_coverage,
                    technical_reliability=evidence.avg_technical_reliability,
                    evidence_freshness=evidence.evidence_freshness,
                    evidence_count=evidence.count,
                    evidence_references=list(evidence.references),
                    missing_evidence=list(evidence.missing_required),
                    rationale="rule_assessment_unavailable",
                    calculation_metadata={"assessment_state": "unassessed"},
                    budget_reconciliation=budget_reconciliation,
                )
            base = 100.0
            assessment_state = "assessed_clean"
        else:
            assessment_state = "assessed_with_signals"

        if conflict.hard_conflict:
            # Delegate scoring to the single canonical model (§B/§C/§D). A hard
            # conflict lands in its severity band by certainty × materiality —
            # graduated, monotonic, never 0. `base` (this category's own rule
            # signals) is passed in; worst_open is deliberately NOT — that is the
            # global layer's concern (§C).
            canonical = score_category(
                CategoryScoreInput(
                    base=base,
                    conflict=ConflictInput(
                        severity=_to_canonical_severity(conflict.severity),
                        certainty=conflict.evidence_certainty,
                        magnitude=_materiality_from_conflict(conflict),
                        independent_count=max(1, len(conflict.conflict_set)),
                    ),
                )
            )
            adjusted = canonical.score if canonical.score is not None else base
            explanation = ScoreExplanation(
                negative_factors=["hard_conflict", f"severity:{conflict.severity}"],
                dominant_rules=[r for r, _ in rule_signals],
                score_path=[{"step": "base", "value": base}, *canonical.penalty_steps],
            )
            return CategoryV2(
                category=category,
                status=CategoryStatus.CONFLICTING_EVIDENCE,
                coherence_score=round(adjusted, 2),
                evidence_coverage=evidence.evidence_coverage,
                technical_reliability=evidence.avg_technical_reliability,
                evidence_freshness=evidence.evidence_freshness,
                evidence_count=evidence.count,
                evidence_references=list(evidence.references),
                detected_conflicts=list(conflict.conflict_set),
                score_explanation=explanation,
                calculation_metadata={"assessment_state": assessment_state},
                budget_reconciliation=budget_reconciliation,
            )

        explanation = ScoreExplanation(
            positive_factors=["evidence_threshold_met", "no_hard_conflict"],
            dominant_rules=[r for r, _ in rule_signals],
            score_path=[{"step": "base", "value": base}],
        )
        return CategoryV2(
            category=category,
            status=CategoryStatus.SCORED,
            coherence_score=round(base, 2),
            evidence_coverage=evidence.evidence_coverage,
            technical_reliability=evidence.avg_technical_reliability,
            evidence_freshness=evidence.evidence_freshness,
            evidence_count=evidence.count,
            evidence_references=list(evidence.references),
            score_explanation=explanation,
            calculation_metadata={"assessment_state": assessment_state},
            budget_reconciliation=budget_reconciliation,
        )

    @staticmethod
    def _aggregate_rule_signals(signals: list[tuple[str, float]]) -> float | None:
        if not signals:
            return None
        values = [score for _, score in signals]
        return max(0.0, min(100.0, sum(values) / len(values)))


__all__ = ["CategoryAggregator"]
