"""
Tests for CMReviewQueueService (TASK-V3-020-01).

RED phase: tests written before implementation.
Contract: bridge ActionItem → CM review queue → CM decision → graph resume.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from src.action_review.domain.action_item import (
    ActionItem,
    ActionStatus,
    ImpactArea,
    Severity,
)
from src.modules.hitl.application.cm_review_queue_service import (
    CMDecision,
    CMReviewQueueService,
    CMReviewRequest,
)
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TENANT = uuid.uuid4()
_THREAD = "thread-abc-123"


def _action_item(
    severity: Severity = Severity.HIGH,
    status: ActionStatus = ActionStatus.OPEN,
    item_id: UUID | None = None,
) -> ActionItem:
    return ActionItem(
        id=item_id or uuid.uuid4(),
        severity=severity,
        confidence=0.75,
        impact_area=[ImpactArea.CONTRACT, ImpactArea.COST],
        affected_objects=[],
        evidence_refs=[],
        recommended_action="Renegotiate clause 4.2",
        owner_stakeholder_id=None,
        due_at=None,
        escalation_path=[],
        correlation_group=uuid.uuid4(),
        status=status,
    )


def _review_item(
    item_id: UUID,
    *,
    item_type: str = "cm_action_item",
    status: ReviewStatus = ReviewStatus.PENDING_REVIEW_REQUIRED,
    tenant_id: UUID | None = None,
    thread_id: str = _THREAD,
    action_item: ActionItem | None = None,
) -> ReviewItem:
    ai = action_item or _action_item(item_id=item_id)
    return ReviewItem(
        item_id=item_id,
        item_type=item_type,
        current_status=status,
        confidence=0.75,
        impact_level=ImpactLevel.HIGH,
        created_at=datetime.now(UTC),
        sla_due_date=datetime.now(UTC) + timedelta(days=3),
        item_data={
            "action_item": ai.model_dump(mode="json"),
            "thread_id": thread_id,
        },
        metadata={
            "queue": "contract_manager",
            "tenant_id": str(tenant_id or _TENANT),
            "checkpoint_id": "chk-001",
            "thread_id": thread_id,
        },
    )


def _make_service(
    *,
    pending_items: list[ReviewItem] | None = None,
    stored_item: ReviewItem | None = None,
) -> tuple[CMReviewQueueService, AsyncMock, MagicMock]:
    repo = AsyncMock()
    repo.add_review_item = AsyncMock(return_value=uuid.uuid4())
    repo.list_by_status = AsyncMock(return_value=pending_items or [])
    repo.get_review_item = AsyncMock(return_value=stored_item)
    repo.update_review_item = AsyncMock(return_value=None)

    resume_uc = MagicMock()
    resume_uc.execute = AsyncMock(return_value=MagicMock(status="resumed"))

    svc = CMReviewQueueService(review_queue_repo=repo, resume_use_case=resume_uc)
    return svc, repo, resume_uc


# ---------------------------------------------------------------------------
# enqueue()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEnqueue:
    async def test_enqueue_calls_add_review_item(self) -> None:
        svc, repo, _ = _make_service()
        item = _action_item()
        await svc.enqueue(item, tenant_id=_TENANT, thread_id=_THREAD)
        repo.add_review_item.assert_called_once()

    async def test_enqueue_sets_item_type_to_cm_action_item(self) -> None:
        svc, repo, _ = _make_service()
        item = _action_item()
        await svc.enqueue(item, tenant_id=_TENANT, thread_id=_THREAD)
        review_item: ReviewItem = repo.add_review_item.call_args[0][0]
        assert review_item.item_type == "cm_action_item"

    async def test_enqueue_sets_cm_queue_tag_in_metadata(self) -> None:
        svc, repo, _ = _make_service()
        await svc.enqueue(_action_item(), tenant_id=_TENANT, thread_id=_THREAD)
        review_item: ReviewItem = repo.add_review_item.call_args[0][0]
        assert review_item.metadata["queue"] == "contract_manager"

    async def test_enqueue_stores_thread_id_in_metadata(self) -> None:
        svc, repo, _ = _make_service()
        await svc.enqueue(_action_item(), tenant_id=_TENANT, thread_id=_THREAD)
        review_item: ReviewItem = repo.add_review_item.call_args[0][0]
        assert review_item.metadata["thread_id"] == _THREAD

    async def test_enqueue_stores_tenant_id_in_metadata(self) -> None:
        svc, repo, _ = _make_service()
        await svc.enqueue(_action_item(), tenant_id=_TENANT, thread_id=_THREAD)
        review_item: ReviewItem = repo.add_review_item.call_args[0][0]
        assert review_item.metadata["tenant_id"] == str(_TENANT)

    async def test_enqueue_serialises_action_item_in_item_data(self) -> None:
        svc, repo, _ = _make_service()
        item = _action_item()
        await svc.enqueue(item, tenant_id=_TENANT, thread_id=_THREAD)
        review_item: ReviewItem = repo.add_review_item.call_args[0][0]
        assert "action_item" in review_item.item_data
        assert review_item.item_data["action_item"]["id"] == str(item.id)

    async def test_enqueue_status_is_pending_review_required(self) -> None:
        svc, repo, _ = _make_service()
        await svc.enqueue(_action_item(), tenant_id=_TENANT, thread_id=_THREAD)
        review_item: ReviewItem = repo.add_review_item.call_args[0][0]
        assert review_item.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED

    async def test_critical_severity_maps_to_high_impact(self) -> None:
        svc, repo, _ = _make_service()
        await svc.enqueue(_action_item(Severity.CRITICAL), tenant_id=_TENANT, thread_id=_THREAD)
        review_item: ReviewItem = repo.add_review_item.call_args[0][0]
        assert review_item.impact_level == ImpactLevel.HIGH

    async def test_medium_severity_maps_to_medium_impact(self) -> None:
        svc, repo, _ = _make_service()
        await svc.enqueue(_action_item(Severity.MEDIUM), tenant_id=_TENANT, thread_id=_THREAD)
        review_item: ReviewItem = repo.add_review_item.call_args[0][0]
        assert review_item.impact_level == ImpactLevel.MEDIUM

    async def test_low_severity_maps_to_low_impact(self) -> None:
        svc, repo, _ = _make_service()
        await svc.enqueue(_action_item(Severity.LOW), tenant_id=_TENANT, thread_id=_THREAD)
        review_item: ReviewItem = repo.add_review_item.call_args[0][0]
        assert review_item.impact_level == ImpactLevel.LOW

    async def test_info_severity_maps_to_low_impact(self) -> None:
        svc, repo, _ = _make_service()
        await svc.enqueue(_action_item(Severity.INFO), tenant_id=_TENANT, thread_id=_THREAD)
        review_item: ReviewItem = repo.add_review_item.call_args[0][0]
        assert review_item.impact_level == ImpactLevel.LOW


# ---------------------------------------------------------------------------
# list_pending()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestListPending:
    async def test_empty_queue_returns_empty(self) -> None:
        svc, _, _ = _make_service(pending_items=[])
        result = await svc.list_pending(_TENANT)
        assert result == []

    async def test_cm_items_returned(self) -> None:
        item_id = uuid.uuid4()
        ri = _review_item(item_id, tenant_id=_TENANT)
        svc, _, _ = _make_service(pending_items=[ri])
        result = await svc.list_pending(_TENANT)
        assert len(result) == 1
        assert result[0].queue_entry_id == item_id

    async def test_non_cm_items_filtered_out(self) -> None:
        ri = _review_item(uuid.uuid4(), item_type="contract_document", tenant_id=_TENANT)
        svc, _, _ = _make_service(pending_items=[ri])
        result = await svc.list_pending(_TENANT)
        assert result == []

    async def test_other_tenant_items_filtered_out(self) -> None:
        other_tenant = uuid.uuid4()
        ri = _review_item(uuid.uuid4(), tenant_id=other_tenant)
        svc, _, _ = _make_service(pending_items=[ri])
        result = await svc.list_pending(_TENANT)
        assert result == []

    async def test_entry_contains_deserialized_action_item(self) -> None:
        item_id = uuid.uuid4()
        ai = _action_item(item_id=item_id)
        ri = _review_item(item_id, action_item=ai, tenant_id=_TENANT)
        svc, _, _ = _make_service(pending_items=[ri])
        result = await svc.list_pending(_TENANT)
        assert result[0].action_item.id == item_id
        assert result[0].action_item.severity == Severity.HIGH

    async def test_entry_carries_thread_id(self) -> None:
        ri = _review_item(uuid.uuid4(), tenant_id=_TENANT)
        svc, _, _ = _make_service(pending_items=[ri])
        result = await svc.list_pending(_TENANT)
        assert result[0].thread_id == _THREAD

    async def test_multiple_cm_items_all_returned(self) -> None:
        items = [_review_item(uuid.uuid4(), tenant_id=_TENANT) for _ in range(3)]
        svc, _, _ = _make_service(pending_items=items)
        result = await svc.list_pending(_TENANT)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# decide() — APPROVE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDecideApprove:
    async def test_approve_calls_resume_use_case(self) -> None:
        item_id = uuid.uuid4()
        ri = _review_item(item_id, tenant_id=_TENANT)
        svc, _, resume_uc = _make_service(stored_item=ri)
        await svc.decide(
            item_id,
            CMReviewRequest(decision=CMDecision.APPROVE, reason="Looks good"),
            reviewer_id=uuid.uuid4(),
            reviewer_name="CM Alice",
        )
        resume_uc.execute.assert_called_once()

    async def test_approve_passes_approve_decision_to_resume(self) -> None:
        from src.modules.hitl.application.resume_workflow_use_case import WorkflowDecision

        item_id = uuid.uuid4()
        ri = _review_item(item_id, tenant_id=_TENANT)
        svc, _, resume_uc = _make_service(stored_item=ri)
        await svc.decide(
            item_id,
            CMReviewRequest(decision=CMDecision.APPROVE, reason="Approved"),
            reviewer_id=uuid.uuid4(),
            reviewer_name="CM Bob",
        )
        call_args = resume_uc.execute.call_args
        request = call_args[0][1]
        assert request.decision == WorkflowDecision.APPROVE

    async def test_approve_result_decision_is_approve(self) -> None:
        item_id = uuid.uuid4()
        ri = _review_item(item_id, tenant_id=_TENANT)
        svc, _, _ = _make_service(stored_item=ri)
        result = await svc.decide(
            item_id,
            CMReviewRequest(decision=CMDecision.APPROVE, reason="OK"),
            reviewer_id=uuid.uuid4(),
            reviewer_name="CM",
        )
        assert result.decision == CMDecision.APPROVE

    async def test_approve_result_action_item_returned(self) -> None:
        item_id = uuid.uuid4()
        ai = _action_item(item_id=item_id)
        ri = _review_item(item_id, action_item=ai, tenant_id=_TENANT)
        svc, _, _ = _make_service(stored_item=ri)
        result = await svc.decide(
            item_id,
            CMReviewRequest(decision=CMDecision.APPROVE, reason="OK"),
            reviewer_id=uuid.uuid4(),
            reviewer_name="CM",
        )
        assert result.action_item.id == item_id


# ---------------------------------------------------------------------------
# decide() — REJECT
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDecideReject:
    async def test_reject_calls_resume_use_case_with_reject(self) -> None:
        from src.modules.hitl.application.resume_workflow_use_case import WorkflowDecision

        item_id = uuid.uuid4()
        ri = _review_item(item_id, tenant_id=_TENANT)
        svc, _, resume_uc = _make_service(stored_item=ri)
        await svc.decide(
            item_id,
            CMReviewRequest(decision=CMDecision.REJECT, reason="Not acceptable"),
            reviewer_id=uuid.uuid4(),
            reviewer_name="CM",
        )
        call_args = resume_uc.execute.call_args
        request = call_args[0][1]
        assert request.decision == WorkflowDecision.REJECT

    async def test_reject_result_decision_is_reject(self) -> None:
        item_id = uuid.uuid4()
        ri = _review_item(item_id, tenant_id=_TENANT)
        svc, _, _ = _make_service(stored_item=ri)
        result = await svc.decide(
            item_id,
            CMReviewRequest(decision=CMDecision.REJECT, reason="No"),
            reviewer_id=uuid.uuid4(),
            reviewer_name="CM",
        )
        assert result.decision == CMDecision.REJECT


# ---------------------------------------------------------------------------
# decide() — CORRECT
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDecideCorrect:
    async def test_correct_applies_new_recommended_action(self) -> None:
        item_id = uuid.uuid4()
        ai = _action_item(item_id=item_id)
        ri = _review_item(item_id, action_item=ai, tenant_id=_TENANT)
        svc, _, _ = _make_service(stored_item=ri)
        result = await svc.decide(
            item_id,
            CMReviewRequest(
                decision=CMDecision.CORRECT,
                reason="Changed scope",
                corrected_recommended_action="Escalate to legal immediately",
            ),
            reviewer_id=uuid.uuid4(),
            reviewer_name="CM",
        )
        assert result.action_item.recommended_action == "Escalate to legal immediately"

    async def test_correct_applies_new_severity(self) -> None:
        item_id = uuid.uuid4()
        ai = _action_item(item_id=item_id, severity=Severity.MEDIUM)
        ri = _review_item(item_id, action_item=ai, tenant_id=_TENANT)
        svc, _, _ = _make_service(stored_item=ri)
        result = await svc.decide(
            item_id,
            CMReviewRequest(
                decision=CMDecision.CORRECT,
                reason="Severity was wrong",
                corrected_severity=Severity.CRITICAL,
            ),
            reviewer_id=uuid.uuid4(),
            reviewer_name="CM",
        )
        assert result.action_item.severity == Severity.CRITICAL

    async def test_correct_resumes_graph_as_approve(self) -> None:
        from src.modules.hitl.application.resume_workflow_use_case import WorkflowDecision

        item_id = uuid.uuid4()
        ri = _review_item(item_id, tenant_id=_TENANT)
        svc, _, resume_uc = _make_service(stored_item=ri)
        await svc.decide(
            item_id,
            CMReviewRequest(
                decision=CMDecision.CORRECT,
                reason="Fixed",
                corrected_recommended_action="New action",
            ),
            reviewer_id=uuid.uuid4(),
            reviewer_name="CM",
        )
        resume_uc.execute.assert_called_once()
        call_args = resume_uc.execute.call_args
        request = call_args[0][1]
        assert request.decision == WorkflowDecision.APPROVE

    async def test_correct_without_changes_returns_original_item(self) -> None:
        item_id = uuid.uuid4()
        ai = _action_item(item_id=item_id)
        ri = _review_item(item_id, action_item=ai, tenant_id=_TENANT)
        svc, _, _ = _make_service(stored_item=ri)
        result = await svc.decide(
            item_id,
            CMReviewRequest(decision=CMDecision.CORRECT, reason="No changes needed"),
            reviewer_id=uuid.uuid4(),
            reviewer_name="CM",
        )
        assert result.action_item.recommended_action == ai.recommended_action
        assert result.action_item.severity == ai.severity

    async def test_correct_result_is_immutable_action_item(self) -> None:
        item_id = uuid.uuid4()
        ai = _action_item(item_id=item_id)
        ri = _review_item(item_id, action_item=ai, tenant_id=_TENANT)
        svc, _, _ = _make_service(stored_item=ri)
        result = await svc.decide(
            item_id,
            CMReviewRequest(
                decision=CMDecision.CORRECT,
                reason="Fix",
                corrected_recommended_action="Updated",
            ),
            reviewer_id=uuid.uuid4(),
            reviewer_name="CM",
        )
        with pytest.raises(Exception):
            result.action_item.recommended_action = "mutate"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# decide() — error cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDecideErrors:
    async def test_decide_not_found_raises_value_error(self) -> None:
        svc, repo, _ = _make_service(stored_item=None)
        repo.get_review_item = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not found"):
            await svc.decide(
                uuid.uuid4(),
                CMReviewRequest(decision=CMDecision.APPROVE, reason="x"),
                reviewer_id=uuid.uuid4(),
                reviewer_name="CM",
            )
