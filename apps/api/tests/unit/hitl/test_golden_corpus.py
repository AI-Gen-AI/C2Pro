"""
Tests for HITL-correction → golden-corpus pipeline (TASK-V3-020-04, ADR-020).

RED phase: written before implementation.
Scope: GoldenCandidate model, InMemoryGoldenCandidateRepository,
       CMReviewQueueService wiring (CORRECT → candidate created;
       APPROVE/REJECT → no candidate).
Out of scope: file-based golden case serialisation, LangSmith trace wiring.
"""

from __future__ import annotations

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
from src.modules.hitl.adapters.in_memory_golden_candidate_repository import (
    InMemoryGoldenCandidateRepository,
)
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus
from src.modules.hitl.domain.golden_candidate import GoldenCandidate, GoldenCandidateStatus

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


def _candidate(
    *,
    queue_entry_id: UUID | None = None,
    reviewer_id: UUID | None = None,
) -> GoldenCandidate:
    ai = _action_item()
    return GoldenCandidate(
        candidate_id=uuid.uuid4(),
        source="hitl_correction",
        queue_entry_id=queue_entry_id or uuid.uuid4(),
        action_item_before=ai,
        action_item_after=ai.model_copy(update={"severity": Severity.MEDIUM}),
        correction_reason="CM lowered severity",
        reviewer_id=reviewer_id or uuid.uuid4(),
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# GoldenCandidate model
# ---------------------------------------------------------------------------


class TestGoldenCandidate:
    def test_default_status_is_pending_review(self) -> None:
        c = _candidate()
        assert c.status == GoldenCandidateStatus.PENDING_REVIEW

    def test_fields_accessible(self) -> None:
        c = _candidate()
        assert c.source == "hitl_correction"
        assert c.correction_reason == "CM lowered severity"

    def test_is_immutable(self) -> None:
        c = _candidate()
        with pytest.raises(Exception):
            c.correction_reason = "tampered"  # type: ignore[misc]

    def test_before_after_snapshots_present(self) -> None:
        ai_before = _action_item(Severity.HIGH)
        ai_after = _action_item(Severity.LOW)
        c = GoldenCandidate(
            candidate_id=uuid.uuid4(),
            source="hitl_correction",
            queue_entry_id=uuid.uuid4(),
            action_item_before=ai_before,
            action_item_after=ai_after,
            correction_reason="reduced severity",
            reviewer_id=uuid.uuid4(),
            created_at=datetime.now(UTC),
        )
        assert c.action_item_before.severity == Severity.HIGH
        assert c.action_item_after.severity == Severity.LOW


class TestGoldenCandidateStatus:
    def test_pending_review_value(self) -> None:
        assert GoldenCandidateStatus.PENDING_REVIEW == "pending_review"

    def test_accepted_value(self) -> None:
        assert GoldenCandidateStatus.ACCEPTED == "accepted"

    def test_rejected_value(self) -> None:
        assert GoldenCandidateStatus.REJECTED == "rejected"


# ---------------------------------------------------------------------------
# InMemoryGoldenCandidateRepository
# ---------------------------------------------------------------------------


class TestInMemoryGoldenCandidateRepository:
    @pytest.mark.asyncio
    async def test_add_and_get(self) -> None:
        repo = InMemoryGoldenCandidateRepository()
        c = _candidate()
        await repo.add_candidate(c)
        fetched = await repo.get_candidate(c.candidate_id)
        assert fetched is not None
        assert fetched.candidate_id == c.candidate_id

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self) -> None:
        repo = InMemoryGoldenCandidateRepository()
        assert await repo.get_candidate(uuid.uuid4()) is None

    @pytest.mark.asyncio
    async def test_list_pending(self) -> None:
        repo = InMemoryGoldenCandidateRepository()
        c1 = _candidate()
        c2 = _candidate()
        await repo.add_candidate(c1)
        await repo.add_candidate(c2)
        pending = await repo.list_by_status(GoldenCandidateStatus.PENDING_REVIEW)
        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_list_by_queue_entry(self) -> None:
        repo = InMemoryGoldenCandidateRepository()
        qid = uuid.uuid4()
        c1 = _candidate(queue_entry_id=qid)
        c2 = _candidate()  # different queue entry
        await repo.add_candidate(c1)
        await repo.add_candidate(c2)
        results = await repo.list_by_queue_entry(qid)
        assert len(results) == 1
        assert results[0].candidate_id == c1.candidate_id

    @pytest.mark.asyncio
    async def test_empty_repo_returns_empty_list(self) -> None:
        repo = InMemoryGoldenCandidateRepository()
        assert await repo.list_by_status(GoldenCandidateStatus.PENDING_REVIEW) == []


