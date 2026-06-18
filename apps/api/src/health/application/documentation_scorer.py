"""TS-UD-HEALTH-018-003 - Deterministic documentation health scorer.

Formula v0:
- missing or empty documentation-health signal returns honest-null.
- score = 95 - 80 * weighted_issue_ratio, where failed=1.0,
  degraded=0.5, skipped=0.25.
- any failed node caps the score below HEALTHY.
"""

from __future__ import annotations

from src.analysis.domain.documentation_health import DocumentationHealthSignal
from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier
from src.health.domain.health_vector import (
    HealthBand,
    HealthDimension,
    HealthNullReason,
    HealthSignal,
    band_for_score,
)


def score_documentation_dimension(signal: DocumentationHealthSignal | None) -> HealthSignal:
    """Score documentation health from the pipeline runtime-trust meta-signal."""

    if signal is None or signal.total_count == 0:
        return HealthSignal(
            dimension=HealthDimension.DOCUMENTATION,
            score=None,
            band=HealthBand.UNKNOWN,
            confidence=0.0,
            missing_data=["no pipeline documentation-health signal"],
            null_reason=HealthNullReason.INSUFFICIENT_EVIDENCE,
        )

    weighted_issues = (
        signal.failed_count + (0.5 * signal.degraded_count) + (0.25 * signal.skipped_count)
    )
    issue_ratio = weighted_issues / signal.total_count
    score = max(0.0, 95.0 - (80.0 * issue_ratio))
    missing_data: list[str] = []
    if signal.failed_count > 0:
        score = min(score, 79.0)
        missing_data.append("failed nodes present")

    confidence = round(max(0.0, (signal.total_count - signal.skipped_count) / signal.total_count), 2)
    return HealthSignal(
        dimension=HealthDimension.DOCUMENTATION,
        score=score,
        band=band_for_score(score),
        confidence=confidence,
        evidence=[
            EvidenceRef(
                ref_id="documentation-health-signal",
                source="analysis_pipeline",
                tier=EvidenceTier.VERIFIED,
                locator="node_results",
            )
        ],
        missing_data=missing_data,
    )


__all__ = ["score_documentation_dimension"]
