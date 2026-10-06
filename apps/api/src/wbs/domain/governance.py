"""WBS governance domain contracts (ADR-029; #688 amendment 2026-10-05; PC-2a.1 #895).

Authority over the canonical WBS is DERIVED, never stored:

* ``APPROVED_BASELINE`` -- an applied baseline exists;
* ``LEGACY_UNGOVERNED`` -- live ``wbs_nodes`` exist but no baseline was ever applied;
* ``NO_WBS`` -- neither;
* ``draft_exists`` is an orthogonal flag (open DRAFT/SUBMITTED change sets);
  ``DRAFT_ONLY`` is only a display name for ``NO_WBS`` + draft.

A change set's origin (manual / ai / import) or entry mode (generate / import + review /
change baseline) never confers authority: only a human-governed apply creates a baseline.
These rules are enforced again by database constraints and triggers.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from src.wbs.domain.digest import LineageEdge, normalize_dictionary


class GovernanceRuleError(ValueError):
    """A WBS governance rule was violated (never a silent repair)."""


class ChangeSetStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    STALE = "STALE"


OPEN_STATUSES = frozenset({ChangeSetStatus.DRAFT, ChangeSetStatus.SUBMITTED})
TERMINAL_STATUSES = frozenset(
    {ChangeSetStatus.APPLIED, ChangeSetStatus.REJECTED, ChangeSetStatus.WITHDRAWN, ChangeSetStatus.STALE}
)

# No approved-but-unapplied state: approve IS apply (PC-2a.2, one transaction).
# SUBMITTED -> DRAFT is "reopen": it invalidates the submitted digest.
ALLOWED_TRANSITIONS: Mapping[ChangeSetStatus, frozenset[ChangeSetStatus]] = {
    ChangeSetStatus.DRAFT: frozenset(
        {ChangeSetStatus.SUBMITTED, ChangeSetStatus.WITHDRAWN, ChangeSetStatus.STALE}
    ),
    ChangeSetStatus.SUBMITTED: frozenset(
        {
            ChangeSetStatus.APPLIED,
            ChangeSetStatus.REJECTED,
            ChangeSetStatus.WITHDRAWN,
            ChangeSetStatus.DRAFT,
            ChangeSetStatus.STALE,
        }
    ),
    ChangeSetStatus.APPLIED: frozenset(),
    ChangeSetStatus.REJECTED: frozenset(),
    ChangeSetStatus.WITHDRAWN: frozenset(),
    ChangeSetStatus.STALE: frozenset(),
}


def require_transition(current: ChangeSetStatus, target: ChangeSetStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[ChangeSetStatus(current)]:
        raise GovernanceRuleError(f"WBS change set cannot move from {current} to {target}")


class ChangeSetOrigin(StrEnum):
    """Who drafted the content. Never a source of authority."""

    MANUAL = "manual"
    AI = "ai"
    IMPORT = "import"


class EntryMode(StrEnum):
    """ADR-029 product entry modes; all of them end in a governed apply."""

    GENERATE = "GENERATE"
    IMPORT_REVIEW = "IMPORT_REVIEW"
    CHANGE_BASELINE = "CHANGE_BASELINE"


class CandidateOriginKind(StrEnum):
    """How a candidate node's canonical id was obtained."""

    EXISTING = "existing"  # kept from the base baseline (same id, any attribute may change)
    MINTED = "minted"  # new identity minted by the server for this change set
    ADOPTED_LEGACY = "adopted_legacy"  # first baseline only: an explicitly kept legacy live id


class LineageKind(StrEnum):
    SPLIT = "SPLIT"
    MERGE = "MERGE"
    SUPERSEDES = "SUPERSEDES"


class ControlLevel(StrEnum):
    """Vocabulary only. Methodology nesting rules (e.g. "no CA under CA") are NOT universal
    across EPC, civil, software, IT and hybrid projects and belong to PC-2b profiles."""

    NONE = "none"
    CONTROL_ACCOUNT = "control_account"
    WORK_PACKAGE = "work_package"
    PLANNING_PACKAGE = "planning_package"


class ActorKind(StrEnum):
    HUMAN = "human"
    AI = "ai"
    SERVICE = "service"


class AuthorityState(StrEnum):
    NO_WBS = "NO_WBS"
    LEGACY_UNGOVERNED = "LEGACY_UNGOVERNED"
    APPROVED_BASELINE = "APPROVED_BASELINE"


CORE_DECOMPOSITION_TERMS = frozenset(
    {"area", "system", "subsystem", "discipline", "deliverable", "component", "capability", "phase", "package", "other"}
)
DECOMPOSITION_KIND_PATTERN = re.compile(r"^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$")


def validate_control_level(value: str) -> ControlLevel:
    try:
        return ControlLevel(value)
    except ValueError as exc:
        raise GovernanceRuleError(f"unknown control_level {value!r}") from exc


