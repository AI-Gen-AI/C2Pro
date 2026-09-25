"""
Tests for minimal org/role model (TASK-V3-019-03).

RED phase: written before the implementation exists.
Scope: StakeholderRole enum, ActionStakeholder model,
       assign_owner(), resolve_escalation_path(), DEFAULT_ESCALATION_POLICY.
Out of scope: full RBAC, auto-assignment from org graph.
"""

from __future__ import annotations

import uuid
from uuid import UUID

import pytest

from src.action_review.domain.action_item import (
    ActionItem,
    ActionStatus,
    ImpactArea,
    Severity,
)
from src.action_review.domain.org import (
    DEFAULT_ESCALATION_POLICY,
    ActionStakeholder,
    EscalationPolicy,
    StakeholderRole,
    assign_owner,
    resolve_escalation_path,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TENANT = uuid.uuid4()


def _stakeholder(role: StakeholderRole, *, name: str = "Alice") -> ActionStakeholder:
    return ActionStakeholder(id=uuid.uuid4(), name=name, role=role, tenant_id=_TENANT)


def _item(
    severity: Severity = Severity.MEDIUM,
    *,
    owner: UUID | None = None,
    escalation: list[UUID] | None = None,
) -> ActionItem:
    return ActionItem(
        id=uuid.uuid4(),
        severity=severity,
        confidence=0.8,
        impact_area=[ImpactArea.CONTRACT],
        affected_objects=[],
        evidence_refs=[],
        recommended_action="Review",
        owner_stakeholder_id=owner,
        due_at=None,
        escalation_path=escalation or [],
        correlation_group=uuid.uuid4(),
        status=ActionStatus.OPEN,
    )


# ---------------------------------------------------------------------------
# StakeholderRole
# ---------------------------------------------------------------------------


class TestStakeholderRole:
    def test_has_contract_manager(self) -> None:
        assert StakeholderRole.CONTRACT_MANAGER == "contract_manager"

    def test_has_legal(self) -> None:
        assert StakeholderRole.LEGAL == "legal"

    def test_has_finance(self) -> None:
        assert StakeholderRole.FINANCE == "finance"

    def test_has_executive(self) -> None:
        assert StakeholderRole.EXECUTIVE == "executive"


# ---------------------------------------------------------------------------
# ActionStakeholder model
# ---------------------------------------------------------------------------


class TestActionStakeholder:
    def test_fields_present(self) -> None:
        s = _stakeholder(StakeholderRole.CONTRACT_MANAGER, name="Bob")
        assert s.name == "Bob"
        assert s.role == StakeholderRole.CONTRACT_MANAGER
        assert s.tenant_id == _TENANT

    def test_is_immutable(self) -> None:
        s = _stakeholder(StakeholderRole.LEGAL)
        with pytest.raises(Exception):
            s.name = "Hacked"  # type: ignore[misc]

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(Exception):
            ActionStakeholder(  # type: ignore[call-arg]
                id=uuid.uuid4(),
                name="X",
                role=StakeholderRole.EXECUTIVE,
                tenant_id=_TENANT,
                unknown_field="oops",
            )


# ---------------------------------------------------------------------------
# assign_owner
# ---------------------------------------------------------------------------


class TestAssignOwner:
    def test_sets_owner_to_first_contract_manager(self) -> None:
        cm = _stakeholder(StakeholderRole.CONTRACT_MANAGER, name="CM One")
        item = _item()
        result = assign_owner(item, [cm])
        assert result.owner_stakeholder_id == cm.id

    def test_no_contract_manager_leaves_owner_none(self) -> None:
        legal = _stakeholder(StakeholderRole.LEGAL)
        item = _item()
        result = assign_owner(item, [legal])
        assert result.owner_stakeholder_id is None

    def test_empty_stakeholders_leaves_owner_none(self) -> None:
        result = assign_owner(_item(), [])
        assert result.owner_stakeholder_id is None

    def test_picks_first_contract_manager_when_multiple(self) -> None:
        cm1 = _stakeholder(StakeholderRole.CONTRACT_MANAGER, name="CM First")
        cm2 = _stakeholder(StakeholderRole.CONTRACT_MANAGER, name="CM Second")
        result = assign_owner(_item(), [cm1, cm2])
        assert result.owner_stakeholder_id == cm1.id

    def test_does_not_mutate_original_item(self) -> None:
        original = _item()
        cm = _stakeholder(StakeholderRole.CONTRACT_MANAGER)
        assign_owner(original, [cm])
        assert original.owner_stakeholder_id is None

    def test_returns_new_item_instance(self) -> None:
        cm = _stakeholder(StakeholderRole.CONTRACT_MANAGER)
        item = _item()
        result = assign_owner(item, [cm])
        assert result is not item

    def test_non_cm_roles_skipped(self) -> None:
        stakeholders = [
            _stakeholder(StakeholderRole.LEGAL),
            _stakeholder(StakeholderRole.EXECUTIVE),
            _stakeholder(StakeholderRole.CONTRACT_MANAGER, name="The CM"),
        ]
        result = assign_owner(_item(), stakeholders)
        assert result.owner_stakeholder_id == stakeholders[2].id

    def test_preserves_other_fields(self) -> None:
        item = _item(severity=Severity.HIGH)
        cm = _stakeholder(StakeholderRole.CONTRACT_MANAGER)
        result = assign_owner(item, [cm])
        assert result.severity == Severity.HIGH
        assert result.status == ActionStatus.OPEN


# ---------------------------------------------------------------------------
# DEFAULT_ESCALATION_POLICY
# ---------------------------------------------------------------------------


class TestDefaultEscalationPolicy:
    def test_critical_has_three_roles(self) -> None:
        roles = DEFAULT_ESCALATION_POLICY[Severity.CRITICAL]
        assert len(roles) == 3
        assert StakeholderRole.CONTRACT_MANAGER in roles
        assert StakeholderRole.EXECUTIVE in roles

    def test_high_has_two_roles(self) -> None:
        roles = DEFAULT_ESCALATION_POLICY[Severity.HIGH]
        assert len(roles) == 2
        assert StakeholderRole.CONTRACT_MANAGER in roles

    def test_medium_has_one_role(self) -> None:
        roles = DEFAULT_ESCALATION_POLICY[Severity.MEDIUM]
        assert roles == [StakeholderRole.CONTRACT_MANAGER]

    def test_low_is_empty(self) -> None:
        assert DEFAULT_ESCALATION_POLICY[Severity.LOW] == []

    def test_info_is_empty(self) -> None:
        assert DEFAULT_ESCALATION_POLICY[Severity.INFO] == []

    def test_all_severities_covered(self) -> None:
        for sev in Severity:
            assert sev in DEFAULT_ESCALATION_POLICY


# ---------------------------------------------------------------------------
# resolve_escalation_path
# ---------------------------------------------------------------------------


class TestResolveEscalationPath:
    def test_critical_path_includes_cm_legal_executive(self) -> None:
        cm = _stakeholder(StakeholderRole.CONTRACT_MANAGER)
        legal = _stakeholder(StakeholderRole.LEGAL)
        exec_ = _stakeholder(StakeholderRole.EXECUTIVE)
        item = _item(Severity.CRITICAL)
        result = resolve_escalation_path(item, [cm, legal, exec_])
        assert cm.id in result.escalation_path
        assert legal.id in result.escalation_path
        assert exec_.id in result.escalation_path

    def test_medium_path_contains_only_cm(self) -> None:
        cm = _stakeholder(StakeholderRole.CONTRACT_MANAGER)
        legal = _stakeholder(StakeholderRole.LEGAL)
        exec_ = _stakeholder(StakeholderRole.EXECUTIVE)
        item = _item(Severity.MEDIUM)
        result = resolve_escalation_path(item, [cm, legal, exec_])
        assert result.escalation_path == [cm.id]

    def test_low_path_is_empty(self) -> None:
        cm = _stakeholder(StakeholderRole.CONTRACT_MANAGER)
        item = _item(Severity.LOW)
        result = resolve_escalation_path(item, [cm])
        assert result.escalation_path == []

    def test_missing_role_skipped_not_error(self) -> None:
        cm = _stakeholder(StakeholderRole.CONTRACT_MANAGER)
        # no LEGAL or EXECUTIVE available
        item = _item(Severity.CRITICAL)
        result = resolve_escalation_path(item, [cm])
        assert result.escalation_path == [cm.id]

    def test_no_stakeholders_empty_path(self) -> None:
        item = _item(Severity.HIGH)
        result = resolve_escalation_path(item, [])
        assert result.escalation_path == []

    def test_does_not_mutate_original(self) -> None:
        cm = _stakeholder(StakeholderRole.CONTRACT_MANAGER)
        item = _item(Severity.HIGH)
        resolve_escalation_path(item, [cm])
        assert item.escalation_path == []

    def test_returns_new_item(self) -> None:
        cm = _stakeholder(StakeholderRole.CONTRACT_MANAGER)
        item = _item(Severity.MEDIUM)
        result = resolve_escalation_path(item, [cm])
        assert result is not item

    def test_custom_policy_overrides_default(self) -> None:
        exec_ = _stakeholder(StakeholderRole.EXECUTIVE)
        custom: EscalationPolicy = {
            Severity.INFO: [StakeholderRole.EXECUTIVE],
            Severity.LOW: [],
            Severity.MEDIUM: [],
            Severity.HIGH: [],
            Severity.CRITICAL: [],
        }
        item = _item(Severity.INFO)
        result = resolve_escalation_path(item, [exec_], policy=custom)
        assert result.escalation_path == [exec_.id]

    def test_path_order_follows_policy_order(self) -> None:
        cm = _stakeholder(StakeholderRole.CONTRACT_MANAGER)
        legal = _stakeholder(StakeholderRole.LEGAL)
        exec_ = _stakeholder(StakeholderRole.EXECUTIVE)
        item = _item(Severity.CRITICAL)
        result = resolve_escalation_path(item, [exec_, legal, cm])
        expected_roles = DEFAULT_ESCALATION_POLICY[Severity.CRITICAL]
        role_map = {StakeholderRole.CONTRACT_MANAGER: cm.id, StakeholderRole.LEGAL: legal.id, StakeholderRole.EXECUTIVE: exec_.id}
        expected_path = [role_map[r] for r in expected_roles]
        assert result.escalation_path == expected_path

    def test_duplicate_role_in_stakeholders_uses_first(self) -> None:
        cm1 = _stakeholder(StakeholderRole.CONTRACT_MANAGER, name="CM1")
        cm2 = _stakeholder(StakeholderRole.CONTRACT_MANAGER, name="CM2")
        item = _item(Severity.MEDIUM)
        result = resolve_escalation_path(item, [cm1, cm2])
        assert result.escalation_path == [cm1.id]
