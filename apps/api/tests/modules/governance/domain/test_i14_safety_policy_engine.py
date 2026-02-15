"""
I14 - Governance Safety Policy Engine (Domain)
Test Suite ID: TS-I14-GOV-DOM-001
"""

from src.modules.governance.domain.entities import GovernanceInput, RiskLevel
from src.modules.governance.domain.services import SafetyPolicyEngine


def test_i14_high_risk_without_citations_is_blocked() -> None:
    engine = SafetyPolicyEngine()
    payload = GovernanceInput(
        risk_level=RiskLevel.HIGH,
        has_citations=False,
        has_reviewer_sign_off=False,
        override_requested=False,
    )

    decision = engine.evaluate(payload)

    assert decision.allowed is False
    assert "missing_citations" in decision.blocking_reasons


def test_i14_override_requires_compliance_sign_off() -> None:
    engine = SafetyPolicyEngine()
    payload = GovernanceInput(
        risk_level=RiskLevel.MEDIUM,
        has_citations=True,
        has_reviewer_sign_off=False,
        override_requested=True,
    )

    decision = engine.evaluate(payload)

    assert decision.allowed is False
    assert "override_requires_sign_off" in decision.blocking_reasons


def test_i14_allowed_output_includes_mandatory_legal_disclaimer() -> None:
    engine = SafetyPolicyEngine()
    payload = GovernanceInput(
        risk_level=RiskLevel.LOW,
        has_citations=True,
        has_reviewer_sign_off=False,
        override_requested=False,
    )

    decision = engine.evaluate(payload)

    assert decision.allowed is True
    assert "C2Pro provides assisted analysis" in decision.disclaimer
