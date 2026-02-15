"""
Governance output guard adapter.

Refers to Suite ID: TS-I14-GOV-ADP-001.
"""

from __future__ import annotations

from typing import Any

from src.modules.governance.application.services import GovernanceOutputGuardService
from src.modules.governance.domain.entities import RiskLevel
from src.modules.governance.domain.exceptions import GovernancePolicyViolation


class GovernanceOutputGuardAdapter:
    """Thin adapter that applies governance service and exposes HTTP mapping."""

    def __init__(self, service: GovernanceOutputGuardService | None = None) -> None:
        self._service = service or GovernanceOutputGuardService()

    def guard_output(
        self,
        *,
        risk_level: RiskLevel,
        has_citations: bool,
        has_reviewer_sign_off: bool,
        override_requested: bool,
        output_payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self._service.enforce(
            risk_level=risk_level,
            has_citations=has_citations,
            has_reviewer_sign_off=has_reviewer_sign_off,
            override_requested=override_requested,
            output_payload=output_payload,
        )

    @staticmethod
    def map_error(error: GovernancePolicyViolation) -> tuple[int, str]:
        return 409, str(error)

