"""
TS-UC-GOV-SPE-001 — SafetyPolicyEngine unit tests.

Refers to Suite ID: TS-I14-GOV-DOM-001.
Pure unit tests: no DB, no HTTP, no external services.
"""

import pytest

from src.modules.governance.domain.entities import GovernanceDecision, GovernanceInput, RiskLevel
from src.modules.governance.domain.services import (
    MANDATORY_LEGAL_DISCLAIMER,
    SafetyPolicyEngine,
)


class TestSafetyPolicyEngine:
    @pytest.mark.asyncio
    async def test_001_all_gates_pass(self):
        engine = SafetyPolicyEngine()
        payload = GovernanceInput(
            risk_level=RiskLevel.LOW,
            has_citations=True,
            has_reviewer_sign_off=False,
            override_requested=False,
        )

        decision = engine.evaluate(payload)

        assert decision.allowed is True
        assert decision.blocking_reasons == ()
        assert decision.disclaimer == MANDATORY_LEGAL_DISCLAIMER

    @pytest.mark.asyncio
    async def test_002_medium_risk_passes(self):
        engine = SafetyPolicyEngine()
        payload = GovernanceInput(
            risk_level=RiskLevel.MEDIUM,
            has_citations=True,
            has_reviewer_sign_off=False,
            override_requested=False,
        )

        decision = engine.evaluate(payload)

        assert decision.allowed is True
        assert decision.blocking_reasons == ()

    @pytest.mark.asyncio
    async def test_003_missing_citations_blocks(self):
        engine = SafetyPolicyEngine()
        payload = GovernanceInput(
            risk_level=RiskLevel.LOW,
            has_citations=False,
            has_reviewer_sign_off=True,
            override_requested=False,
        )

        decision = engine.evaluate(payload)

        assert decision.allowed is False
        assert "missing_citations" in decision.blocking_reasons

    @pytest.mark.asyncio
    async def test_004_high_risk_without_signoff_blocks(self):
        engine = SafetyPolicyEngine()
        payload = GovernanceInput(
            risk_level=RiskLevel.HIGH,
            has_citations=True,
            has_reviewer_sign_off=False,
            override_requested=False,
        )

        decision = engine.evaluate(payload)

        assert decision.allowed is False
        assert "mandatory_sign_off_required" in decision.blocking_reasons

    @pytest.mark.asyncio
    async def test_005_critical_risk_without_signoff_blocks(self):
        engine = SafetyPolicyEngine()
        payload = GovernanceInput(
            risk_level=RiskLevel.CRITICAL,
            has_citations=True,
            has_reviewer_sign_off=False,
            override_requested=False,
        )

        decision = engine.evaluate(payload)

        assert decision.allowed is False
        assert "mandatory_sign_off_required" in decision.blocking_reasons

    @pytest.mark.asyncio
    async def test_006_high_risk_with_signoff_passes(self):
        engine = SafetyPolicyEngine()
        payload = GovernanceInput(
            risk_level=RiskLevel.HIGH,
            has_citations=True,
            has_reviewer_sign_off=True,
            override_requested=False,
        )

        decision = engine.evaluate(payload)

        assert decision.allowed is True

    @pytest.mark.asyncio
    async def test_007_override_without_signoff_blocks(self):
        engine = SafetyPolicyEngine()
        payload = GovernanceInput(
            risk_level=RiskLevel.LOW,
            has_citations=True,
            has_reviewer_sign_off=False,
            override_requested=True,
        )

        decision = engine.evaluate(payload)

        assert decision.allowed is False
        assert "override_requires_sign_off" in decision.blocking_reasons

    @pytest.mark.asyncio
    async def test_008_override_with_signoff_passes(self):
        engine = SafetyPolicyEngine()
        payload = GovernanceInput(
            risk_level=RiskLevel.LOW,
            has_citations=True,
            has_reviewer_sign_off=True,
            override_requested=True,
        )

        decision = engine.evaluate(payload)

        assert decision.allowed is True

    @pytest.mark.asyncio
    async def test_009_multiple_reasons_accumulate(self):
        engine = SafetyPolicyEngine()
        payload = GovernanceInput(
            risk_level=RiskLevel.HIGH,
            has_citations=False,
            has_reviewer_sign_off=False,
            override_requested=True,
        )

        decision = engine.evaluate(payload)

        assert decision.allowed is False
        assert "missing_citations" in decision.blocking_reasons
        assert "mandatory_sign_off_required" in decision.blocking_reasons
        assert "override_requires_sign_off" in decision.blocking_reasons
        assert len(decision.blocking_reasons) == 3

    @pytest.mark.asyncio
    async def test_010_disclaimer_always_present(self):
        engine = SafetyPolicyEngine()
        payload = GovernanceInput(
            risk_level=RiskLevel.CRITICAL,
            has_citations=False,
            has_reviewer_sign_off=False,
            override_requested=True,
        )

        decision = engine.evaluate(payload)

        assert decision.disclaimer == MANDATORY_LEGAL_DISCLAIMER
        assert len(decision.disclaimer) > 0
