"""
Tests for dispute-grade audit trail (TASK-V3-020-03, ADR-020).

RED phase: written before implementation.
Scope: AuditEntry model, InMemoryAuditRepository, CMReviewQueueService
       audit-write behaviour, fallback-path alert logging.
Out of scope: database-backed audit store, HTTP endpoints.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from uuid import UUID

import pytest

from src.action_review.domain.action_item import (
    ActionItem,
    ActionStatus,
    ImpactArea,
    Severity,
)
from src.modules.hitl.adapters.in_memory_audit_repository import InMemoryAuditRepository
from src.modules.hitl.domain.audit import AuditEntry
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _action_item(severity: Severity = Severity.HIGH) -> ActionItem:
    return ActionItem(
        id=uuid.uuid4(),
        severity=severity,
        confidence=0.8,
        impact_area=[ImpactArea.CONTRACT],
        affected_objects=[],
        evidence_refs=[],
        recommended_action="Review clause 12",
        owner_stakeholder_id=None,
        due_at=None,
        escalation_path=[],
        correlation_group=uuid.uuid4(),
        status=ActionStatus.OPEN,
    )


def _entry(
    *,
    queue_entry_id: UUID | None = None,
    reviewer_id: UUID | None = None,
    decision: str = "approve",
) -> AuditEntry:
    from src.modules.hitl.application.cm_review_queue_service import CMDecision

    ai = _action_item()
    return AuditEntry(
        entry_id=uuid.uuid4(),
        queue_entry_id=queue_entry_id or uuid.uuid4(),
        reviewer_id=reviewer_id or uuid.uuid4(),
        reviewer_name="Alice CM",
        decision=CMDecision(decision),
        reason="LGTM",
        decided_at=datetime.now(UTC),
        action_item_before=ai,
        action_item_after=ai,
        model_version="claude-sonnet-4-6",
    )


# ---------------------------------------------------------------------------
# AuditEntry model
# ---------------------------------------------------------------------------


class TestAuditEntry:
    def test_fields_accessible(self) -> None:
        e = _entry()
        assert e.reviewer_name == "Alice CM"
        assert e.reason == "LGTM"
        assert e.model_version == "claude-sonnet-4-6"

    def test_is_immutable(self) -> None:
        e = _entry()
        with pytest.raises(Exception):
            e.reason = "tampered"  # type: ignore[misc]

    def test_before_and_after_fields_present(self) -> None:
        ai_before = _action_item(Severity.HIGH)
        ai_after = _action_item(Severity.MEDIUM)
        from src.modules.hitl.application.cm_review_queue_service import CMDecision

        e = AuditEntry(
            entry_id=uuid.uuid4(),
            queue_entry_id=uuid.uuid4(),
            reviewer_id=uuid.uuid4(),
            reviewer_name="Bob",
            decision=CMDecision.CORRECT,
            reason="severity too high",
            decided_at=datetime.now(UTC),
            action_item_before=ai_before,
            action_item_after=ai_after,
            model_version="",
        )
        assert e.action_item_before.severity == Severity.HIGH
        assert e.action_item_after.severity == Severity.MEDIUM


# ---------------------------------------------------------------------------
# InMemoryAuditRepository
# ---------------------------------------------------------------------------


class TestInMemoryAuditRepository:
    @pytest.mark.asyncio
    async def test_add_and_list_by_queue_entry(self) -> None:
        repo = InMemoryAuditRepository()
        e = _entry()
        await repo.add_entry(e)
        entries = await repo.list_by_queue_entry(e.queue_entry_id)
        assert len(entries) == 1
        assert entries[0].entry_id == e.entry_id

    @pytest.mark.asyncio
    async def test_list_returns_empty_for_unknown_id(self) -> None:
        repo = InMemoryAuditRepository()
        entries = await repo.list_by_queue_entry(uuid.uuid4())
        assert entries == []

    @pytest.mark.asyncio
    async def test_multiple_entries_same_queue(self) -> None:
        repo = InMemoryAuditRepository()
        qid = uuid.uuid4()
        e1 = _entry(queue_entry_id=qid)
        e2 = _entry(queue_entry_id=qid)
        await repo.add_entry(e1)
        await repo.add_entry(e2)
        entries = await repo.list_by_queue_entry(qid)
        assert len(entries) == 2

    @pytest.mark.asyncio
    async def test_entries_isolated_by_queue_entry(self) -> None:
        repo = InMemoryAuditRepository()
        qid1, qid2 = uuid.uuid4(), uuid.uuid4()
        await repo.add_entry(_entry(queue_entry_id=qid1))
        await repo.add_entry(_entry(queue_entry_id=qid2))
        assert len(await repo.list_by_queue_entry(qid1)) == 1
        assert len(await repo.list_by_queue_entry(qid2)) == 1

    @pytest.mark.asyncio
    async def test_get_by_entry_id(self) -> None:
        repo = InMemoryAuditRepository()
        e = _entry()
        await repo.add_entry(e)
        fetched = await repo.get_entry(e.entry_id)
        assert fetched is not None
        assert fetched.entry_id == e.entry_id

    @pytest.mark.asyncio
    async def test_get_by_entry_id_missing_returns_none(self) -> None:
        repo = InMemoryAuditRepository()
        assert await repo.get_entry(uuid.uuid4()) is None


# ---------------------------------------------------------------------------
# CMReviewQueueService — audit trail integration
# ---------------------------------------------------------------------------


class TestCMReviewQueueServiceAuditTrail:
    """decide() must write an AuditEntry with correct who/when/what/before-after."""

    def _mock_repo(self, action_item: ActionItem) -> object:
        from unittest.mock import AsyncMock

        review_item = ReviewItem(
            item_id=action_item.id,
            item_type="cm_action_item",
            current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
            confidence=action_item.confidence,
            impact_level=ImpactLevel.HIGH,
            created_at=datetime.now(UTC),
            sla_due_date=datetime.now(UTC),
            item_data={"action_item": action_item.model_dump(mode="json"), "thread_id": "t-1"},
            metadata={"queue": "contract_manager", "tenant_id": str(uuid.uuid4()), "thread_id": "t-1"},
        )
        repo = AsyncMock()
        repo.get_review_item.return_value = review_item
        return repo

    @pytest.mark.asyncio
    async def test_decide_writes_audit_entry(self) -> None:
        from unittest.mock import AsyncMock

        from src.modules.hitl.application.cm_review_queue_service import (
            CMDecision,
            CMReviewQueueService,
            CMReviewRequest,
        )
        from src.modules.hitl.application.resume_workflow_use_case import (
            ResumeWorkflowUseCase,
        )

        ai = _action_item()
        queue_repo = self._mock_repo(ai)
        resume_uc = AsyncMock(spec=ResumeWorkflowUseCase)
        audit_repo = InMemoryAuditRepository()

        svc = CMReviewQueueService(
            review_queue_repo=queue_repo,
            resume_use_case=resume_uc,
            audit_repository=audit_repo,
        )
        reviewer_id = uuid.uuid4()
        request = CMReviewRequest(decision=CMDecision.APPROVE, reason="All good")

        await svc.decide(ai.id, request, reviewer_id=reviewer_id, reviewer_name="Alice")

        entries = await audit_repo.list_by_queue_entry(ai.id)
        assert len(entries) == 1
        e = entries[0]
        assert e.reviewer_id == reviewer_id
        assert e.reviewer_name == "Alice"
        assert e.decision == CMDecision.APPROVE
        assert e.reason == "All good"
        assert e.action_item_before == ai
        assert e.action_item_after == ai  # APPROVE: no change

    @pytest.mark.asyncio
    async def test_correct_decision_captures_before_and_after(self) -> None:
        from unittest.mock import AsyncMock

        from src.modules.hitl.application.cm_review_queue_service import (
            CMDecision,
            CMReviewQueueService,
            CMReviewRequest,
        )
        from src.modules.hitl.application.resume_workflow_use_case import (
            ResumeWorkflowUseCase,
        )

        ai = _action_item(Severity.HIGH)
        queue_repo = self._mock_repo(ai)
        resume_uc = AsyncMock(spec=ResumeWorkflowUseCase)
        audit_repo = InMemoryAuditRepository()

        svc = CMReviewQueueService(
            review_queue_repo=queue_repo,
            resume_use_case=resume_uc,
            audit_repository=audit_repo,
        )
        request = CMReviewRequest(
            decision=CMDecision.CORRECT,
            reason="severity wrong",
            corrected_severity=Severity.MEDIUM,
        )

        result = await svc.decide(ai.id, request, reviewer_id=uuid.uuid4(), reviewer_name="Bob")

        entries = await audit_repo.list_by_queue_entry(ai.id)
        assert len(entries) == 1
        e = entries[0]
        assert e.action_item_before.severity == Severity.HIGH
        assert e.action_item_after.severity == Severity.MEDIUM
        assert result.action_item.severity == Severity.MEDIUM

    @pytest.mark.asyncio
    async def test_decide_without_audit_repo_still_works(self) -> None:
        """Backward compat: audit_repository=None means no audit writing."""
        from unittest.mock import AsyncMock

        from src.modules.hitl.application.cm_review_queue_service import (
            CMDecision,
            CMReviewQueueService,
            CMReviewRequest,
        )
        from src.modules.hitl.application.resume_workflow_use_case import (
            ResumeWorkflowUseCase,
        )

        ai = _action_item()
        queue_repo = self._mock_repo(ai)
        resume_uc = AsyncMock(spec=ResumeWorkflowUseCase)

        svc = CMReviewQueueService(
            review_queue_repo=queue_repo,
            resume_use_case=resume_uc,
            audit_repository=None,
        )
        request = CMReviewRequest(decision=CMDecision.APPROVE, reason="ok")
        result = await svc.decide(ai.id, request, reviewer_id=uuid.uuid4(), reviewer_name="X")
        assert result.decision == CMDecision.APPROVE

    @pytest.mark.asyncio
    async def test_audit_entry_timestamp_is_recent(self) -> None:
        from unittest.mock import AsyncMock

        from src.modules.hitl.application.cm_review_queue_service import (
            CMDecision,
            CMReviewQueueService,
            CMReviewRequest,
        )
        from src.modules.hitl.application.resume_workflow_use_case import (
            ResumeWorkflowUseCase,
        )

        ai = _action_item()
        queue_repo = self._mock_repo(ai)
        resume_uc = AsyncMock(spec=ResumeWorkflowUseCase)
        audit_repo = InMemoryAuditRepository()

        svc = CMReviewQueueService(
            review_queue_repo=queue_repo,
            resume_use_case=resume_uc,
            audit_repository=audit_repo,
        )
        before = datetime.now(UTC)
        await svc.decide(
            ai.id,
            CMReviewRequest(decision=CMDecision.REJECT, reason="invalid"),
            reviewer_id=uuid.uuid4(),
            reviewer_name="Y",
        )
        after = datetime.now(UTC)

        entries = await audit_repo.list_by_queue_entry(ai.id)
        assert before <= entries[0].decided_at <= after


# ---------------------------------------------------------------------------
# Fallback-path alert
# ---------------------------------------------------------------------------


class TestFallbackPathAlert:
    """enqueue(is_fallback=True) must emit a structured warning log."""

    @pytest.mark.asyncio
    async def test_fallback_enqueue_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        from unittest.mock import AsyncMock

        from src.modules.hitl.application.cm_review_queue_service import (
            CMReviewQueueService,
        )
        from src.modules.hitl.application.resume_workflow_use_case import (
            ResumeWorkflowUseCase,
        )

        ai = _action_item()
        queue_repo = AsyncMock()
        queue_repo.add_review_item.return_value = ai.id
        resume_uc = AsyncMock(spec=ResumeWorkflowUseCase)

        svc = CMReviewQueueService(
            review_queue_repo=queue_repo,
            resume_use_case=resume_uc,
        )

        with caplog.at_level(logging.WARNING, logger="src.modules.hitl"):
            await svc.enqueue(ai, tenant_id=uuid.uuid4(), thread_id="t-1", is_fallback=True)

        assert any("fallback" in r.message.lower() for r in caplog.records)

    @pytest.mark.asyncio
    async def test_normal_enqueue_does_not_log_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        from unittest.mock import AsyncMock

        from src.modules.hitl.application.cm_review_queue_service import (
            CMReviewQueueService,
        )
        from src.modules.hitl.application.resume_workflow_use_case import (
            ResumeWorkflowUseCase,
        )

        ai = _action_item()
        queue_repo = AsyncMock()
        queue_repo.add_review_item.return_value = ai.id
        resume_uc = AsyncMock(spec=ResumeWorkflowUseCase)

        svc = CMReviewQueueService(
            review_queue_repo=queue_repo,
            resume_use_case=resume_uc,
        )

        with caplog.at_level(logging.WARNING, logger="src.modules.hitl"):
            await svc.enqueue(ai, tenant_id=uuid.uuid4(), thread_id="t-1", is_fallback=False)

        fallback_warnings = [r for r in caplog.records if "fallback" in r.message.lower()]
        assert fallback_warnings == []
