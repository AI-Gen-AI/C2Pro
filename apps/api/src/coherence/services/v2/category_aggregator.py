"""
Per-category aggregator: turns evidence + conflicts + rule signals into a
fully-typed `CategoryV2` (ADR-009 §6, §10, §13).

This module is the single source of truth for the deterministic conflict
formula:

    adjusted_score = base_score × (1 − (1 − SEVERITY_MULTIPLIERS[severity]) × evidence_certainty)

i.e. detection-certainty scales the PENALTY, not the score: higher certainty ⇒
stronger penalty ⇒ lower score (ADR-009, 2026-08-16 governing amendment §B/§D).
Identical to the prior `base × multiplier × certainty` at full certainty; corrected
(non-inverted) below it. The band a critical may fall into stays governed by
SEVERITY_MULTIPLIERS as an interim guard pending the unified calibrated model.

Refers to Suite ID: TS-UA-COH-V2-CATAGG-001.
"""

from __future__ import annotations

from src.coherence.application.dtos.coherence_v2_dtos import (
    BudgetReconciliation,
    CategoryStatus,
    CategoryV2,
    ScoreExplanation,
)
from src.coherence.domain.category_state_machine import CategoryStateMachine
from src.coherence.domain.v2_constants import (
    MIN_EVIDENCE_BY_CATEGORY,
    SEVERITY_MULTIPLIERS,
)
from src.coherence.services.v2.conflict_service import ConflictReport
from src.coherence.services.v2.evidence_service import EvidenceBundle


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
            # ADR-009 (2026-08-16 GOVERNING amendment §B/§D): graduated penalty in
            # which detection-certainty scales the PENALTY, not the score. The
            # `severity_penalty` is the fraction of base removed at full certainty
            # (retained from SEVERITY_MULTIPLIERS: 1 - multiplier). Lower certainty =>
            # weaker penalty => higher score. The previous
            # `base * multiplier * certainty` was inverted (a *more*-certain conflict
            # scored *higher*). At certainty == 1.0 this is identical to the prior
            # formula, so full-certainty behaviour is preserved; no new band constant
            # is introduced here.
            multiplier = SEVERITY_MULTIPLIERS.get(conflict.severity, 0.4)
            severity_penalty = 1.0 - multiplier
            certainty_scaled_penalty = severity_penalty * conflict.evidence_certainty
            adjusted = base * (1.0 - certainty_scaled_penalty)
            explanation = ScoreExplanation(
                negative_factors=["hard_conflict", f"severity:{conflict.severity}"],
                dominant_rules=[r for r, _ in rule_signals],
                score_path=[
                    {"step": "base", "value": base},
                    {
                        "step": "severity_penalty",
                        "severity": conflict.severity,
                        "value": severity_penalty,
                    },
                    {
                        "step": "certainty_scaled_penalty",
                        "certainty": conflict.evidence_certainty,
                        "value": certainty_scaled_penalty,
                    },
                    {"step": "adjusted", "value": adjusted},
                ],
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
