"""
Contract-Manager review queue service (ADR-020, TASK-V3-020-01/03).

Bridges ActionItem (ADR-019) → single CM review queue → CM decision →
langgraph resume. The queue discriminator is item_type="cm_action_item".

TASK-V3-020-03 additions:
- decide() writes a dispute-grade AuditEntry (who/when/what/why/before-after)
- enqueue(is_fallback=True) emits a structured WARNING so infra blips that
  route everything to humans do not silently bury reviewers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from src.action_review.domain.action_item import ActionItem, Severity
from src.modules.hitl.application.resume_workflow_use_case import (
    ResumeWorkflowRequest,
    ResumeWorkflowUseCase,
    WorkflowDecision,
)
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus
from src.modules.hitl.ports.review_queue_repository import IReviewQueueRepository

_log = logging.getLogger(__name__)

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

    Optionally accepts an IAuditRepository for dispute-grade audit trail.
    """

    def __init__(
        self,
        review_queue_repo: IReviewQueueRepository,
        resume_use_case: ResumeWorkflowUseCase,
        audit_repository: Any | None = None,
    ) -> None:
        self._repo = review_queue_repo
        self._resume = resume_use_case
        self._audit = audit_repository

    async def enqueue(
        self,
        action_item: ActionItem,
        tenant_id: UUID,
        thread_id: str,
        is_fallback: bool = False,
    ) -> UUID:
        """
        Place an ActionItem in the CM review queue.

        Returns the queue_entry_id (= action_item.id, used as ReviewItem.item_id).

        If is_fallback is True, emits a WARNING — an infrastructure error routed
        this item to humans instead of the normal processing path.
        """
        if is_fallback:
            _log.warning(
                "CM queue: fallback-path enqueue detected — item %s (severity=%s) "
                "was routed via except→interrupt, not normal routing. "
                "Check for upstream infrastructure errors.",
                action_item.id,
                action_item.severity,
            )

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
                "is_fallback": is_fallback,
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
        reviewer_id: UUID,
        reviewer_name: str,
        model_version: str = "",
    ) -> CMDecisionResult:
        """
        Record a CM decision and resume the LangGraph graph.

        - APPROVE: resume graph, item unchanged.
        - REJECT: terminate graph, item unchanged.
        - CORRECT: apply CM corrections, then resume graph as APPROVE.

        Writes an AuditEntry if an audit_repository was provided.
        """
        review_item = await self._repo.get_review_item(queue_entry_id)
        if review_item is None:
            raise ValueError(f"CM queue entry {queue_entry_id} not found")

        action_item_before = _deserialize_action_item(review_item.item_data)
        if action_item_before is None:
            raise ValueError(f"CM queue entry {queue_entry_id} has no valid action_item")

        action_item_after = action_item_before

        # Apply corrections (CORRECT only)
        if request.decision == CMDecision.CORRECT:
            updates: dict[str, Any] = {}
            if request.corrected_recommended_action is not None:
                updates["recommended_action"] = request.corrected_recommended_action
            if request.corrected_severity is not None:
                updates["severity"] = request.corrected_severity
            if updates:
                action_item_after = action_item_before.model_copy(update=updates)

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

        # Dispute-grade audit trail
        if self._audit is not None:
            from src.modules.hitl.domain.audit import AuditEntry

            entry = AuditEntry(
                entry_id=uuid4(),
                queue_entry_id=queue_entry_id,
                reviewer_id=reviewer_id,
                reviewer_name=reviewer_name,
                decision=request.decision,
                reason=request.reason,
                decided_at=datetime.now(UTC),
                action_item_before=action_item_before,
                action_item_after=action_item_after,
                model_version=model_version,
            )
            await self._audit.add_entry(entry)

        return CMDecisionResult(
            queue_entry_id=queue_entry_id,
            decision=request.decision,
            action_item=action_item_after,
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
