"""
Minimal org/role model for the Action & Review bounded context (ADR-019).

Provides the shared seam that ADR-020 HITL consumes (CM queue) and
ADR-014 Stakeholder-Intelligence will extend. Scope is intentionally
thin: no full RBAC, no auto-assignment from an org graph.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.action_review.domain.action_item import ActionItem, Severity


class StakeholderRole(StrEnum):
    CONTRACT_MANAGER = "contract_manager"
    LEGAL = "legal"
    FINANCE = "finance"
    EXECUTIVE = "executive"


class ActionStakeholder(BaseModel):
    """Stakeholder within the action-review context. Immutable reference object."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    name: str
    role: StakeholderRole
    tenant_id: UUID


# Policy type: maps Severity → ordered list of roles for escalation.
EscalationPolicy = dict[Severity, list[StakeholderRole]]

DEFAULT_ESCALATION_POLICY: EscalationPolicy = {
    Severity.CRITICAL: [
        StakeholderRole.CONTRACT_MANAGER,
        StakeholderRole.LEGAL,
        StakeholderRole.EXECUTIVE,
    ],
    Severity.HIGH: [StakeholderRole.CONTRACT_MANAGER, StakeholderRole.LEGAL],
    Severity.MEDIUM: [StakeholderRole.CONTRACT_MANAGER],
    Severity.LOW: [],
    Severity.INFO: [],
}


def assign_owner(
    item: ActionItem,
    stakeholders: list[ActionStakeholder],
) -> ActionItem:
    """
    Return new ActionItem with owner_stakeholder_id set to the first
    CONTRACT_MANAGER in stakeholders. Returns item unchanged when none found.
    """
    for s in stakeholders:
        if s.role == StakeholderRole.CONTRACT_MANAGER:
            return item.model_copy(update={"owner_stakeholder_id": s.id})
    return item


def resolve_escalation_path(
    item: ActionItem,
    stakeholders: list[ActionStakeholder],
    policy: EscalationPolicy | None = None,
) -> ActionItem:
    """
    Return new ActionItem with escalation_path resolved per policy.

    Path order follows the policy's role order. Missing roles are skipped
    rather than raising an error. First stakeholder per role wins when
    duplicates exist.
    """
    effective = policy if policy is not None else DEFAULT_ESCALATION_POLICY
    target_roles = effective.get(item.severity, [])

    # first-wins per role
    role_to_id: dict[StakeholderRole, UUID] = {}
    for s in stakeholders:
        if s.role not in role_to_id:
            role_to_id[s.role] = s.id

    path = [role_to_id[role] for role in target_roles if role in role_to_id]
    return item.model_copy(update={"escalation_path": path})


__all__ = [
    "DEFAULT_ESCALATION_POLICY",
    "ActionStakeholder",
    "EscalationPolicy",
    "StakeholderRole",
    "assign_owner",
    "resolve_escalation_path",
]
