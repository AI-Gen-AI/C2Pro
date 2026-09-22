"""
C2PRO P0b PROD HITL APPROVAL RESUME + REVIEW UX HOTFIX -- direct router
coverage.

Companion to test_p0b_hitl_approve_route_resume_hotfix.py, which proves
end-to-end behavior through the real HTTP route (authenticated_client +
ASGITransport). This file calls the SAME router endpoint functions directly
(the established pattern already used by
tests/unit/modules/hitl/test_snapshot_trigger.py) -- Starlette's own ASGI
request-dispatch path does not register reliably with this project's
coverage.py/Python 3.12 setup for large router modules (verified: a
production log line and a passing status-code assertion both confirm a
guard-clause raise executed through the full HTTP stack, yet coverage.py
shows the same line as never hit; calling the identical function directly,
bypassing Starlette's dispatch, registers it correctly). These direct-call
tests exercise the exact same real production logic (real
SqlAlchemyReviewQueueRepository, real HumanInTheLoopService, real
ResumeWorkflowUseCase) -- only the HTTP transport layer is skipped, which is
what the measurement gap is specific to, not the endpoint bodies themselves.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import Tenant
from src.documents.adapters.persistence.models import DocumentORM
from src.modules.hitl.adapters.http import router as hitl_router
from src.modules.hitl.adapters.http.schemas import (
    ApproveRequest,
    RejectRequest,
    RouteForReviewRequest,
)
from src.modules.hitl.adapters.notifications.log_notification_service import (
    LogNotificationService,
)
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.adapters.persistence.repository import (
    SqlAlchemyReviewQueueRepository,
)
from src.modules.hitl.application.human_in_the_loop_service import HumanInTheLoopService
from src.modules.hitl.application.resume_workflow_use_case import ResumeWorkflowUseCase
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus
from src.modules.hitl.domain.services import ConfidenceRouter
from src.projects.adapters.persistence.models import ProjectORM

pytestmark = pytest.mark.asyncio


def _current_user(name: str = "Direct Test User") -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), full_name=name)


def _service(db: AsyncSession, tenant_id: UUID) -> HumanInTheLoopService:
    repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant_id)
    return HumanInTheLoopService(
        review_queue_repo=repo,
        notification_service=LogNotificationService(),
        confidence_router=ConfidenceRouter(),
    )


class _FakeResumingGraphApp:
    def __init__(self, seed_state: dict | None = None) -> None:
        self.last_state: dict | None = None
        self.seed_state: dict | None = seed_state

    async def aupdate_state(self, config: dict, state: dict) -> None:
        self.last_state = state

    async def ainvoke(self, resume_signal: object, config: dict) -> dict:
        from src.analysis.adapters.graph.nodes import save_to_db_node
        from tests.support.hitl_resume_fakes import decision_from_resume

        # C2PRO P0b true-resume hotfix: resume now arrives as
        # Command(resume=...) and the decision must be read FROM it, the
        # way the real interrupt node reads interrupt()'s return value.
        decision, feedback = decision_from_resume(resume_signal)
        state = dict(self.last_state or self.seed_state or {})
        state["human_decision"] = decision or ""
        state["human_feedback"] = feedback
        if decision == "reject":
            state["human_approval_required"] = False
            state["workflow_terminated"] = True
            state["termination_reason"] = feedback
            return state
        if decision != "approve":
            return {**state, "__interrupt__": ({"reason": "approval_required"},)}
        state["human_approval_required"] = False
        return await save_to_db_node(state)


class _FailingGraphApp:
    async def aupdate_state(self, config: dict, state: dict) -> None:
        return None

    async def ainvoke(self, *args, **kwargs) -> dict:
        raise RuntimeError("checkpointer connection reset")


class _FakeCheckpointService:
    def __init__(self, state: dict) -> None:
        self._state = state

    async def load_checkpoint(self, thread_id: str, checkpoint_id: str | None = None) -> dict:
        return {"id": checkpoint_id or "latest", "channel_values": {"__root__": dict(self._state)}}

    async def restore_checkpoint(self, thread_id: str, checkpoint_id: str | None = None):
        from src.modules.hitl.adapters.checkpoint_service import CheckpointRestore

        configurable: dict = {"thread_id": thread_id, "checkpoint_ns": ""}
        if checkpoint_id:
            configurable["checkpoint_id"] = checkpoint_id
        return CheckpointRestore(
            checkpoint={
                "id": checkpoint_id or "latest",
                "channel_values": {"__root__": dict(self._state)},
            },
            config={"configurable": configurable},
            metadata={},
        )

    def extract_state(self, checkpoint: dict) -> dict:
        return dict(checkpoint["channel_values"]["__root__"])


def _resume_use_case(db: AsyncSession, tenant_id: UUID, state: dict, graph_app) -> ResumeWorkflowUseCase:
    repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant_id)
    return ResumeWorkflowUseCase(
        review_queue_repo=repo,
        checkpoint_service=_FakeCheckpointService(state),
        graph_app=graph_app,
    )


async def _seed_project_and_document(db: AsyncSession, tenant: Tenant) -> DocumentORM:
    project_id, document_id = uuid4(), uuid4()
    db.add(
        ProjectORM(
            id=project_id,
            tenant_id=tenant.id,
            name="Direct Coverage Project",
            code="P0B-DIRECT",
            start_date=datetime.now(),
        )
    )
    await db.commit()
    document = DocumentORM(
        id=document_id,
        tenant_id=tenant.id,
        project_id=project_id,
        document_type="contract",
        filename="contract.pdf",
        upload_status="parsed_pending_analysis",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


def _review_row(
    *,
    tenant_id: UUID,
    project_id: UUID,
    document_id: UUID,
    thread_id: str | None,
    checkpoint_id: str | None,
    status: ReviewStatus = ReviewStatus.PENDING_REVIEW_REQUIRED,
) -> ReviewItemORM:
    return ReviewItemORM(
        id=uuid4(),
        item_id=document_id,
        item_type="contract",
        current_status=status,
        confidence=0.0,
        impact_level=ImpactLevel.HIGH,
        tenant_id=tenant_id,
        sla_due_date=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=3),
        item_data={"project_id": str(project_id), "document_id": str(document_id)},
        review_metadata={"tenant_id": str(tenant_id)},
        checkpoint_id=checkpoint_id,
        thread_id=thread_id,
        project_id=project_id,
        document_id=document_id,
        review_type="analysis_critique",
    )


async def test_direct_route_for_review_returns_full_context(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    document = await _seed_project_and_document(db, tenant)
    item_id = uuid4()

    response = await hitl_router.route_for_review(
        payload=RouteForReviewRequest(
            item_id=item_id,
            item_type="coherence_alert",
            confidence=0.4,
            impact_level=ImpactLevel.HIGH,
            item_data={"document_id": str(document.id)},
        ),
        _tenant_id=tenant.id,
        service=_service(db, tenant.id),
    )

    assert response.item_id == item_id
    assert response.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED
    assert response.resumable is False
    assert response.row_id is not None


async def test_direct_get_review_item_success(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    document = await _seed_project_and_document(db, tenant)
    review = _review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=None,
        checkpoint_id=None,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant.id)
    response = await hitl_router.get_review_item(item_id=review.item_id, _tenant_id=tenant.id, repo=repo)
    assert response.item_id == review.item_id
    assert response.row_id == review.id


async def test_direct_get_review_item_404(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()

    repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant.id)
    with pytest.raises(HTTPException) as exc_info:
        await hitl_router.get_review_item(item_id=uuid4(), _tenant_id=tenant.id, repo=repo)
    assert exc_info.value.status_code == 404


async def test_direct_list_review_queue_dedups_legacy_duplicates(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    document = await _seed_project_and_document(db, tenant)

    adopted = _review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=f"document:{document.id}:analysis",
        checkpoint_id="real-checkpoint-1",
    )
    db.add(adopted)
    for _ in range(3):
        db.add(
            _review_row(
                tenant_id=tenant.id,
                project_id=document.project_id,
                document_id=document.id,
                thread_id=None,
                checkpoint_id=None,
            )
        )
    await db.commit()

    repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant.id)
    response = await hitl_router.list_review_queue(
        _tenant_id=tenant.id,
        status_filter=ReviewStatus.PENDING_REVIEW_REQUIRED,
        skip=0,
        limit=50,
        project_id=document.project_id,
        repo=repo,
    )

    assert response.total == 1
    assert len(response.items) == 1
    assert response.items[0].resumable is True


async def test_direct_approve_resumable_review_reaches_analyzed(db: AsyncSession) -> None:
    from src.analysis.adapters.persistence.models import Analysis

    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    document = await _seed_project_and_document(db, tenant)
    thread_id = f"document:{document.id}:analysis"

    review = _review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=thread_id,
        checkpoint_id="real-checkpoint-1",
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    resume_state = {
        "project_id": str(document.project_id),
        "tenant_id": str(tenant.id),
        "document_id": str(document.id),
        "extracted_risks": [],
        "extracted_wbs": [],
        "coherence_score": 90,
        "coherence_breakdown": {},
        "messages": [],
        "node_results": [],
    }

    response = await hitl_router.approve_item(
        item_id=review.item_id,
        _payload=ApproveRequest(),
        _tenant_id=tenant.id,
        current_user=_current_user(),
        service=_service(db, tenant.id),
        resume_use_case=_resume_use_case(db, tenant.id, resume_state, _FakeResumingGraphApp(resume_state)),
    )

    assert response.current_status == ReviewStatus.APPROVED
    assert response.resumable is True

    analyses = (
        await db.execute(
            select(Analysis).where(Analysis.project_id == document.project_id)
        )
    ).scalars().all()
    assert len(analyses) == 1


async def test_direct_approve_non_resumable_review_succeeds_without_resume(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    document = await _seed_project_and_document(db, tenant)

    review = _review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=None,
        checkpoint_id=None,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    class _ExplodingUseCase:
        async def execute(self, *args, **kwargs):
            raise AssertionError("must not be invoked for a non-resumable review")

    response = await hitl_router.approve_item(
        item_id=review.item_id,
        _payload=ApproveRequest(),
        _tenant_id=tenant.id,
        current_user=_current_user(),
        service=_service(db, tenant.id),
        resume_use_case=_ExplodingUseCase(),
    )

    assert response.current_status == ReviewStatus.APPROVED
    assert response.resumable is False


async def test_direct_approve_nonexistent_review_404(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()

    class _UnusedUseCase:
        async def execute(self, *args, **kwargs):
            raise AssertionError("must not be reached")

    with pytest.raises(HTTPException) as exc_info:
        await hitl_router.approve_item(
            item_id=uuid4(),
            _payload=ApproveRequest(),
            _tenant_id=tenant.id,
            current_user=_current_user(),
            service=_service(db, tenant.id),
            resume_use_case=_UnusedUseCase(),
        )
    assert exc_info.value.status_code == 404


async def test_direct_approve_non_resumable_already_approved_400(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    document = await _seed_project_and_document(db, tenant)

    review = _review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=None,
        checkpoint_id=None,
        status=ReviewStatus.APPROVED,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    class _UnusedUseCase:
        async def execute(self, *args, **kwargs):
            raise AssertionError("must not be reached")

    with pytest.raises(HTTPException) as exc_info:
        await hitl_router.approve_item(
            item_id=review.item_id,
            _payload=ApproveRequest(),
            _tenant_id=tenant.id,
            current_user=_current_user(),
            service=_service(db, tenant.id),
            resume_use_case=_UnusedUseCase(),
        )
    assert exc_info.value.status_code == 400


async def test_direct_approve_resume_failure_returns_502_and_stays_pending(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    document = await _seed_project_and_document(db, tenant)
    thread_id = f"document:{document.id}:analysis"

    review = _review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=thread_id,
        checkpoint_id="real-checkpoint-1",
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    with pytest.raises(HTTPException) as exc_info:
        await hitl_router.approve_item(
            item_id=review.item_id,
            _payload=ApproveRequest(),
            _tenant_id=tenant.id,
            current_user=_current_user(),
            service=_service(db, tenant.id),
            resume_use_case=_resume_use_case(db, tenant.id, {}, _FailingGraphApp()),
        )
    assert exc_info.value.status_code == 502

    refreshed = await db.get(ReviewItemORM, review.id)
    await db.refresh(refreshed)
    # C2PRO P0b true-resume hotfix: inverted on purpose. A failed resume
    # must NOT leave a false APPROVED behind -- the decision is recorded
    # only after the workflow reaches durable completion.
    assert refreshed.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED.value
    assert refreshed.approved_at is None


async def test_direct_approve_already_processed_is_idempotent(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    document = await _seed_project_and_document(db, tenant)
    thread_id = f"document:{document.id}:analysis"

    review = _review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=thread_id,
        checkpoint_id="real-checkpoint-1",
        status=ReviewStatus.APPROVED,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    response = await hitl_router.approve_item(
        item_id=review.item_id,
        _payload=ApproveRequest(),
        _tenant_id=tenant.id,
        current_user=_current_user(),
        service=_service(db, tenant.id),
        resume_use_case=_resume_use_case(db, tenant.id, {}, _FakeResumingGraphApp({})),
    )
    assert response.current_status == ReviewStatus.APPROVED


async def test_direct_reject_resumable_review_terminates_without_n17(db: AsyncSession) -> None:
    from src.analysis.adapters.persistence.models import Analysis

    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    document = await _seed_project_and_document(db, tenant)
    thread_id = f"document:{document.id}:analysis"

    review = _review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=thread_id,
        checkpoint_id="real-checkpoint-1",
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    response = await hitl_router.reject_item(
        item_id=review.item_id,
        payload=RejectRequest(reason="needs correction"),
        _tenant_id=tenant.id,
        current_user=_current_user(),
        service=_service(db, tenant.id),
        resume_use_case=_resume_use_case(db, tenant.id, {"messages": [], "node_results": []}, _FakeResumingGraphApp({"messages": [], "node_results": []})),
    )

    assert response.current_status == ReviewStatus.REJECTED

    analyses = (
        await db.execute(
            select(Analysis).where(Analysis.project_id == document.project_id)
        )
    ).scalars().all()
    assert len(analyses) == 0


async def test_direct_reject_resumable_maps_use_case_not_found_to_404(db: AsyncSession) -> None:
    """A resumable review found by the router's own lookup can still race
    with the resume use case's own (tenant-scoped) lookup -- e.g. deleted
    between the two reads. That ValueError("... not found") must map to
    404, not the generic 400 used for every other ValueError.
    """
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    document = await _seed_project_and_document(db, tenant)

    review = _review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=f"document:{document.id}:analysis",
        checkpoint_id="real-checkpoint-1",
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    class _NotFoundUseCase:
        async def execute(self, *args, **kwargs):
            raise ValueError(f"Review item {review.item_id} not found")

    with pytest.raises(HTTPException) as exc_info:
        await hitl_router.reject_item(
            item_id=review.item_id,
            payload=RejectRequest(reason="race condition"),
            _tenant_id=tenant.id,
            current_user=_current_user(),
            service=_service(db, tenant.id),
            resume_use_case=_NotFoundUseCase(),
        )
    assert exc_info.value.status_code == 404


async def test_direct_reject_non_resumable_review_succeeds_without_resume(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    document = await _seed_project_and_document(db, tenant)

    review = _review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=None,
        checkpoint_id=None,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    class _ExplodingUseCase:
        async def execute(self, *args, **kwargs):
            raise AssertionError("must not be invoked for a non-resumable review")

    response = await hitl_router.reject_item(
        item_id=review.item_id,
        payload=RejectRequest(reason="bad extraction"),
        _tenant_id=tenant.id,
        current_user=_current_user(),
        service=_service(db, tenant.id),
        resume_use_case=_ExplodingUseCase(),
    )
    assert response.current_status == ReviewStatus.REJECTED


async def test_direct_reject_nonexistent_review_404(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()

    class _UnusedUseCase:
        async def execute(self, *args, **kwargs):
            raise AssertionError("must not be reached")

    with pytest.raises(HTTPException) as exc_info:
        await hitl_router.reject_item(
            item_id=uuid4(),
            payload=RejectRequest(reason="n/a"),
            _tenant_id=tenant.id,
            current_user=_current_user(),
            service=_service(db, tenant.id),
            resume_use_case=_UnusedUseCase(),
        )
    assert exc_info.value.status_code == 404


async def test_direct_reject_non_resumable_already_rejected_400(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    document = await _seed_project_and_document(db, tenant)

    review = _review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=None,
        checkpoint_id=None,
        status=ReviewStatus.REJECTED,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    class _UnusedUseCase:
        async def execute(self, *args, **kwargs):
            raise AssertionError("must not be reached")

    with pytest.raises(HTTPException) as exc_info:
        await hitl_router.reject_item(
            item_id=review.item_id,
            payload=RejectRequest(reason="n/a"),
            _tenant_id=tenant.id,
            current_user=_current_user(),
            service=_service(db, tenant.id),
            resume_use_case=_UnusedUseCase(),
        )
    assert exc_info.value.status_code == 400


async def test_direct_reject_resumable_already_processed_400(db: AsyncSession) -> None:
    """The graph-gated reject path's own ValueError -> 400 mapping (a
    review that is not in a pending status, e.g. already CLOSED, cannot be
    rejected -- mirrors the equivalent approve-path test).
    """
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    document = await _seed_project_and_document(db, tenant)

    review = _review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=f"document:{document.id}:analysis",
        checkpoint_id="real-checkpoint-1",
        status=ReviewStatus.CLOSED,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    with pytest.raises(HTTPException) as exc_info:
        await hitl_router.reject_item(
            item_id=review.item_id,
            payload=RejectRequest(reason="n/a"),
            _tenant_id=tenant.id,
            current_user=_current_user(),
            service=_service(db, tenant.id),
            resume_use_case=_resume_use_case(db, tenant.id, {}, _FakeResumingGraphApp({})),
        )
    assert exc_info.value.status_code == 400


async def test_direct_release_approved_item_marks_closed(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    document = await _seed_project_and_document(db, tenant)

    review = _review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=None,
        checkpoint_id=None,
        status=ReviewStatus.APPROVED,
    )
    review.approved_by = "Direct Test User"
    review.approved_at = datetime.now(UTC).replace(tzinfo=None)
    db.add(review)
    await db.commit()
    await db.refresh(review)

    response = await hitl_router.release_item(
        item_id=review.item_id,
        _tenant_id=tenant.id,
        _user_id=uuid4(),
        service=_service(db, tenant.id),
    )

    assert response.current_status == ReviewStatus.CLOSED

    result = await db.execute(select(ReviewItemORM).where(ReviewItemORM.id == review.id))
    row = result.scalar_one()
    assert row.current_status == ReviewStatus.CLOSED


async def test_direct_release_item_not_approved_returns_400(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    document = await _seed_project_and_document(db, tenant)

    review = _review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=None,
        checkpoint_id=None,
        status=ReviewStatus.PENDING_REVIEW_REQUIRED,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    with pytest.raises(HTTPException) as exc_info:
        await hitl_router.release_item(
            item_id=review.item_id,
            _tenant_id=tenant.id,
            _user_id=uuid4(),
            service=_service(db, tenant.id),
        )
    assert exc_info.value.status_code == 400


async def test_direct_release_nonexistent_item_returns_400(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()

    with pytest.raises(HTTPException) as exc_info:
        await hitl_router.release_item(
            item_id=uuid4(),
            _tenant_id=tenant.id,
            _user_id=uuid4(),
            service=_service(db, tenant.id),
        )
    assert exc_info.value.status_code == 400
