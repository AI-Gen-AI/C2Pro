"""
I14 - Governance Output Guard Middleware (Adapters)
Test Suite ID: TS-I14-GOV-ADP-001
"""

import pytest

from src.modules.governance.adapters.output_guard import GovernanceOutputGuardAdapter
from src.modules.governance.domain.entities import RiskLevel
from src.modules.governance.domain.exceptions import GovernancePolicyViolation


def test_i14_adapter_maps_policy_violation_to_http_409() -> None:
    adapter = GovernanceOutputGuardAdapter()

    with pytest.raises(GovernancePolicyViolation):
        adapter.guard_output(
            risk_level=RiskLevel.HIGH,
            has_citations=False,
            has_reviewer_sign_off=False,
            override_requested=False,
            output_payload={"message": "blocked"},
        )

    err = GovernancePolicyViolation("missing_citations")
    status_code, detail = adapter.map_error(err)
    assert status_code == 409
    assert detail == "missing_citations"


def test_i14_adapter_allows_and_injects_disclaimer() -> None:
    adapter = GovernanceOutputGuardAdapter()

    guarded = adapter.guard_output(
        risk_level=RiskLevel.LOW,
        has_citations=True,
        has_reviewer_sign_off=False,
        override_requested=False,
        output_payload={"message": "ok"},
    )

    assert guarded["message"] == "ok"
    assert "disclaimer" in guarded
