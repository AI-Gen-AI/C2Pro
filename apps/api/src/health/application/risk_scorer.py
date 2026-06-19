"""TS-UD-HEALTH-018-002 - Deterministic risk health scorer.

Formula v0:
- no completed assessment, or extraction quality below 0.40, returns honest-null.
- successful clean assessment scores 90 with explicit clean-assessment evidence.
- otherwise score = max(0, 95 - severity penalties), where LOW=5,
  MEDIUM=12, HIGH=25, CRITICAL=40 if a future producer emits it.
"""

from __future__ import annotations

from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier
from src.health.domain.health_vector import (
    HealthBand,
    HealthDimension,
    HealthNullReason,
    HealthSignal,
    band_for_score,
)
from src.project_state.domain.entities import ProjectRisk

_QUALITY_FLOOR = 0.4
_DEFAULT_CONFIDENCE = 0.7
_CLEAN_ASSESSMENT_SCORE = 90.0
_SEVERITY_WEIGHTS = {
    "LOW": 5.0,
    "MEDIUM": 12.0,
    "HIGH": 25.0,
    "CRITICAL": 40.0,
}


def score_risk_dimension(
    risks: list[ProjectRisk],
    *,
    assessment_ran: bool,
    extraction_quality: float | None = None,
) -> HealthSignal:
    """Score project risk health without treating missing assessment as green."""

    confidence = _confidence_from_quality(extraction_quality)
    if not assessment_ran:
        return _unknown_signal(
            confidence=0.0,
            missing_data=["risk assessment did not run"],
        )
    if extraction_quality is not None and extraction_quality < _QUALITY_FLOOR:
        return _unknown_signal(
            confidence=confidence,
            missing_data=["poor extraction quality"],
        )
    if not risks:
        score = _CLEAN_ASSESSMENT_SCORE
        return HealthSignal(
            dimension=HealthDimension.RISK,
            score=score,
            band=band_for_score(score),
            confidence=confidence,
            evidence=[
                EvidenceRef(
                    ref_id="risk-assessment-clean",
                    source="risk_assessment",
                    tier=EvidenceTier.VERIFIED,
                    locator="assessment",
                )
            ],
        )

    penalty = sum(_risk_penalty(risk) for risk in risks)
    score = max(0.0, 95.0 - penalty)
    return HealthSignal(
        dimension=HealthDimension.RISK,
        score=score,
        band=band_for_score(score),
        confidence=confidence,
        evidence=_risk_evidence(risks),
    )


def _unknown_signal(*, confidence: float, missing_data: list[str]) -> HealthSignal:
    return HealthSignal(
        dimension=HealthDimension.RISK,
        score=None,
        band=HealthBand.UNKNOWN,
        confidence=confidence,
        missing_data=missing_data,
        null_reason=HealthNullReason.INSUFFICIENT_EVIDENCE,
    )


def _confidence_from_quality(extraction_quality: float | None) -> float:
    if extraction_quality is None:
        return _DEFAULT_CONFIDENCE
    return min(1.0, max(0.0, extraction_quality))


def _risk_penalty(risk: ProjectRisk) -> float:
    severity = risk.payload.severity or risk.payload.impact
    if severity is None:
        return _SEVERITY_WEIGHTS["MEDIUM"]
    return _SEVERITY_WEIGHTS.get(str(severity.value).upper(), _SEVERITY_WEIGHTS["MEDIUM"])


def _risk_evidence(risks: list[ProjectRisk]) -> list[EvidenceRef]:
    evidence: list[EvidenceRef] = []
    for risk in risks:
        if risk.evidence:
            evidence.extend(risk.evidence)
        else:
            evidence.append(
                EvidenceRef(
                    ref_id=str(risk.entity_id),
                    source="risk_assessment",
                    tier=EvidenceTier.WEAK,
                    locator=str(risk.entity_id),
                )
            )
    return evidence


__all__ = ["score_risk_dimension"]
