"""
I13/I14 security controls for final output gating.

Test Suite ID: TS-SEC-S6-001
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.modules.decision_intelligence.application.ports import DecisionOrchestrationService
from src.modules.decision_intelligence.domain.exceptions import FinalizationBlockedError
from src.modules.governance.application.services import GovernanceOutputGuardService
from src.modules.governance.domain.entities import RiskLevel
from src.modules.governance.domain.exceptions import GovernancePolicyViolation


@pytest.mark.asyncio
async def test_s6_i13_low_confidence_cannot_be_bypassed_with_inline_approval() -> None:
    service = DecisionOrchestrationService()

    with pytest.raises(FinalizationBlockedError, match="Item requires review"):
        await service.execute_full_decision_flow(
            document_bytes=b"doc",
            tenant_id=uuid4(),
            project_id=uuid4(),
            force_profile="low_confidence",
            review_decision={
                "item_id": str(uuid4()),
                "reviewer_id": str(uuid4()),
                "reviewer_name": "Inline Reviewer",
                "action": "approve",
            },
        )


def test_s6_i14_override_cannot_bypass_missing_citations_even_with_sign_off() -> None:
    service = GovernanceOutputGuardService()

    with pytest.raises(GovernancePolicyViolation, match="missing_citations"):
        service.enforce(
            risk_level=RiskLevel.HIGH,
            has_citations=False,
            has_reviewer_sign_off=True,
            override_requested=True,
            output_payload={"message": "must block"},
        )


def test_s6_i14_high_risk_without_sign_off_is_always_blocked() -> None:
    service = GovernanceOutputGuardService()

    with pytest.raises(GovernancePolicyViolation, match="mandatory_sign_off_required"):
        service.enforce(
            risk_level=RiskLevel.HIGH,
            has_citations=True,
            has_reviewer_sign_off=False,
            override_requested=False,
            output_payload={"message": "must block"},
        )
