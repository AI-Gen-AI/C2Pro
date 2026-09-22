"""
C2PRO P0b PROD HITL APPROVAL RESUME + REVIEW UX HOTFIX.

Production evidence: POST /api/v1/hitl/queue/{item_id}/approve returned 200
and the adopted review row flipped to APPROVED -- but ResumeWorkflowUseCase
was never invoked. No analyses row, no graph.completed, document stuck at
parsed_pending_analysis, Health never readable. Subsequent approve clicks on
the 3 remaining legacy duplicate rows (all sharing the same item_id) then
returned an ambiguous 400.

Proves, against the real production route (not just the use case directly):

1. Approving a review carrying a real thread_id resumes the SAME LangGraph
   workflow -- the real N17 executes, an analyses row persists,
   graph.completed is emitted, the document becomes ANALYZED, and the
   persisted single_document_assessment fragment (Health's read model) is
   readable.
2. Legacy duplicate rows (same item_id, no thread_id) are not presented as
   separate actionable decisions in GET /queue.
3. Approve targets the EXACT review row (by row_id), never a sibling
   duplicate.
4. A second approval of an already-approved review is idempotent (200, not
   an ambiguous 400).
5. Tenant isolation remains intact.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import Tenant, User
from src.documents.adapters.persistence.models import DocumentORM
from src.modules.hitl.adapters.http.dependencies import get_resume_workflow_use_case
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.adapters.persistence.repository import (
    SqlAlchemyReviewQueueRepository,
)
from src.modules.hitl.application.resume_workflow_use_case import ResumeWorkflowUseCase
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus
from src.projects.adapters.persistence.models import ProjectORM

pytestmark = pytest.mark.asyncio


class _FakeResumingGraphApp:
    """Resumes by invoking the REAL N17 save_to_db_node -- so persisted
    analysis rows, the graph.completed event, and the returned analysis_id
    are all genuine, not stubbed.
    """

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


class _FakeResumeCheckpointService:
    def __init__(self, state: dict) -> None:
        self._state = state
        self.loaded: list[tuple[str, str | None]] = []

    async def load_checkpoint(self, thread_id: str, checkpoint_id: str | None = None) -> dict:
        self.loaded.append((thread_id, checkpoint_id))
        return {"id": checkpoint_id or "latest", "channel_values": {"__root__": dict(self._state)}}

    async def restore_checkpoint(self, thread_id: str, checkpoint_id: str | None = None):
        from src.modules.hitl.adapters.checkpoint_service import CheckpointRestore

        self.loaded.append((thread_id, checkpoint_id))
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


async def _seed_project_and_document(db: AsyncSession, tenant: Tenant) -> DocumentORM:
    project_id, document_id = uuid4(), uuid4()
    db.add(
        ProjectORM(
            id=project_id,
            tenant_id=tenant.id,
            name="P0b Approve/Resume Hotfix Project",
            code="P0B-APPROVE",
            start_date=datetime.now(),
        )
    )
    await db.commit()
    document = DocumentORM(
        id=document_id,
        tenant_id=tenant.id,
        project_id=project_id,
        document_type="contract",
        filename="contract_english_only.pdf",
        upload_status="parsed_pending_analysis",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


def _make_review_row(
    *,
    tenant_id: UUID,
    project_id: UUID,
    document_id: UUID,
    thread_id: str | None,
    checkpoint_id: str | None,
    status: ReviewStatus = ReviewStatus.PENDING_REVIEW_REQUIRED,
    created_offset_minutes: float = 0,
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
        item_data={
            "project_id": str(project_id),
            "document_id": str(document_id),
            "document_filename": "contract_english_only.pdf",
            "reason": "This document was flagged as high impact and requires human review.",
        },
        review_metadata={
            "tenant_id": str(tenant_id),
        },
        checkpoint_id=checkpoint_id,
        thread_id=thread_id,
        project_id=project_id,
        document_id=document_id,
        review_type="analysis_critique",
        created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=created_offset_minutes),
    )


def _override_resume_use_case(app, db: AsyncSession, tenant_id: UUID, resume_state: dict):
    resuming_app = _FakeResumingGraphApp(resume_state)
    checkpoint_service = _FakeResumeCheckpointService(resume_state)

    def _use_case() -> ResumeWorkflowUseCase:
        repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant_id)
        return ResumeWorkflowUseCase(
            review_queue_repo=repo,
            checkpoint_service=checkpoint_service,
            graph_app=resuming_app,
        )

    app.dependency_overrides[get_resume_workflow_use_case] = _use_case
    return resuming_app, checkpoint_service


async def test_approve_via_queue_route_resumes_to_analyzed_and_health_readable(
    authenticated_client: AsyncClient,
    app,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Objective A + D.1: the REAL production approve route resumes the
    SAME LangGraph thread/checkpoint -- N17 executes for real, an analyses
    row persists, graph.completed is emitted, the document becomes
    ANALYZED, and Health's single_document_assessment is readable.
    """
    from src.analysis.adapters.persistence.models import Analysis
    from src.temporal.adapters.persistence.models import ProjectEventORM

    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed_project_and_document(db, tenant)
    thread_id = f"document:{document.id}:analysis"
    checkpoint_id = "1f1b4d1e-5c6e-6c06-800c-6d08ba742545"

    review = _make_review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=thread_id,
        checkpoint_id=checkpoint_id,
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
        "coherence_breakdown": {"overall": 90},
        "single_document_assessment": {
            "single_document_assessment": {
                "evidence_granularity": "document",
                "proof_marker": "p0b-approve-route-health-readable",
            }
        },
        "messages": [],
        "node_results": [],
    }
    resuming_app, checkpoint_service = _override_resume_use_case(app, db, tenant.id, resume_state)

    response = await authenticated_client.post(
        f"/api/v1/hitl/queue/{review.item_id}/approve",
        json={},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["current_status"] == "APPROVED"
    assert body["resumable"] is True
    assert body["row_id"] == str(review.id)
    assert checkpoint_service.loaded == [(thread_id, checkpoint_id)]

    analyses = (
        await db.execute(select(Analysis).where(Analysis.project_id == document.project_id))
    ).scalars().all()
    assert len(analyses) == 1, "N17 must have run for real and persisted an analysis"
    analysis_row = analyses[0]

    assert (
        analysis_row.result_json.get("single_document_assessment", {}).get("proof_marker")
        == "p0b-approve-route-health-readable"
    )

    events = (
        await db.execute(
            select(ProjectEventORM).where(
                ProjectEventORM.project_id == document.project_id,
                ProjectEventORM.event_type == "graph.completed",
            )
        )
    ).scalars().all()
    assert len(events) == 1

    refreshed_document = await db.get(DocumentORM, document.id)
    await db.refresh(refreshed_document)
    assert refreshed_document.upload_status == "analyzed"


async def test_approve_route_defines_explicit_failure_semantics_on_resume_error(
    authenticated_client: AsyncClient,
    app,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Objective A: a resume failure must never look like a clean success."""
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed_project_and_document(db, tenant)
    thread_id = f"document:{document.id}:analysis"

    review = _make_review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=thread_id,
        checkpoint_id="real-checkpoint-1",
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    class _ExplodingGraphApp:
        async def aupdate_state(self, config: dict, state: dict) -> None:
            return None

        async def ainvoke(self, _resume_signal: None, config: dict) -> dict:
            raise RuntimeError("checkpointer connection reset")

    checkpoint_service = _FakeResumeCheckpointService({"tenant_id": str(tenant.id)})

    from tests.support.hitl_resume_fakes import claim_session_factory_for

    def _use_case() -> ResumeWorkflowUseCase:
        repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant.id)
        return ResumeWorkflowUseCase(
            review_queue_repo=repo,
            checkpoint_service=checkpoint_service,
            graph_app=_ExplodingGraphApp(),
            claim_session_factory=claim_session_factory_for(db),
        )

    app.dependency_overrides[get_resume_workflow_use_case] = _use_case

    response = await authenticated_client.post(
        f"/api/v1/hitl/queue/{review.item_id}/approve",
        json={},
    )

    # Explicit failure: never a bland 200 that looks like success.
    assert response.status_code == 502, response.text

    refreshed = await db.get(ReviewItemORM, review.id)
    await db.refresh(refreshed)
    # C2PRO P0b true-resume hotfix: this assertion is INVERTED on purpose.
    # It previously asserted APPROVED after a failed resume -- the old
    # "record the decision first, swallow graph errors" contract, which made
    # the system claim a successful approval while N17 had never executed.
    # A decision is now recorded only once the workflow actually reached
    # durable completion, so a failed resume must leave the review genuinely
    # pending and retryable.
    assert refreshed.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED.value
    assert refreshed.approved_at is None
    assert (refreshed.review_metadata or {}).get("resume_claim") is None, (
        "the claim must be released so the review stays retryable"
    )


async def test_legacy_duplicates_hidden_from_queue_list(
    authenticated_client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Objective B + D.2: 4 rows share one item_id (the exact production
    shape) -- the queue list must show exactly ONE actionable entry, the
    adopted (thread_id-carrying) row.
    """
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed_project_and_document(db, tenant)

    adopted = _make_review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=f"document:{document.id}:analysis",
        checkpoint_id="real-checkpoint-1",
        created_offset_minutes=0,
    )
    db.add(adopted)
    for i in range(1, 4):
        db.add(
            _make_review_row(
                tenant_id=tenant.id,
                project_id=document.project_id,
                document_id=document.id,
                thread_id=None,
                checkpoint_id=None,
                created_offset_minutes=float(i),
            )
        )
    await db.commit()
    await db.refresh(adopted)

    response = await authenticated_client.get(
        "/api/v1/hitl/queue",
        params={"project_id": str(document.project_id), "status": "PENDING_REVIEW_REQUIRED"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1, "legacy duplicates must not inflate the reported total"
    assert len(body["items"]) == 1
    assert body["items"][0]["row_id"] == str(adopted.id)
    assert body["items"][0]["resumable"] is True

    # The 3 legacy rows are untouched in the DB -- never deleted, just not
    # rendered as separate actionable decisions.
    all_rows = (
        await db.execute(select(ReviewItemORM).where(ReviewItemORM.document_id == document.id))
    ).scalars().all()
    assert len(all_rows) == 4


async def test_approve_targets_exact_row_never_a_sibling(
    authenticated_client: AsyncClient,
    app,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Objective B + D.3: approving BY row_id must affect only that exact
    row, even when 3 sibling rows share the same item_id.
    """
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed_project_and_document(db, tenant)

    target = _make_review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=None,
        checkpoint_id=None,
        created_offset_minutes=5,  # older than the siblings below
    )
    siblings = [
        _make_review_row(
            tenant_id=tenant.id,
            project_id=document.project_id,
            document_id=document.id,
            thread_id=None,
            checkpoint_id=None,
            created_offset_minutes=float(i),
        )
        for i in range(3)
    ]
    db.add(target)
    for s in siblings:
        db.add(s)
    await db.commit()
    await db.refresh(target)
    for s in siblings:
        await db.refresh(s)

    # `target` is NOT the most-recently-created row (the siblings are), so
    # approving via bare item_id would resolve to a DIFFERENT row than
    # `target`. Approving by its own row_id must hit exactly `target`.
    response = await authenticated_client.post(
        f"/api/v1/hitl/queue/{target.id}/approve",
        json={},
    )

    assert response.status_code == 200, response.text
    assert response.json()["row_id"] == str(target.id)

    refreshed_target = await db.get(ReviewItemORM, target.id)
    await db.refresh(refreshed_target)
    assert refreshed_target.current_status == ReviewStatus.APPROVED.value

    for s in siblings:
        refreshed_sibling = await db.get(ReviewItemORM, s.id)
        await db.refresh(refreshed_sibling)
        assert refreshed_sibling.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED.value


async def test_second_approval_is_idempotent_not_an_ambiguous_400(
    authenticated_client: AsyncClient,
    app,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Objective D.4: approving an already-approved graph-gated review must
    be idempotent, not the ambiguous 400 production hit on the legacy
    duplicate shape.
    """
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed_project_and_document(db, tenant)
    thread_id = f"document:{document.id}:analysis"

    review = _make_review_row(
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
    _override_resume_use_case(app, db, tenant.id, resume_state)

    first = await authenticated_client.post(f"/api/v1/hitl/queue/{review.item_id}/approve", json={})
    assert first.status_code == 200, first.text

    second = await authenticated_client.post(f"/api/v1/hitl/queue/{review.item_id}/approve", json={})
    assert second.status_code == 200, second.text
    assert second.json()["current_status"] == "APPROVED"


async def test_tenant_isolation_remains_intact(
    authenticated_client: AsyncClient,
    db: AsyncSession,
    test_user: User,
    test_tenant_2: Tenant,
) -> None:
    """Objective D.6: a review belonging to a different tenant is invisible
    and unapprovable through this tenant's authenticated client.
    """
    document = await _seed_project_and_document(db, test_tenant_2)
    other_review = _make_review_row(
        tenant_id=test_tenant_2.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=f"document:{document.id}:analysis",
        checkpoint_id="real-checkpoint-1",
    )
    db.add(other_review)
    await db.commit()
    await db.refresh(other_review)

    get_response = await authenticated_client.get(f"/api/v1/hitl/queue/{other_review.item_id}")
    assert get_response.status_code == 404

    approve_response = await authenticated_client.post(
        f"/api/v1/hitl/queue/{other_review.item_id}/approve", json={}
    )
    assert approve_response.status_code == 404

    refreshed = await db.get(ReviewItemORM, other_review.id)
    await db.refresh(refreshed)
    assert refreshed.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED.value


async def test_row_id_fallback_cannot_bypass_tenant_isolation(
    authenticated_client: AsyncClient,
    db: AsyncSession,
    test_user: User,
    test_tenant_2: Tenant,
) -> None:
    """get_review_item()'s row-id-first lookup must stay tenant-scoped --
    knowing another tenant's row_id must not let it resolve or be approved.
    """
    document = await _seed_project_and_document(db, test_tenant_2)
    other_review = _make_review_row(
        tenant_id=test_tenant_2.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=f"document:{document.id}:analysis",
        checkpoint_id="real-checkpoint-1",
    )
    db.add(other_review)
    await db.commit()
    await db.refresh(other_review)

    # Address the row directly by its own primary key (row_id), not item_id.
    get_by_row_id = await authenticated_client.get(f"/api/v1/hitl/queue/{other_review.id}")
    assert get_by_row_id.status_code == 404

    approve_by_row_id = await authenticated_client.post(
        f"/api/v1/hitl/queue/{other_review.id}/approve", json={}
    )
    assert approve_by_row_id.status_code == 404

    refreshed = await db.get(ReviewItemORM, other_review.id)
    await db.refresh(refreshed)
    assert refreshed.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED.value


async def test_reject_tenant_isolation_remains_intact(
    authenticated_client: AsyncClient,
    db: AsyncSession,
    test_user: User,
    test_tenant_2: Tenant,
) -> None:
    document = await _seed_project_and_document(db, test_tenant_2)
    other_review = _make_review_row(
        tenant_id=test_tenant_2.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=None,
        checkpoint_id=None,
    )
    db.add(other_review)
    await db.commit()
    await db.refresh(other_review)

    reject_response = await authenticated_client.post(
        f"/api/v1/hitl/queue/{other_review.item_id}/reject", json={"reason": "not mine"}
    )
    assert reject_response.status_code == 404

    refreshed = await db.get(ReviewItemORM, other_review.id)
    await db.refresh(refreshed)
    assert refreshed.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED.value


async def test_route_for_review_endpoint_still_works(
    authenticated_client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """POST /route is untouched behaviorally by this hotfix (only its
    response construction was refactored through _to_review_item_response)
    -- prove it still returns full review context, including the new
    row_id/resumable fields.
    """
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed_project_and_document(db, tenant)
    item_id = uuid4()

    response = await authenticated_client.post(
        "/api/v1/hitl/route",
        json={
            "item_id": str(item_id),
            "item_type": "coherence_alert",
            "confidence": 0.4,
            "impact_level": "HIGH",
            "item_data": {"document_id": str(document.id)},
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["item_id"] == str(item_id)
    assert body["current_status"] == "PENDING_REVIEW_REQUIRED"
    assert body["resumable"] is False
    assert body["row_id"] is not None


async def test_approve_nonexistent_review_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post(
        f"/api/v1/hitl/queue/{uuid4()}/approve", json={}
    )
    assert response.status_code == 404


async def test_approve_non_resumable_review_does_not_invoke_resume(
    authenticated_client: AsyncClient,
    app,
    db: AsyncSession,
    test_user: User,
) -> None:
    """A review with no thread_id must take the plain status-flip path and
    never touch ResumeWorkflowUseCase at all -- proves the else branch, and
    that graph-resume machinery isn't invoked for reviews that have no
    workflow to resume.
    """
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed_project_and_document(db, tenant)
    review = _make_review_row(
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
            raise AssertionError("ResumeWorkflowUseCase must not be invoked for a non-resumable review")

    app.dependency_overrides[get_resume_workflow_use_case] = lambda: _ExplodingUseCase()

    response = await authenticated_client.post(
        f"/api/v1/hitl/queue/{review.item_id}/approve", json={}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["current_status"] == "APPROVED"
    assert body["resumable"] is False


async def test_reject_graph_gated_review_terminates_without_running_n17(
    authenticated_client: AsyncClient,
    app,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Objective D.5: rejecting a graph-gated review must be durable and
    truthful, and must NEVER run N17 / persist an analysis / mark the
    document ANALYZED -- rejection terminates the workflow, it does not
    complete it.
    """
    from src.analysis.adapters.persistence.models import Analysis

    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed_project_and_document(db, tenant)
    thread_id = f"document:{document.id}:analysis"

    review = _make_review_row(
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
        "messages": [],
        "node_results": [],
    }

    class _RejectOnlyGraphApp:
        """C2PRO P0b true-resume hotfix: a rejection now DOES resume the
        graph -- with Command(resume={"decision": "reject"}) -- so the real
        workflow terminates at its own conditional edge instead of merely
        having a "terminated" flag patched into stored state. What must
        still never happen is N17: this double therefore records the
        decision it was resumed with and refuses to run save_to_db.
        """

        def __init__(self) -> None:
            self.update_calls: list[dict] = []
            self.invoked = False
            self.resumed_decisions: list[str | None] = []
            self.resumed_state: dict = {}

        async def aupdate_state(self, config: dict, state: dict) -> None:
            self.update_calls.append(dict(state))

        async def ainvoke(self, resume_signal: object, config: dict) -> dict:
            from tests.support.hitl_resume_fakes import decision_from_resume

            self.invoked = True
            decision, feedback = decision_from_resume(resume_signal)
            self.resumed_decisions.append(decision)
            assert decision == "reject", (
                f"a reject request must resume with a reject decision, got {decision!r}"
            )
            resumed = {
                **resume_state,
                "human_decision": "reject",
                "human_approval_required": False,
                "workflow_terminated": True,
                "termination_reason": feedback,
            }
            self.resumed_state = resumed
            return resumed

    checkpoint_service = _FakeResumeCheckpointService(resume_state)
    reject_graph_app = _RejectOnlyGraphApp()

    def _use_case() -> ResumeWorkflowUseCase:
        repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant.id)
        return ResumeWorkflowUseCase(
            review_queue_repo=repo,
            checkpoint_service=checkpoint_service,
            graph_app=reject_graph_app,
        )

    app.dependency_overrides[get_resume_workflow_use_case] = _use_case

    response = await authenticated_client.post(
        f"/api/v1/hitl/queue/{review.item_id}/reject",
        json={"reason": "Clause is ambiguous, needs correction."},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["current_status"] == "REJECTED"
    # C2PRO P0b true-resume hotfix: the invariant is "reject must not run
    # N17", not "reject must not call ainvoke". A rejection now resumes the
    # real workflow so it terminates at the graph's own conditional edge --
    # carrying an explicit reject decision, asserted inside the double.
    assert reject_graph_app.resumed_decisions == ["reject"], (
        "reject must resume the graph with an explicit reject decision"
    )
    reject_resumed_state = reject_graph_app.resumed_state
    # Termination is now carried by the resumed run itself (the graph's own
    # conditional edge to END), not by a separate aupdate_state patch, so
    # assert the resumed result rather than a state-injection side channel.
    assert reject_resumed_state["workflow_terminated"] is True

    # No analysis persisted, document not ANALYZED -- rejection never
    # completes the pipeline.
    analyses = (
        await db.execute(select(Analysis).where(Analysis.project_id == document.project_id))
    ).scalars().all()
    assert len(analyses) == 0

    refreshed_document = await db.get(DocumentORM, document.id)
    await db.refresh(refreshed_document)
    assert refreshed_document.upload_status == "parsed_pending_analysis"

    refreshed_review = await db.get(ReviewItemORM, review.id)
    await db.refresh(refreshed_review)
    assert refreshed_review.approved_by == test_user.full_name
    assert refreshed_review.review_metadata.get("rejection_reason") == "Clause is ambiguous, needs correction."


async def test_reject_nonexistent_review_returns_404(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post(
        f"/api/v1/hitl/queue/{uuid4()}/reject", json={"reason": "n/a"}
    )
    assert response.status_code == 404


async def test_reject_non_resumable_review_does_not_invoke_resume(
    authenticated_client: AsyncClient,
    app,
    db: AsyncSession,
    test_user: User,
) -> None:
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed_project_and_document(db, tenant)
    review = _make_review_row(
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
            raise AssertionError("ResumeWorkflowUseCase must not be invoked for a non-resumable review")

    app.dependency_overrides[get_resume_workflow_use_case] = lambda: _ExplodingUseCase()

    response = await authenticated_client.post(
        f"/api/v1/hitl/queue/{review.item_id}/reject", json={"reason": "bad extraction"}
    )

    assert response.status_code == 200, response.text
    assert response.json()["current_status"] == "REJECTED"


async def test_reject_already_processed_graph_gated_review_returns_400_not_502(
    authenticated_client: AsyncClient,
    app,
    db: AsyncSession,
    test_user: User,
) -> None:
    """A resume-side ValueError that is NOT the "_with_errors" workflow
    failure (e.g. the review is in a genuinely invalid status for a
    decision) must surface as 400, not 502 -- 502 is reserved for a resume
    that was attempted and failed, not for a request that never should
    have been attempted.
    """
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed_project_and_document(db, tenant)
    review = _make_review_row(
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

    checkpoint_service = _FakeResumeCheckpointService({})

    def _use_case() -> ResumeWorkflowUseCase:
        repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant.id)
        return ResumeWorkflowUseCase(
            review_queue_repo=repo,
            checkpoint_service=checkpoint_service,
            graph_app=_FakeResumingGraphApp(),
        )

    app.dependency_overrides[get_resume_workflow_use_case] = _use_case

    response = await authenticated_client.post(
        f"/api/v1/hitl/queue/{review.item_id}/reject", json={"reason": "n/a"}
    )
    assert response.status_code == 400, response.text


async def test_approve_and_resume_workflow_maps_not_found_to_404() -> None:
    """Direct unit coverage for _approve_and_resume_workflow's ValueError
    branches: a "not found" message maps to 404.
    """
    from src.modules.hitl.adapters.http.router import _approve_and_resume_workflow

    class _NotFoundUseCase:
        async def execute(self, *args, **kwargs):
            raise ValueError("Review item deadbeef-0000-0000-0000-000000000000 not found")

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await _approve_and_resume_workflow(
            item_id=uuid4(),
            reviewer_name="Reviewer",
            resume_use_case=_NotFoundUseCase(),
        )
    assert exc_info.value.status_code == 404


async def test_approve_and_resume_workflow_maps_other_value_error_to_400() -> None:
    """Direct unit coverage: any other ValueError (e.g. not-pending) maps
    to 400, not 404 or 502.
    """
    from fastapi import HTTPException

    from src.modules.hitl.adapters.http.router import _approve_and_resume_workflow

    class _NotPendingUseCase:
        async def execute(self, *args, **kwargs):
            raise ValueError("Review item ... is not in pending status (current: CLOSED)")

    with pytest.raises(HTTPException) as exc_info:
        await _approve_and_resume_workflow(
            item_id=uuid4(),
            reviewer_name="Reviewer",
            resume_use_case=_NotPendingUseCase(),
        )
    assert exc_info.value.status_code == 400


async def test_approve_non_resumable_already_approved_review_returns_400(
    authenticated_client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """The plain (non-resumable) approve_item() path's own ValueError ->
    400 mapping, for a review with no thread_id that is not in a pending
    status (e.g. already approved).
    """
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed_project_and_document(db, tenant)
    review = _make_review_row(
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

    response = await authenticated_client.post(
        f"/api/v1/hitl/queue/{review.item_id}/approve", json={}
    )
    assert response.status_code == 400, response.text
