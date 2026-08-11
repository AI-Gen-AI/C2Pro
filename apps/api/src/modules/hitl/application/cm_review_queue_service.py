"""
Contract-Manager review queue service (ADR-020, TASK-V3-020-01).

Bridges ActionItem (ADR-019) → single CM review queue → CM decision →
langgraph resume. The queue discriminator is item_type="cm_action_item".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

from src.action_review.domain.action_item import ActionItem, Severity
from src.modules.hitl.application.resume_workflow_use_case import (
    ResumeWorkflowRequest,
    ResumeWorkflowUseCase,
    WorkflowDecision,
)
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus
from src.modules.hitl.ports.review_queue_repository import IReviewQueueRepository

_ITEM_TYPE = "cm_action_item"
_QUEUE_TAG = "contract_manager"
_SLA_DAYS = 3

_SEVERITY_TO_IMPACT: dict[Severity, ImpactLevel] = {
    Severity.CRITICAL: ImpactLevel.HIGH,
    Severity.HIGH: ImpactLevel.HIGH,
    Severity.MEDIUM: ImpactLevel.MEDIUM,
    Severity.LOW: ImpactLevel.LOW,
    Severity.INFO: ImpactLevel.LOW,
}


class CMDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    CORRECT = "correct"


@dataclass(frozen=True)
class CMReviewRequest:
    """A CM's decision on a queued ActionItem."""

    decision: CMDecision
    reason: str
    corrected_recommended_action: str | None = None
    corrected_severity: Severity | None = None


@dataclass(frozen=True)
class CMQueueEntry:
    """Lightweight CM queue view — what the CM sees in the dashboard."""

    queue_entry_id: UUID
    action_item: ActionItem
    thread_id: str
    tenant_id: UUID
    enqueued_at: datetime


@dataclass(frozen=True)
class CMDecisionResult:
    """Outcome of a CM review decision."""

    queue_entry_id: UUID
    decision: CMDecision
    action_item: ActionItem


class CMReviewQueueService:
    """
    Enqueue ActionItems into the Contract-Manager review queue and process
    CM decisions (approve / reject / correct).

    Uses the existing IReviewQueueRepository for persistence and
    ResumeWorkflowUseCase for LangGraph graph resumption.
    """

    def __init__(
        self,
        review_queue_repo: IReviewQueueRepository,
        resume_use_case: ResumeWorkflowUseCase,
    ) -> None:
        self._repo = review_queue_repo
        self._resume = resume_use_case

    async def enqueue(
        self,
        action_item: ActionItem,
        tenant_id: UUID,
        thread_id: str,
    ) -> UUID:
        """
        Place an ActionItem in the CM review queue.

        Returns the queue_entry_id (= action_item.id, used as ReviewItem.item_id).
        """
        review_item = ReviewItem(
            item_id=action_item.id,
            item_type=_ITEM_TYPE,
            current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
            confidence=action_item.confidence,
            impact_level=_SEVERITY_TO_IMPACT[action_item.severity],
            created_at=datetime.now(UTC),
            sla_due_date=datetime.now(UTC) + timedelta(days=_SLA_DAYS),
            item_data={
                "action_item": action_item.model_dump(mode="json"),
                "thread_id": thread_id,
            },
            metadata={
                "queue": _QUEUE_TAG,
                "tenant_id": str(tenant_id),
                "thread_id": thread_id,
            },
        )
        return await self._repo.add_review_item(review_item)

    async def list_pending(self, tenant_id: UUID) -> list[CMQueueEntry]:
        """Return all pending CM queue entries for a tenant."""
        all_pending = await self._repo.list_by_status(
            ReviewStatus.PENDING_REVIEW_REQUIRED
        )
        entries: list[CMQueueEntry] = []
        tenant_str = str(tenant_id)
        for ri in all_pending:
            if ri.item_type != _ITEM_TYPE:
                continue
            if ri.metadata.get("tenant_id") != tenant_str:
                continue
            ai = _deserialize_action_item(ri.item_data)
            if ai is None:
                continue
            entries.append(
                CMQueueEntry(
                    queue_entry_id=ri.item_id,
                    action_item=ai,
                    thread_id=str(ri.metadata.get("thread_id", "")),
                    tenant_id=tenant_id,
                    enqueued_at=ri.created_at,
                )
            )
        return entries

    async def decide(
        self,
        queue_entry_id: UUID,
        request: CMReviewRequest,
        reviewer_id: UUID,  # noqa: ARG002 — reserved for audit trail (TASK-V3-020-03)
        reviewer_name: str,  # noqa: ARG002 — reserved for audit trail (TASK-V3-020-03)
    ) -> CMDecisionResult:
        """
        Record a CM decision and resume the LangGraph graph.

        - APPROVE: resume graph, item unchanged.
        - REJECT: terminate graph, item unchanged.
        - CORRECT: apply CM corrections, then resume graph as APPROVE.
        """
        review_item = await self._repo.get_review_item(queue_entry_id)
        if review_item is None:
            raise ValueError(f"CM queue entry {queue_entry_id} not found")

        action_item = _deserialize_action_item(review_item.item_data)
        if action_item is None:
            raise ValueError(f"CM queue entry {queue_entry_id} has no valid action_item")

        # Apply corrections (CORRECT only)
        if request.decision == CMDecision.CORRECT:
            updates: dict[str, Any] = {}
            if request.corrected_recommended_action is not None:
                updates["recommended_action"] = request.corrected_recommended_action
            if request.corrected_severity is not None:
                updates["severity"] = request.corrected_severity
            if updates:
                action_item = action_item.model_copy(update=updates)

        # Map to graph-level workflow decision
        workflow_decision = (
            WorkflowDecision.REJECT
            if request.decision == CMDecision.REJECT
            else WorkflowDecision.APPROVE
        )

        resume_req = ResumeWorkflowRequest(
            decision=workflow_decision,
            feedback=request.reason,
        )
        await self._resume.execute(queue_entry_id, resume_req)

        return CMDecisionResult(
            queue_entry_id=queue_entry_id,
            decision=request.decision,
            action_item=action_item,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _deserialize_action_item(item_data: dict[str, Any]) -> ActionItem | None:
    raw = item_data.get("action_item")
    if not isinstance(raw, dict):
        return None
    try:
        return ActionItem.model_validate(raw)
    except Exception:
        return None


__all__ = [
    "CMDecision",
    "CMDecisionResult",
    "CMQueueEntry",
    "CMReviewQueueService",
    "CMReviewRequest",
]