def validate_decomposition_kind(value: str | None) -> str | None:
    """``namespace:term``; ``core:`` terms must be in the v1 core vocabulary.

    Other namespaces only have their format checked here: validating them against a
    pinned WBS Domain Profile is PC-2b work.
    """
    if value is None:
        return None
    if not DECOMPOSITION_KIND_PATTERN.fullmatch(value):
        raise GovernanceRuleError(f"decomposition_kind {value!r} is not 'namespace:term'")
    namespace, term = value.split(":", 1)
    if namespace == "core" and term not in CORE_DECOMPOSITION_TERMS:
        raise GovernanceRuleError(f"{value!r} is not in the core decomposition vocabulary")
    return value


# --------------------------------------------------------------------------- actors
_AUTHOR_ROLES = frozenset({"admin", "user"})
_DECIDER_ROLES = frozenset({"admin"})


def can_author(actor_kind: ActorKind | str, role: str | None) -> bool:
    """Create/edit/submit/withdraw/reopen: a human ``user`` or ``admin``.

    AI may create ``origin=ai`` DRAFTS through a service path, but never submits."""
    return ActorKind(actor_kind) is ActorKind.HUMAN and (role or "") in _AUTHOR_ROLES


def can_withdraw_or_reopen(
    actor_kind: ActorKind | str, role: str | None, actor_id: UUID, *, proposers: Iterable[UUID | None]
) -> bool:
    """Withdraw/reopen: the proposer (who drafted or submitted it) or a human ``admin``.

    Another tenant ``user`` can neither clear someone else's signed submission nor close it."""
    if not can_author(actor_kind, role):
        return False
    return role == "admin" or actor_id in {proposer for proposer in proposers if proposer is not None}


def can_decide(actor_kind: ActorKind | str, role: str | None) -> bool:
    """Approve/reject: a human ``admin`` only -- never an ``api`` user, AI or service."""
    return ActorKind(actor_kind) is ActorKind.HUMAN and (role or "") in _DECIDER_ROLES


def self_approval(*, submitter: UUID, approver: UUID, require_distinct_approver: bool = True) -> bool:
    """Separation of duties. Returns whether the decision is a (permitted) self-approval.

    ``require_distinct_approver`` is the tenant setting
    ``settings.wbs_governance.require_distinct_approver`` and defaults to TRUE (fail-closed).
    """
    is_self = submitter == approver
    if is_self and require_distinct_approver:
        raise GovernanceRuleError("the approver must differ from the submitter (separation of duties)")
    return is_self


def require_distinct_approver(tenant_settings: Mapping[str, Any] | None) -> bool:
    value = ((tenant_settings or {}).get("wbs_governance") or {}).get("require_distinct_approver", True)
    return value is not False


# --------------------------------------------------------------------------- candidate validation
@dataclass(frozen=True)
class CandidateNode:
    node_id: UUID
    parent_id: UUID | None
    sort_order: int
    code: str | None
    name: str
    decomposition_kind: str | None = None
    control_level: str = ControlLevel.NONE.value
    dictionary: Mapping[str, Any] | None = None
    origin_kind: str = CandidateOriginKind.EXISTING.value


def validate_for_submit(nodes: Sequence[CandidateNode], lineage: Iterable[LineageEdge]) -> list[str]:
    """Every reason the candidate cannot be submitted (empty list = submittable)."""
    violations: list[str] = []
    by_id = {node.node_id: node for node in nodes}
    if len(by_id) != len(nodes):
        violations.append("duplicate node ids in candidate")
    seen_codes: dict[str, UUID] = {}
    for node in nodes:
        label = str(node.node_id)
        if node.code is None or not node.code.strip():
            violations.append(f"{label}: code is required to submit")
        elif unicodedata.normalize("NFC", node.code) != node.code:
            violations.append(f"{label}: code must be NFC-normalised")
        elif node.code in seen_codes:
            violations.append(f"{label}: duplicate code {node.code!r}")
        else:
            seen_codes[node.code] = node.node_id
        if not node.name or not node.name.strip():
            violations.append(f"{label}: name is required")
        if node.parent_id is not None and node.parent_id not in by_id:
            violations.append(f"{label}: parent {node.parent_id} is not in the candidate")
        try:
            validate_control_level(node.control_level)
            validate_decomposition_kind(node.decomposition_kind)
        except GovernanceRuleError as exc:
            violations.append(f"{label}: {exc}")
        try:
            normalize_dictionary(node.dictionary)
        except (TypeError, ValueError) as exc:
            violations.append(f"{label}: invalid dictionary ({exc})")
    for node in nodes:
        walked: set[UUID] = set()
        current: UUID | None = node.node_id
        while current is not None and current in by_id:
            if current in walked:
                violations.append(f"{node.node_id}: parent cycle")
                break
            walked.add(current)
            current = by_id[current].parent_id
    for edge in lineage:
        target = by_id.get(edge.target_node_id)
        if target is None:
            violations.append(f"lineage target {edge.target_node_id} is not in the candidate")
        elif target.origin_kind != CandidateOriginKind.MINTED:
            violations.append(f"lineage target {edge.target_node_id} must be a minted identity")
        if edge.source_node_id == edge.target_node_id:
            violations.append(f"lineage edge {edge.source_node_id} points to itself")
    return violations