# ---------------------------------------------------------------------------
# CMReviewQueueService wiring
# ---------------------------------------------------------------------------


class TestCMReviewQueueGoldenCorpusWiring:
    """CORRECT → GoldenCandidate created; APPROVE/REJECT → no candidate."""

    def _mock_queue_repo(self, action_item: ActionItem) -> object:
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
    async def test_correct_decision_creates_golden_candidate(self) -> None:
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
        queue_repo = self._mock_queue_repo(ai)
        resume_uc = AsyncMock(spec=ResumeWorkflowUseCase)
        golden_repo = InMemoryGoldenCandidateRepository()

        svc = CMReviewQueueService(
            review_queue_repo=queue_repo,
            resume_use_case=resume_uc,
            golden_corpus_repository=golden_repo,
        )
        request = CMReviewRequest(
            decision=CMDecision.CORRECT,
            reason="severity should be medium",
            corrected_severity=Severity.MEDIUM,
        )
        reviewer_id = uuid.uuid4()
        await svc.decide(ai.id, request, reviewer_id=reviewer_id, reviewer_name="Alice")

        candidates = await golden_repo.list_by_queue_entry(ai.id)
        assert len(candidates) == 1
        c = candidates[0]
        assert c.source == "hitl_correction"
        assert c.action_item_before.severity == Severity.HIGH
        assert c.action_item_after.severity == Severity.MEDIUM
        assert c.reviewer_id == reviewer_id
        assert c.correction_reason == "severity should be medium"

    @pytest.mark.asyncio
    async def test_approve_does_not_create_golden_candidate(self) -> None:
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
        queue_repo = self._mock_queue_repo(ai)
        resume_uc = AsyncMock(spec=ResumeWorkflowUseCase)
        golden_repo = InMemoryGoldenCandidateRepository()

        svc = CMReviewQueueService(
            review_queue_repo=queue_repo,
            resume_use_case=resume_uc,
            golden_corpus_repository=golden_repo,
        )
        await svc.decide(
            ai.id,
            CMReviewRequest(decision=CMDecision.APPROVE, reason="ok"),
            reviewer_id=uuid.uuid4(),
            reviewer_name="Bob",
        )
        assert await golden_repo.list_by_queue_entry(ai.id) == []

    @pytest.mark.asyncio
    async def test_reject_does_not_create_golden_candidate(self) -> None:
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
        queue_repo = self._mock_queue_repo(ai)
        resume_uc = AsyncMock(spec=ResumeWorkflowUseCase)
        golden_repo = InMemoryGoldenCandidateRepository()

        svc = CMReviewQueueService(
            review_queue_repo=queue_repo,
            resume_use_case=resume_uc,
            golden_corpus_repository=golden_repo,
        )
        await svc.decide(
            ai.id,
            CMReviewRequest(decision=CMDecision.REJECT, reason="invalid"),
            reviewer_id=uuid.uuid4(),
            reviewer_name="Carol",
        )
        assert await golden_repo.list_by_queue_entry(ai.id) == []

    @pytest.mark.asyncio
    async def test_no_golden_repo_still_works(self) -> None:
        """Backward compat: golden_corpus_repository=None means no candidate created."""
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
        queue_repo = self._mock_queue_repo(ai)
        resume_uc = AsyncMock(spec=ResumeWorkflowUseCase)

        svc = CMReviewQueueService(
            review_queue_repo=queue_repo,
            resume_use_case=resume_uc,
            golden_corpus_repository=None,
        )
        result = await svc.decide(
            ai.id,
            CMReviewRequest(
                decision=CMDecision.CORRECT,
                reason="fix",
                corrected_severity=Severity.LOW,
            ),
            reviewer_id=uuid.uuid4(),
            reviewer_name="Dave",
        )
        assert result.action_item.severity == Severity.LOW
