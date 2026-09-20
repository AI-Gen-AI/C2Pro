"""
C2PRO P0b PROD LEGACY REVIEW CANONICAL-SELECTION HOTFIX.

Authoritative production evidence (project 2b7f3509-4b0f-4cc3-90f4-9f55c1964392,
document/item_id 369cdc8f-50ed-4a15-9fe1-5167e4eb4862): the review queue's
"All" filter showed Pending=0, Approved=1, rendering only a historical
APPROVED row -- while a genuinely active PENDING_REVIEW_REQUIRED row (with
its own real thread_id/checkpoint_id) for the SAME item_id existed and was
invisible.

Root cause: SqlAlchemyReviewQueueRepository._canonical_rows_subquery()
collapsed duplicate rows sharing one item_id by ordering purely on
``thread_id IS NOT NULL DESC, created_at DESC`` -- current_status never
factored into the tie-break. When both an old APPROVED row and the current
active PENDING row carry a thread_id, whichever was created more recently
(in this production shape, the historical APPROVED audit row) silently won,
regardless of lifecycle stage. get_review_item()'s item_id fallback was
worse still: it ordered by created_at alone, ignoring thread_id AND status
entirely -- meaning the very card the UI wasn't even showing could still be
the one approve/reject resolved and mutated, producing exactly the failure
this hotfix exists to prevent: "UI shows pending row B -> POST item_id ->
backend resolves and mutates historical row A".

Fixed by SqlAlchemyReviewQueueRepository._canonical_priority(): an active
row (PENDING_REVIEW_REQUIRED/PENDING_REVIEW_CONDITIONAL) now always
outranks a historical, already-decided row (APPROVED/REJECTED/CLOSED/
ESCALATED) for the same item_id, before thread_id/created_at tie-breaking
-- applied identically to the queue list (_canonical_rows_subquery),
single-item lookup (get_review_item's item_id fallback), and mutation
targeting (update_review_item's item_id fallback), so all three can never
disagree about which row is "the" canonical one.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import Analysis
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
    def __init__(self) -> None:
        self.last_state: dict | None = None

    async def aupdate_state(self, config: dict, state: dict) -> None:
        self.last_state = state

    async def ainvoke(self, _resume_signal: None, config: dict) -> dict:
        from src.analysis.adapters.graph.nodes import save_to_db_node

        assert self.last_state is not None
        return await save_to_db_node(self.last_state)


class _FakeResumeCheckpointService:
    def __init__(self, state: dict) -> None:
        self._state = state
        self.loaded: list[tuple[str, str | None]] = []

    async def load_checkpoint(self, thread_id: str, checkpoint_id: str | None) -> dict:
        self.loaded.append((thread_id, checkpoint_id))
        return {"id": checkpoint_id or "latest", "channel_values": {"__root__": dict(self._state)}}

    def extract_state(self, checkpoint: dict) -> dict:
        return dict(checkpoint["channel_values"]["__root__"])


def _override_resume_use_case(app, db: AsyncSession, tenant_id: UUID, resume_state: dict):
    resuming_app = _FakeResumingGraphApp()
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


async def _seed_project_and_document(db: AsyncSession, tenant: Tenant) -> DocumentORM:
    project_id, document_id = uuid4(), uuid4()
    db.add(
        ProjectORM(
            id=project_id,
            tenant_id=tenant.id,
            name="Legacy Canonical Selection Hotfix Project",
            code="P0B-CANON",
            start_date=datetime.now(),
        )
    )
    await db.commit()
    document = DocumentORM(
        id=document_id,
        tenant_id=tenant.id,
        project_id=project_id,
        document_type="contract",
        filename="legacy_canonical.pdf",
        upload_status="parsed_pending_analysis",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


def _row(
    *,
    tenant_id: UUID,
    project_id: UUID,
    document_id: UUID,
    status: ReviewStatus,
    thread_id: str | None,
    checkpoint_id: str | None,
    created_at: datetime,
    approved_at: datetime | None = None,
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
        created_at=created_at,
        approved_by="Prior Reviewer" if approved_at else None,
        approved_at=approved_at,
    )


async def _seed_prod_shape(
    db: AsyncSession, tenant: Tenant
) -> tuple[DocumentORM, ReviewItemORM, ReviewItemORM, ReviewItemORM, ReviewItemORM]:
    """Objective D's exact production shape: one item_id, four rows.

    A: APPROVED + thread/checkpoint, created LATEST (the historical row
       that was wrongly winning canonical selection).
    B: PENDING_REVIEW_REQUIRED + thread/checkpoint, created slightly
       earlier than A (the actual active, actionable row).
    C, D: PENDING_REVIEW_REQUIRED, no thread/checkpoint (oldest legacy
       duplicates, pre-hotfix retries).
    """
    document = await _seed_project_and_document(db, tenant)
    thread_id = f"document:{document.id}:analysis"
    now = datetime.now(UTC).replace(tzinfo=None)

    row_d = _row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        thread_id=None,
        checkpoint_id=None,
        created_at=now - timedelta(hours=3),
    )
    row_c = _row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        thread_id=None,
        checkpoint_id=None,
        created_at=now - timedelta(hours=2),
    )
    row_b = _row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        thread_id=thread_id,
        checkpoint_id="1f1b533f-ed72-602d-8013-839c8b8e26c9",
        created_at=now - timedelta(minutes=14),
    )
    row_a = _row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        status=ReviewStatus.APPROVED,
        thread_id=thread_id,
        checkpoint_id="1f1b4d1e-5c6e-6c06-800c-6d08ba742545",
        created_at=now,
        approved_at=now,
    )
    db.add_all([row_a, row_b, row_c, row_d])
    await db.commit()
    for row in (row_a, row_b, row_c, row_d):
        await db.refresh(row)
    return document, row_a, row_b, row_c, row_d


# -- Objectives A/B: canonical selection across filters ----------------------


async def test_all_filter_returns_active_pending_not_historical_approved(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    _document, row_a, row_b, _row_c, _row_d = await _seed_prod_shape(db, tenant)

    repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant.id)
    items = await repo.list_by_status(status=None, skip=0, limit=50)
    matching = [i for i in items if i.item_id == row_b.item_id]

    assert len(matching) == 1, "exactly one logical review must render for this item_id"
    assert matching[0].metadata["row_id"] == str(row_b.id), (
        "the ALL filter must surface the active PENDING row, not the "
        f"historical APPROVED row {row_a.id}"
    )
    assert matching[0].current_status == ReviewStatus.PENDING_REVIEW_REQUIRED


async def test_pending_filter_returns_same_row_as_all_filter(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    _document, _row_a, row_b, _row_c, _row_d = await _seed_prod_shape(db, tenant)

    repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant.id)
    items = await repo.list_by_status(status=ReviewStatus.PENDING_REVIEW_REQUIRED, skip=0, limit=50)
    matching = [i for i in items if i.item_id == row_b.item_id]

    assert len(matching) == 1
    assert matching[0].metadata["row_id"] == str(row_b.id)


async def test_approved_filter_returns_historical_approved_row(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    _document, row_a, _row_b, _row_c, _row_d = await _seed_prod_shape(db, tenant)

    repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant.id)
    items = await repo.list_by_status(status=ReviewStatus.APPROVED, skip=0, limit=50)
    matching = [i for i in items if i.item_id == row_a.item_id]

    assert len(matching) == 1, (
        "explicitly filtering Approved must still surface the historical "
        "approved row -- the ALL-filter fix must not suppress it there"
    )
    assert matching[0].metadata["row_id"] == str(row_a.id)


async def test_counts_stay_consistent_with_rendered_canonical_rows(db: AsyncSession) -> None:
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    await _seed_prod_shape(db, tenant)

    repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant.id)
    all_items = await repo.list_by_status(status=None, skip=0, limit=50)
    all_count = await repo.count_by_status(status=None)
    pending_items = await repo.list_by_status(status=ReviewStatus.PENDING_REVIEW_REQUIRED, skip=0, limit=50)
    pending_count = await repo.count_by_status(status=ReviewStatus.PENDING_REVIEW_REQUIRED)

    assert all_count == len(all_items)
    assert pending_count == len(pending_items)
    # One canonical logical review for this item_id, and it is PENDING --
    # so it must appear in the pending count/list exactly as in "all".
    assert pending_count == all_count


# -- Objective C: action target consistency -----------------------------------


async def test_get_review_item_by_item_id_resolves_active_pending_row(db: AsyncSession) -> None:
    """The exact same row the queue list surfaces for this item_id must be
    the row get_review_item(item_id) resolves -- otherwise a caller that
    fetches by item_id (as approve/reject's non-row_id-aware callers do)
    can silently act on a different row than the one rendered.
    """
    tenant = Tenant(
        id=uuid4(), name="T", slug=f"t-{uuid4().hex[:8]}", subscription_plan="professional", is_active=True
    )
    db.add(tenant)
    await db.commit()
    _document, _row_a, row_b, _row_c, _row_d = await _seed_prod_shape(db, tenant)

    repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant.id)
    resolved = await repo.get_review_item(row_b.item_id)

    assert resolved is not None
    assert resolved.metadata["row_id"] == str(row_b.id)
    assert resolved.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED


async def test_approve_via_route_targets_active_pending_row_resumes_and_leaves_approved_row_untouched(
    authenticated_client: AsyncClient,
    app,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Objective C + D: approve via the real production route, addressed
    by item_id (the URL contract the frontend actually uses), must resolve
    to row B -- resume its SAME thread/checkpoint, run the real N17,
    persist an analysis, mark the document ANALYZED -- and leave the
    historical row A completely untouched. Rows C/D (never adopted) must
    also remain untouched, and no fifth row may be created.
    """
    tenant = await db.get(Tenant, test_user.tenant_id)
    document, row_a, row_b, row_c, row_d = await _seed_prod_shape(db, tenant)
    original_a_approved_at = row_a.approved_at

    resume_state = {
        "project_id": str(document.project_id),
        "tenant_id": str(tenant.id),
        "document_id": str(document.id),
        "extracted_risks": [],
        "extracted_wbs": [],
        "coherence_score": 88,
        "coherence_breakdown": {"overall": 88},
        "single_document_assessment": {
            "single_document_assessment": {
                "evidence_granularity": "document",
                "proof_marker": "p0b-legacy-canonical-selection-health-readable",
            }
        },
        "messages": [],
        "node_results": [],
    }
    resuming_app, checkpoint_service = _override_resume_use_case(app, db, tenant.id, resume_state)

    response = await authenticated_client.post(
        f"/api/v1/hitl/queue/{row_b.item_id}/approve",
        json={},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["row_id"] == str(row_b.id), "approve must have resolved row B, not row A"
    assert body["current_status"] == "APPROVED"
    assert checkpoint_service.loaded == [(row_b.thread_id, row_b.checkpoint_id)], (
        "resume must use row B's own thread_id/checkpoint_id, never row A's"
    )

    analyses = (
        await db.execute(select(Analysis).where(Analysis.project_id == document.project_id))
    ).scalars().all()
    assert len(analyses) == 1, "N17 must have run for real exactly once"
    assert (
        analyses[0].result_json.get("single_document_assessment", {}).get("proof_marker")
        == "p0b-legacy-canonical-selection-health-readable"
    )

    refreshed_document = await db.get(DocumentORM, document.id)
    await db.refresh(refreshed_document)
    assert refreshed_document.upload_status == "analyzed"

    refreshed_b = await db.get(ReviewItemORM, row_b.id)
    await db.refresh(refreshed_b)
    assert refreshed_b.current_status == ReviewStatus.APPROVED.value

    refreshed_a = await db.get(ReviewItemORM, row_a.id)
    await db.refresh(refreshed_a)
    assert refreshed_a.current_status == ReviewStatus.APPROVED.value
    assert refreshed_a.approved_at == original_a_approved_at, "row A must not have been re-mutated"

    refreshed_c = await db.get(ReviewItemORM, row_c.id)
    refreshed_d = await db.get(ReviewItemORM, row_d.id)
    await db.refresh(refreshed_c)
    await db.refresh(refreshed_d)
    assert refreshed_c.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED.value
    assert refreshed_d.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED.value

    all_rows = (
        await db.execute(select(ReviewItemORM).where(ReviewItemORM.document_id == document.id))
    ).scalars().all()
    assert len(all_rows) == 4, "approve must never create a fifth row"


# -- Objective E: tenant isolation --------------------------------------------


async def test_cross_tenant_row_id_and_item_id_cannot_mutate_another_tenant_review(
    authenticated_client: AsyncClient,
    db: AsyncSession,
    test_user: User,
    test_tenant_2: Tenant,
) -> None:
    _document, row_a, row_b, _row_c, _row_d = await _seed_prod_shape(db, test_tenant_2)

    for target_id in (row_b.item_id, row_b.id, row_a.item_id, row_a.id):
        get_response = await authenticated_client.get(f"/api/v1/hitl/queue/{target_id}")
        assert get_response.status_code == 404

        approve_response = await authenticated_client.post(
            f"/api/v1/hitl/queue/{target_id}/approve", json={}
        )
        assert approve_response.status_code == 404

    refreshed_b = await db.get(ReviewItemORM, row_b.id)
    await db.refresh(refreshed_b)
    assert refreshed_b.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED.value

    refreshed_a = await db.get(ReviewItemORM, row_a.id)
    await db.refresh(refreshed_a)
    assert refreshed_a.current_status == ReviewStatus.APPROVED.value
