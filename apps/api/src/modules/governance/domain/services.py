"""
Governance domain services.

Refers to Suite ID: TS-I14-GOV-DOM-001.
"""

from __future__ import annotations

from src.modules.governance.domain.entities import GovernanceDecision, GovernanceInput, RiskLevel


MANDATORY_LEGAL_DISCLAIMER = (
    "C2Pro provides assisted analysis and does not replace legal, technical, "
    "or commercial professional judgment."
)


class SafetyPolicyEngine:
    """Evaluates release safety gates for output publication."""

    def evaluate(self, payload: GovernanceInput) -> GovernanceDecision:
        reasons: list[str] = []

        if not payload.has_citations:
            reasons.append("missing_citations")

        if payload.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL} and not payload.has_reviewer_sign_off:
            reasons.append("mandatory_sign_off_required")

        if payload.override_requested and not payload.has_reviewer_sign_off:
            reasons.append("override_requires_sign_off")

        return GovernanceDecision(
            allowed=len(reasons) == 0,
            blocking_reasons=tuple(reasons),
            disclaimer=MANDATORY_LEGAL_DISCLAIMER,
        )

