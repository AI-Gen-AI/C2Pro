"""TS-UD-HEALTH-018-003 - Governance health scorer honest-null behavior."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.health.application.governance_scorer import (
    GovernanceInputs,
    score_governance_dimension,
)
from src.health.domain.health_vector import HealthBand, HealthDimension, HealthNullReason


def test_missing_governance_inputs_are_unknown_not_green() -> None:
    signal = score_governance_dimension(None)

    assert signal.dimension is HealthDimension.GOVERNANCE
    assert signal.score is None
    assert signal.band is HealthBand.UNKNOWN
    assert signal.null_reason is HealthNullReason.INSUFFICIENT_EVIDENCE
    assert "no governance activity observed" in signal.missing_data


def test_unobserved_governance_workflow_is_unknown_not_green() -> None:
    signal = score_governance_dimension(
        GovernanceInputs(
            hitl_pending=0,
            hitl_approved=0,
            hitl_rejected=0,
            alert_sla_breaches=0,
            audit_complete=None,
            workflow_observed=False,
        )
    )

    assert signal.score is None
    assert signal.band is HealthBand.UNKNOWN
    assert signal.null_reason is HealthNullReason.INSUFFICIENT_EVIDENCE


def test_sla_breaches_cap_governance_below_healthy() -> None:
    signal = score_governance_dimension(
        GovernanceInputs(
            hitl_pending=0,
            hitl_approved=5,
            hitl_rejected=0,
            alert_sla_breaches=1,
            audit_complete=True,
            workflow_observed=True,
        )
    )

    assert signal.score == 79
    assert signal.band is HealthBand.WATCH
    assert "unresolved SLA breaches present" in signal.missing_data
    assert signal.evidence


def test_clean_resolved_governance_workflow_scores_high_with_evidence() -> None:
    signal = score_governance_dimension(
        GovernanceInputs(
            hitl_pending=0,
            hitl_approved=4,
            hitl_rejected=0,
            alert_sla_breaches=0,
            audit_complete=True,
            workflow_observed=True,
        )
    )

    assert signal.score == 93
    assert signal.band is HealthBand.HEALTHY
    assert signal.confidence == pytest.approx(1.0)
    assert signal.evidence


def test_governance_confidence_tracks_workflow_coverage() -> None:
    signal = score_governance_dimension(
        GovernanceInputs(
            hitl_pending=2,
            hitl_approved=2,
            hitl_rejected=0,
            alert_sla_breaches=0,
            audit_complete=None,
            workflow_observed=True,
        )
    )

    assert signal.score == 45
    assert signal.band is HealthBand.AT_RISK
    assert signal.confidence == pytest.approx(0.65)
    assert "audit completeness unknown" in signal.missing_data


def test_governance_inputs_are_frozen_and_extra_forbidden() -> None:
    inputs = GovernanceInputs(
        hitl_pending=0,
        hitl_approved=1,
        hitl_rejected=0,
        alert_sla_breaches=0,
        audit_complete=True,
        workflow_observed=True,
    )

    with pytest.raises(ValidationError):
        inputs.hitl_pending = 2  # type: ignore[misc]

    with pytest.raises(ValidationError):
        GovernanceInputs(
            hitl_pending=0,
            hitl_approved=1,
            hitl_rejected=0,
            alert_sla_breaches=0,
            audit_complete=True,
            workflow_observed=True,
            unexpected=True,
        )
