"""
Golden corpus candidate domain model (ADR-020, TASK-V3-020-04).

A GoldenCandidate is created when a CM makes a CORRECT decision in the
HITL review queue. It captures the before/after ActionItem pair plus the
CM's reason, ready for a human curator to convert into a formal golden
case for the benchmark regression suite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from src.action_review.domain.action_item import ActionItem


class GoldenCandidateStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class GoldenCandidate:
    candidate_id: UUID
    queue_entry_id: UUID
    action_item_before: ActionItem
    action_item_after: ActionItem
    correction_reason: str
    reviewer_id: UUID
    created_at: datetime
    source: str = "hitl_correction"
    status: GoldenCandidateStatus = field(default=GoldenCandidateStatus.PENDING_REVIEW)


__all__ = ["GoldenCandidate", "GoldenCandidateStatus"]
