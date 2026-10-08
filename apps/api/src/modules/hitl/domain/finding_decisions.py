"""PQ-HITL-04A: append-only *draft* per-finding decisions.

This domain has NO persistence, TRUSTED transition, review-row approval, or
LangGraph resume capability. The only finalization authority remains the
existing exact-candidate #714/#758 HITL settlement.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any
from uuid import UUID

from src.analysis.domain.trust import CandidateBinding


class DecisionConflict(ValueError):
    """Stale candidate, review authority, ledger revision or idempotency key."""


class DecisionAction(StrEnum):
    CONFIRM = "CONFIRM"
    DISMISS = "DISMISS"
    CORRECT = "CORRECT"
    NEEDS_INFO = "NEEDS_INFO"


@dataclass(frozen=True)
class ReviewCandidateScope:
    """Exact identity for a *proposed* candidate and its live review lineage."""

    tenant_id: UUID
    review_row_id: UUID
    binding: CandidateBinding
    generation: int
    fencing_token: int
    thread_id: str
    checkpoint_id: UUID | None

    def __post_init__(self) -> None:
        if self.generation < 1 or self.fencing_token < 1:
            raise ValueError("An active generation and fence are required")
        if not self.thread_id.strip():
            raise ValueError("An authority-scoped thread is required")
        digest = self.binding.artifact_hash
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
            raise ValueError("An exact SHA-256 candidate hash is required")
        if self.binding.artifact_version < 1:
            raise ValueError("An immutable candidate version is required")


@dataclass(frozen=True)
class ProposedFindingDecision:
    scope: ReviewCandidateScope
    finding_id: str
    action: DecisionAction
    reason: str
    reviewer_id: UUID
    expected_revision: int
    idempotency_key: str
    proposed_correction: dict[str, Any] | None = None


@dataclass(frozen=True)
class FindingDecisionDraft:
    """Append-only, immutable in-memory projection, not a settlement result."""

    scope: ReviewCandidateScope
    required_finding_ids: frozenset[str]
    revision: int = 0
    entries: tuple[ProposedFindingDecision, ...] = ()

    def __post_init__(self) -> None:
        if not self.required_finding_ids or any(
            not finding.strip() for finding in self.required_finding_ids
        ):
            raise ValueError("Explicit nonempty required finding IDs are mandatory")
        if self.revision < 0:
            raise ValueError("Decision revision cannot be negative")

    @property
    def _latest_actions(self) -> dict[str, DecisionAction]:
        return {entry.finding_id: entry.action for entry in self.entries}

    @property
    def requires_new_candidate(self) -> bool:
        # Proposed corrections cannot be approved in place: a new artifact
        # version + digest requires an explicitly re-bound human review.
        return DecisionAction.CORRECT in self._latest_actions.values()

    @property
    def ready_for_final_authority_check(self) -> bool:
        # This flag NEVER approves or resumes anything. The existing #714
        # settlement must independently verify source evidence, actor,
        # candidate hash, tenant, fence, checkpoint, and current ledger.
        actions = self._latest_actions
        return not self.requires_new_candidate and all(
            actions.get(finding_id) in {DecisionAction.CONFIRM, DecisionAction.DISMISS}
            for finding_id in self.required_finding_ids
        )


def apply_finding_decision(
    draft: FindingDecisionDraft, command: ProposedFindingDecision
) -> FindingDecisionDraft:
    """CAS + idempotent append to a *draft* only. Never commits trusted evidence."""

    if command.scope != draft.scope:
        raise DecisionConflict("Review scope or candidate binding changed")
    if not command.idempotency_key.strip():
        raise ValueError("Idempotency key is required")
    for recorded in draft.entries:
        if recorded.idempotency_key == command.idempotency_key:
            if recorded == command:
                return draft
            raise DecisionConflict("Idempotency key already used for a different decision")
    if command.expected_revision != draft.revision:
        raise DecisionConflict("Decision revision changed; reload the review")
    if command.finding_id not in draft.required_finding_ids:
        raise DecisionConflict("Finding is not bound to this candidate")
    if not command.reason.strip():
        raise ValueError("The reviewer must record a reason")
    if command.action == DecisionAction.CORRECT:
        if not command.proposed_correction:
            raise ValueError("A correction must propose a nonempty changed payload")
    elif command.proposed_correction is not None:
        raise ValueError("Only a correction may include a proposed payload")
    return replace(
        draft,
        revision=draft.revision + 1,
        entries=(*draft.entries, command),
    )
