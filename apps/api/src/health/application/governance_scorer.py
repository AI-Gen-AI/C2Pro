"""TS-UD-HEALTH-018-003 - Deterministic governance health scorer.

Formula v0:
- missing or unobserved governance workflow returns honest-null.
- base score 70, plus audit/approval evidence, minus pending reviews and SLA
  breaches. Any unresolved SLA breach caps the score below HEALTHY.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier
from src.health.domain.health_vector import (
    HealthBand,
    HealthDimension,
    HealthNullReason,
    HealthSignal,
    band_for_score,
)


class GovernanceInputs(BaseModel):
    """Health-ready governance summary supplied by future assembly code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hitl_pending: int = Field(ge=0)
    hitl_approved: int = Field(ge=0)
    hitl_rejected: int = Field(ge=0)
    alert_sla_breaches: int = Field(ge=0)
    audit_complete: bool | None
    workflow_observed: bool


def score_governance_dimension(inputs: GovernanceInputs | None) -> HealthSignal:
    """Score governance health from provided HITL, alert, and audit summary inputs."""

    if inputs is None or not inputs.workflow_observed:
        return HealthSignal(
            dimension=HealthDimension.GOVERNANCE,
            score=None,
            band=HealthBand.UNKNOWN,
            confidence=0.0,
            missing_data=["no governance activity observed"],
            null_reason=HealthNullReason.INSUFFICIENT_EVIDENCE,
        )

    score = 70.0
    missing_data: list[str] = []
    if inputs.audit_complete is True:
        score += 15.0
    elif inputs.audit_complete is False:
        score -= 20.0
        missing_data.append("audit incomplete")
    else:
        score -= 10.0
        missing_data.append("audit completeness unknown")

    score += min(10.0, inputs.hitl_approved * 2.0)
    score -= inputs.hitl_rejected * 5.0
    score -= inputs.hitl_pending * 9.5
    if inputs.hitl_pending > 0:
        missing_data.append("pending HITL reviews present")

    score -= inputs.alert_sla_breaches * 5.0
    if inputs.alert_sla_breaches > 0:
        score = min(score, 79.0)
        missing_data.append("unresolved SLA breaches present")

    score = min(100.0, max(0.0, score))
    return HealthSignal(
        dimension=HealthDimension.GOVERNANCE,
        score=score,
        band=band_for_score(score),
        confidence=_governance_confidence(inputs),
        evidence=_governance_evidence(inputs),
        missing_data=missing_data,
    )


def _governance_confidence(inputs: GovernanceInputs) -> float:
    total_reviews = inputs.hitl_pending + inputs.hitl_approved + inputs.hitl_rejected
    resolved_ratio = (
        (inputs.hitl_approved + inputs.hitl_rejected) / total_reviews
        if total_reviews > 0
        else 1.0
    )
    audit_confidence = 0.30 if inputs.audit_complete is not None else 0.10
    return round(min(1.0, 0.40 + audit_confidence + (0.30 * resolved_ratio)), 2)


def _governance_evidence(inputs: GovernanceInputs) -> list[EvidenceRef]:
    evidence = [
        EvidenceRef(
            ref_id="governance-workflow-observed",
            source="governance_inputs",
            tier=EvidenceTier.VERIFIED,
            locator="workflow_observed",
        )
    ]
    if inputs.hitl_pending + inputs.hitl_approved + inputs.hitl_rejected > 0:
        evidence.append(
            EvidenceRef(
                ref_id="hitl-review-summary",
                source="governance_inputs",
                tier=EvidenceTier.VERIFIED,
                locator="hitl",
            )
        )
    if inputs.alert_sla_breaches >= 0:
        evidence.append(
            EvidenceRef(
                ref_id="alert-sla-summary",
                source="governance_inputs",
                tier=EvidenceTier.VERIFIED,
                locator="alert_sla_breaches",
            )
        )
    return evidence


__all__ = ["GovernanceInputs", "score_governance_dimension"]