# --------------------------------------------------------------------------- authority
@dataclass(frozen=True)
class BaselineRef:
    baseline_id: UUID
    baseline_no: int
    tree_digest: str
    applied_at: datetime


@dataclass(frozen=True)
class WBSAuthority:
    state: AuthorityState
    baseline_id: UUID | None
    baseline_no: int | None
    tree_digest: str | None
    applied_at: datetime | None
    open_change_sets: int
    legacy_node_count: int

    @property
    def draft_exists(self) -> bool:
        return self.open_change_sets > 0

    @property
    def approved(self) -> bool:
        return self.state is AuthorityState.APPROVED_BASELINE

    @property
    def display_state(self) -> str:
        if self.state is AuthorityState.NO_WBS and self.draft_exists:
            return "DRAFT_ONLY"
        return self.state.value


def resolve_authority(
    *, current_baseline: BaselineRef | None, live_node_count: int, open_change_sets: int
) -> WBSAuthority:
    """The single canonical authority derivation (no stored enum)."""
    if current_baseline is not None:
        return WBSAuthority(
            state=AuthorityState.APPROVED_BASELINE,
            baseline_id=current_baseline.baseline_id,
            baseline_no=current_baseline.baseline_no,
            tree_digest=current_baseline.tree_digest,
            applied_at=current_baseline.applied_at,
            open_change_sets=open_change_sets,
            legacy_node_count=0,
        )
    state = AuthorityState.LEGACY_UNGOVERNED if live_node_count > 0 else AuthorityState.NO_WBS
    return WBSAuthority(
        state=state,
        baseline_id=None,
        baseline_no=None,
        tree_digest=None,
        applied_at=None,
        open_change_sets=open_change_sets,
        legacy_node_count=live_node_count,
    )


class WBSAuthorityReader(Protocol):
    """Port to the single authority resolver (implemented by ``WBSGovernanceRepository``)."""

    async def authority(self, project_id: UUID, tenant_id: UUID) -> WBSAuthority: ...


# PC-2a.3 (#897) consumer vocabulary. An approved baseline confers authority on SCOPE only
# (identity, hierarchy, order, code, name, control level, decomposition, dictionary) -- never on
# the legacy date / cost columns of the live rows: WBS dates are not Schedule authority and
# budget_allocated / budget_spent are not Cost authority, in every state.
LEGACY_WBS_SCOPE_LABEL = "Unapproved / Legacy WBS"
DRAFT_WBS_SCOPE_LABEL = "Draft WBS (not approved)"
NO_WBS_SCOPE_LABEL = "No WBS"
WBS_NOT_APPROVED_REASON = "WBS_NOT_APPROVED"
WBS_DATES_NOT_SCHEDULE_AUTHORITY_REASON = "WBS_DATES_NOT_SCHEDULE_AUTHORITY"


def wbs_scope_label(authority: WBSAuthority) -> str:
    """How a consumer names the project's WBS scope: approved scope is never implied."""
    if authority.approved:
        return f"Approved WBS Baseline #{authority.baseline_no}"
    if authority.state is AuthorityState.LEGACY_UNGOVERNED:
        return LEGACY_WBS_SCOPE_LABEL
    return DRAFT_WBS_SCOPE_LABEL if authority.draft_exists else NO_WBS_SCOPE_LABEL


__all__ = [
    "ALLOWED_TRANSITIONS",
    "CORE_DECOMPOSITION_TERMS",
    "DRAFT_WBS_SCOPE_LABEL",
    "LEGACY_WBS_SCOPE_LABEL",
    "NO_WBS_SCOPE_LABEL",
    "OPEN_STATUSES",
    "TERMINAL_STATUSES",
    "WBS_DATES_NOT_SCHEDULE_AUTHORITY_REASON",
    "WBS_NOT_APPROVED_REASON",
    "ActorKind",
    "AuthorityState",
    "BaselineRef",
    "CandidateNode",
    "CandidateOriginKind",
    "ChangeSetOrigin",
    "ChangeSetStatus",
    "ControlLevel",
    "EntryMode",
    "GovernanceRuleError",
    "LineageEdge",
    "LineageKind",
    "WBSAuthority",
    "WBSAuthorityReader",
    "can_author",
    "can_decide",
    "can_withdraw_or_reopen",
    "require_distinct_approver",
    "require_transition",
    "resolve_authority",
    "self_approval",
    "validate_control_level",
    "validate_decomposition_kind",
    "validate_for_submit",
    "wbs_scope_label",
]
