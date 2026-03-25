"""
I10 - Stakeholder Resolution + RACI Inference (Domain)
Test Suite ID: TS-I10-STKH-DOM-001
"""

from datetime import datetime
from uuid import uuid4, UUID

import pytest

from src.stakeholders.domain.models import (
    InterestLevel,
    PartyResolutionResult,
    PowerLevel,
    RaciActivity,
    RaciResponsibility,
    RACIRole,
    Stakeholder,
)
from src.stakeholders.domain.services.stakeholder_resolver import StakeholderResolver
from src.stakeholders.domain.services.raci_validator import validate_activity_raci


class RACIValidator:
    def validate_activity_raci(self, activity: RaciActivity) -> list[str]:
        return validate_activity_raci(activity)


def _make_stakeholder(**overrides) -> Stakeholder:
    now = datetime.utcnow()
    base = {
        "id": uuid4(),
        "project_id": uuid4(),
        "power_level": PowerLevel.MEDIUM,
        "interest_level": InterestLevel.MEDIUM,
        "approval_status": "approved",
        "created_at": now,
        "updated_at": now,
        "name": "Default Name",
    }
    base.update(overrides)
    return Stakeholder(**base)


def test_i10_resolver_merges_alias_to_existing_canonical_stakeholder() -> None:
    """Refers to I10.1: stakeholder aliases must resolve to existing canonical identity."""
    canonical_id = uuid4()
    existing = [
        _make_stakeholder(
            name="Contractor Inc.",
            canonical_id=canonical_id,
            aliases={"Contractor", "Main Contractor"},
            confidence=0.99,
        )
    ]
    resolver = StakeholderResolver()

    result = resolver.resolve_entity("Main Contractor", existing)

    assert isinstance(result, PartyResolutionResult)
    assert result.action == "merged"
    assert result.canonical_id == canonical_id
    assert result.resolved_stakeholder_id == existing[0].id
    assert result.ambiguity_flag is False


def test_i10_resolver_flags_ambiguous_party_for_human_validation() -> None:
    """Refers to I10.6: ambiguous party mapping must be flagged and not auto-merged."""
    existing = [
        _make_stakeholder(
            name="Client Holdings LLC",
            canonical_id=uuid4(),
            aliases={"Client Holdings"},
            confidence=0.90,
        ),
        _make_stakeholder(
            name="Client Holdings Group",
            canonical_id=uuid4(),
            aliases={"Client Holdings"},
            confidence=0.88,
        ),
    ]
    resolver = StakeholderResolver()

    result = resolver.resolve_entity("Client Holdings", existing)

    assert isinstance(result, PartyResolutionResult)
    assert result.ambiguity_flag is True
    assert result.resolved_stakeholder_id is None
    assert result.action in {"new_with_canonical", "new"}
    assert result.warning_message is not None


def test_i10_raci_validator_rejects_multiple_accountable_assignments() -> None:
    """Refers to I10.2: each activity must have exactly one Accountable assignment."""
    activity = RaciActivity(
        description="Approve change order package for structural revision.",
        confidence=0.92,
        responsibilities=[
            RaciResponsibility(stakeholder_id=uuid4(), role=RACIRole.ACCOUNTABLE, confidence=0.96),
            RaciResponsibility(stakeholder_id=uuid4(), role=RACIRole.ACCOUNTABLE, confidence=0.94),
            RaciResponsibility(stakeholder_id=uuid4(), role=RACIRole.RESPONSIBLE, confidence=0.90),
        ],
    )
    validator = RACIValidator()

    violations = validator.validate_activity_raci(activity)

    assert len(violations) > 0
    assert any("accountable" in v.lower() for v in violations)

