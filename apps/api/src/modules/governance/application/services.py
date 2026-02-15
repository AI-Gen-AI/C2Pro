"""
Governance application services.

Refers to Suite ID: TS-I14-GOV-APP-001.
"""

from __future__ import annotations

from typing import Any

from src.modules.governance.domain.entities import GovernanceInput, RiskLevel
from src.modules.governance.domain.exceptions import GovernancePolicyViolation
from src.modules.governance.domain.services import SafetyPolicyEngine


class GovernanceOutputGuardService:
    """Applies governance policy gates before returning output payloads."""

    def __init__(self, policy_engine: SafetyPolicyEngine | None = None) -> None:
        self._policy_engine = policy_engine or SafetyPolicyEngine()

    def enforce(
        self,
        *,
        risk_level: RiskLevel,
        has_citations: bool,
        has_reviewer_sign_off: bool,
        override_requested: bool,
        output_payload: dict[str, Any],
    ) -> dict[str, Any]:
        decision = self._policy_engine.evaluate(
            GovernanceInput(
                risk_level=risk_level,
                has_citations=has_citations,
                has_reviewer_sign_off=has_reviewer_sign_off,
                override_requested=override_requested,
            )
        )

        if not decision.allowed:
            raise GovernancePolicyViolation(",".join(decision.blocking_reasons))

        guarded = dict(output_payload)
        guarded["disclaimer"] = decision.disclaimer
        return guarded

