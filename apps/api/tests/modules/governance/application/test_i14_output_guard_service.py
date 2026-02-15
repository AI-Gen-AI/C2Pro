"""
I14 - Governance Output Guard Service (Application)
Test Suite ID: TS-I14-GOV-APP-001
"""

import pytest

from src.modules.governance.application.services import GovernanceOutputGuardService
from src.modules.governance.domain.entities import RiskLevel
from src.modules.governance.domain.exceptions import GovernancePolicyViolation


def test_i14_output_guard_blocks_unsafe_release() -> None:
    service = GovernanceOutputGuardService()

    with pytest.raises(GovernancePolicyViolation, match="missing_citations"):
        service.enforce(
            risk_level=RiskLevel.HIGH,
            has_citations=False,
            has_reviewer_sign_off=False,
            override_requested=False,
            output_payload={"result": "unsafe"},
        )


def test_i14_output_guard_allows_release_with_disclaimer() -> None:
    service = GovernanceOutputGuardService()

    guarded = service.enforce(
        risk_level=RiskLevel.LOW,
        has_citations=True,
        has_reviewer_sign_off=False,
        override_requested=False,
        output_payload={"result": "safe"},
    )

    assert guarded["result"] == "safe"
    assert "disclaimer" in guarded
    assert "C2Pro provides assisted analysis" in guarded["disclaimer"]
