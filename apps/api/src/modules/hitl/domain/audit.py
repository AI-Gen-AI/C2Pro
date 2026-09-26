"""
Dispute-grade audit entry (ADR-020, TASK-V3-020-03).

Every CM decide() action is recorded here: who / when / what / why /
before-after snapshot / model-or-rule version.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.action_review.domain.action_item import ActionItem
from src.modules.hitl.application.cm_review_queue_service import CMDecision


@dataclass(frozen=True)
class AuditEntry:
    entry_id: UUID
    queue_entry_id: UUID
    reviewer_id: UUID
    reviewer_name: str
    decision: CMDecision
    reason: str
    decided_at: datetime
    action_item_before: ActionItem
    action_item_after: ActionItem
    model_version: str = ""


__all__ = ["AuditEntry"]
