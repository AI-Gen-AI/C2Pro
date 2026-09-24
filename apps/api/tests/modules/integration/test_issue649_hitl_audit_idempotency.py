"""
C2PRO ISSUE #649 -- POST-#646 HITL AUDIT IDEMPOTENCY + APPROVED CANONICAL ROW.

Production evidence after the #646 rollout: one effective human approval,
three successful ``POST /hitl/queue/{item_id}/approve`` responses, and three
``hitl.correction`` project events. The V3 core (one operation, one analysis,
one ``analysis.persisted``, one ``graph.completed``) was idempotent; the
temporal audit layer was not: the router appended a fresh ``hitl.correction``
after EVERY 2xx, including idempotent replays, with no durable key.

Required invariant proven here:

    ONE EFFECTIVE FINAL HUMAN DECISION -> ONE durable hitl.correction

for sequential repeats (double click after completion), concurrent identical
requests on independent database connections, and a lost-response retry --
while a genuinely different final decision (a NEW review row, hence a NEW
resume operation) remains auditable.

Second defect: once the active row B was finalized, it tied on status with a
historical APPROVED row A sharing its item_id, and the created_at tiebreak
surfaced A ("Reviewed: Sep 20" instead of the Sep 24 decision). The
canonical read model must prefer the row the durable V3 finalization
references, keep PENDING priority, and stay deterministic for legacy-only
data.

Everything runs against REAL PostgreSQL, a REAL AsyncPostgresSaver and the
REAL production graph nodes (reused from the #646 crash-safe suite).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.analysis.adapters.persistence.models import Analysis
from src.core.auth.models import Tenant, User
from src.modules.hitl.adapters.checkpoint_service import CheckpointService
from src.modules.hitl.adapters.http import router as hitl_router
from src.modules.hitl.adapters.http.schemas import ApproveRequest, RejectRequest
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.adapters.persistence.repository import (
    SqlAlchemyReviewQueueRepository,
)
from src.modules.hitl.application.resume_workflow_use_case import (
    ResumeWorkflowRequest,
    ResumeWorkflowUseCase,
    WorkflowDecision,
)
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus
from src.temporal.adapters.persistence.models import ProjectEventORM
from src.temporal.application import project_snapshot_trigger
from tests.modules.integration.test_p0b_crash_safe_resume_recovery import (
    N17_RUNS,
    _arrange,
    _dsn,
    _initial_state,
    _reload,
    independent_sessions,  # noqa: F401 - pytest fixture
    real_saver,  # noqa: F401 - pytest fixture
)

pytestmark = pytest.mark.asyncio

HITL_CORRECTION = "hitl.correction"


# ── harness ──────────────────────────────────────────────────────────────────


@pytest.fixture
def snapshot_enqueues(monkeypatch) -> list[dict[str, Any]]:
    """Every snapshot enqueue, from ANY emitter (router or use case).

    Celery is not running; counting enqueues is how "no duplicate snapshot
    for a deduplicated event" is proven.
    """
    calls: list[dict[str, Any]] = []

    def _record(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(project_snapshot_trigger, "enqueue_project_snapshot", _record)
    return calls


@pytest.fixture
async def request_sessions(db):
    """One genuinely independent session per simulated HTTP request."""
    engine = create_async_engine(_dsn(db), pool_size=10, max_overflow=10)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield maker
    finally:
        await engine.dispose()


def _reviewer() -> Any:
    return SimpleNamespace(id=uuid4(), full_name="Reviewer")


async def _post_approve(
    maker: Any, tenant_id: UUID, item_id: UUID, *, saver: Any, app: Any, sessions: Any
) -> Any:
    """One ``POST /queue/{item_id}/approve`` on its OWN connection/transaction.

    Drives the production route handler exactly as FastAPI would, but with a
    request-scoped session per call, so concurrent calls are arbitrated by
    PostgreSQL across connections the way API workers are.
    """
    async with maker() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": str(tenant_id)},
        )
        repo = SqlAlchemyReviewQueueRepository(session=session, tenant_id=tenant_id)
        use_case = ResumeWorkflowUseCase(
            review_queue_repo=repo,
            checkpoint_service=CheckpointService(checkpointer=saver),
            graph_app=app,
            claim_session_factory=sessions,
        )
        try:
            return await hitl_router.approve_item(
                item_id=item_id,
                _payload=ApproveRequest(),
                _tenant_id=tenant_id,
                current_user=_reviewer(),
                service=SimpleNamespace(review_queue_repo=repo),
                resume_use_case=use_case,
            )
        finally:
            await session.commit()


async def _post_reject(
    maker: Any,
    tenant_id: UUID,
    item_id: UUID,
    *,
    saver: Any,
    app: Any,
    sessions: Any,
    reason: str = "wrong clause extraction",
    reviewer_name: str = "Reviewer",
) -> Any:
    async with maker() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": str(tenant_id)},
        )
        repo = SqlAlchemyReviewQueueRepository(session=session, tenant_id=tenant_id)
        use_case = ResumeWorkflowUseCase(
            review_queue_repo=repo,
            checkpoint_service=CheckpointService(checkpointer=saver),
            graph_app=app,
            claim_session_factory=sessions,
        )
        try:
            return await hitl_router.reject_item(
                item_id=item_id,
                payload=RejectRequest(reason=reason),
                _tenant_id=tenant_id,
                current_user=SimpleNamespace(id=uuid4(), full_name=reviewer_name),
                service=SimpleNamespace(review_queue_repo=repo),
                resume_use_case=use_case,
            )
        finally:
            await session.commit()


async def _events(db: AsyncSession, project_id: UUID, event_type: str) -> list[ProjectEventORM]:
    return list(
        (
            await db.execute(
                select(ProjectEventORM)
                .where(
                    ProjectEventORM.project_id == project_id,
                    ProjectEventORM.event_type == event_type,
                )
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .all()
    )


async def _operation_count(sessions: Any, tenant_id: UUID, project_id: UUID) -> int:
    async with sessions(tenant_id) as s:
        return int(
            (
                await s.execute(
                    text(
                        "SELECT count(*) FROM resume_operations "
                        " WHERE project_id = cast(:p as uuid)"
                    ),
                    {"p": str(project_id)},
                )
            ).scalar_one()
        )


async def _assert_core_invariants(
    db: AsyncSession, sessions: Any, tenant_id: UUID, arranged: Any
) -> None:
    """The #646 guarantees that must not move."""
    analyses = (
        (await db.execute(select(Analysis).where(Analysis.project_id == arranged.project_id)))
        .scalars()
        .all()
    )
    assert len(analyses) == 1, "ONE analysis"
    assert await _operation_count(sessions, tenant_id, arranged.project_id) == 1, (
        "ONE resume operation"
    )
    assert len(await _events(db, arranged.project_id, "analysis.persisted")) == 1
    assert len(await _events(db, arranged.project_id, "graph.completed")) == 1
    assert len(N17_RUNS) == 1, f"exactly one N17 execution, got {N17_RUNS}"
    rows = (
        (
            await db.execute(
                select(ReviewItemORM).where(ReviewItemORM.document_id == arranged.document_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, "no fifth review row"


def _assert_correction_is_v3_keyed(event: ProjectEventORM, arranged: Any, decision: str) -> None:
    assert event.resume_operation_id is not None, (
        "hitl.correction must be keyed to durable V3 provenance, not request arrival"
    )
    assert event.payload["decision"] == decision
    assert event.payload["review_item_id"] == str(arranged.review_item_id)
    assert event.payload["review_row_id"] == str(arranged.review_row_id)
    assert event.payload["resume_operation_id"] == str(event.resume_operation_id)


# ── BACKEND TEST A: sequential repeated approve ──────────────────────────────


async def test_a_sequential_repeated_approve_records_one_correction(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,
    snapshot_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    N17_RUNS.clear()

    responses = []
    for _ in range(3):  # Confirm clicked three times, one after another.
        responses.append(
            await _post_approve(
                request_sessions,
                tenant.id,
                arranged.review_item_id,
                saver=saver,
                app=arranged.app,
                sessions=independent_sessions,
            )
        )

    for response in responses:
        assert response.current_status == ReviewStatus.APPROVED
        assert response.row_id == arranged.review_row_id

    await _assert_core_invariants(db, independent_sessions, tenant.id, arranged)
    corrections = await _events(db, arranged.project_id, HITL_CORRECTION)
    assert len(corrections) == 1, (
        f"one effective human decision must produce ONE hitl.correction, got {len(corrections)}"
    )
    _assert_correction_is_v3_keyed(corrections[0], arranged, ReviewStatus.APPROVED.value)
    hitl_snapshots = [c for c in snapshot_enqueues if c["trigger"].value == "hitl_correction"]
    assert [c["source_event_id"] for c in hitl_snapshots] == [corrections[0].event_id], (
        "exactly one snapshot, for the one durable correction event"
    )


# ── BACKEND TEST B: concurrent identical approve on independent sessions ─────


async def test_b_concurrent_identical_approve_records_one_correction(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,
    snapshot_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    N17_RUNS.clear()

    def burst() -> Any:
        return asyncio.gather(
            *[
                _post_approve(
                    request_sessions,
                    tenant.id,
                    arranged.review_item_id,
                    saver=saver,
                    app=arranged.app,
                    sessions=independent_sessions,
                )
                for _ in range(3)
            ],
            return_exceptions=True,
        )

    # Wave 1: every request may observe PENDING before anyone commits.
    first_wave = await burst()
    # Wave 2: a double-click burst arriving after the decision committed --
    # every request observes APPROVED concurrently.
    second_wave = await burst()

    winners = [r for r in first_wave if not isinstance(r, BaseException)]
    losers = [r for r in first_wave if isinstance(r, BaseException)]
    assert winners, f"one request must win: {first_wave}"
    for loser in losers:
        assert isinstance(loser, HTTPException) and loser.status_code == 400, loser
    for replay in second_wave:
        assert not isinstance(replay, BaseException), replay
        assert replay.current_status == ReviewStatus.APPROVED
        assert replay.row_id == arranged.review_row_id

    await _assert_core_invariants(db, independent_sessions, tenant.id, arranged)
    corrections = await _events(db, arranged.project_id, HITL_CORRECTION)
    assert len(corrections) == 1, (
        f"concurrent identical approvals must produce ONE hitl.correction, got {len(corrections)}"
    )
    _assert_correction_is_v3_keyed(corrections[0], arranged, ReviewStatus.APPROVED.value)
    hitl_snapshots = [c for c in snapshot_enqueues if c["trigger"].value == "hitl_correction"]
    assert len(hitl_snapshots) == 1


# ── BACKEND TEST C: lost response / idempotent replay after FINALIZED ────────


async def test_c_lost_response_replay_after_finalized_adds_no_correction(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,
    snapshot_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    """The process finalizes, then dies before ANY post-decision router code.

    The durable decision exists; the response never reached the browser. The
    client retries. The retry must be an idempotent 200 for the same row, and
    the audit trail must still hold exactly one correction for the decision
    -- not zero (the decision really happened) and not two (the retry is not
    a new decision).
    """
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    N17_RUNS.clear()

    # The first request: everything the route does up to and including the
    # durable finalization -- then the process is lost, so NOTHING after
    # the use case (no router post-processing, no response) ever runs.
    async with request_sessions() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": str(tenant.id)},
        )
        first = await ResumeWorkflowUseCase(
            review_queue_repo=SqlAlchemyReviewQueueRepository(session=session, tenant_id=tenant.id),
            checkpoint_service=CheckpointService(checkpointer=saver),
            graph_app=arranged.app,
            claim_session_factory=independent_sessions,
        ).execute(
            review_id=arranged.review_item_id,
            request=ResumeWorkflowRequest(
                decision=WorkflowDecision.APPROVE, feedback="", approved_by="Reviewer"
            ),
        )
        await session.commit()
    assert first.status == "resumed"

    async with independent_sessions(tenant.id) as s:
        op_phase = (
            await s.execute(
                text("SELECT phase FROM resume_operations WHERE review_row_id = cast(:r as uuid)"),
                {"r": str(arranged.review_row_id)},
            )
        ).scalar_one()
    assert op_phase == "FINALIZED_APPROVED"

    for _ in range(2):  # the browser's retry, then an impatient second one
        replay = await _post_approve(
            request_sessions,
            tenant.id,
            arranged.review_item_id,
            saver=saver,
            app=arranged.app,
            sessions=independent_sessions,
        )
        assert replay.current_status == ReviewStatus.APPROVED
        assert replay.row_id == arranged.review_row_id

    await _assert_core_invariants(db, independent_sessions, tenant.id, arranged)
    corrections = await _events(db, arranged.project_id, HITL_CORRECTION)
    assert len(corrections) == 1, (
        f"a lost-response retry must not add a correction; got {len(corrections)}"
    )
    _assert_correction_is_v3_keyed(corrections[0], arranged, ReviewStatus.APPROVED.value)


# ── reject is the same final-decision contract ───────────────────────────────


async def test_repeated_reject_records_one_rejected_correction(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,
    snapshot_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    N17_RUNS.clear()

    for _ in range(2):
        response = await _post_reject(
            request_sessions,
            tenant.id,
            arranged.review_item_id,
            saver=saver,
            app=arranged.app,
            sessions=independent_sessions,
        )
        assert response.current_status == ReviewStatus.REJECTED

    assert N17_RUNS == [], "a rejection never runs N17"
    corrections = await _events(db, arranged.project_id, HITL_CORRECTION)
    assert len(corrections) == 1, f"got {len(corrections)} corrections for one rejection"
    _assert_correction_is_v3_keyed(corrections[0], arranged, ReviewStatus.REJECTED.value)


# ── a genuinely new final decision stays auditable ───────────────────────────


async def _rerun_to_new_review(
    db: AsyncSession, tenant: Tenant, saver: Any, arranged: Any, register: Any
) -> ReviewItemORM:
    """Re-analyse the same document on a NEW thread -> a NEW review row.

    The previous review is finalized, so the idempotency guard finds no
    active review and the interrupt node creates a new one for the same
    business item_id -- the legitimate way a second, different final human
    decision about this document comes to exist.
    """
    thread_id = f"document:{arranged.document_id}:analysis:rerun:{uuid4().hex[:8]}"
    register(thread_id)
    cfg = {"configurable": {"thread_id": thread_id}}
    document = SimpleNamespace(project_id=arranged.project_id, id=arranged.document_id)
    result = await arranged.app.ainvoke(_initial_state(document, tenant, thread_id), cfg)
    assert "__interrupt__" in result
    checkpoint_id = (await arranged.app.aget_state(cfg)).config["configurable"]["checkpoint_id"]
    new_row = (
        (
            await db.execute(
                select(ReviewItemORM)
                .where(
                    ReviewItemORM.document_id == arranged.document_id,
                    ReviewItemORM.id != arranged.review_row_id,
                )
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .one()
    )
    new_row.thread_id, new_row.checkpoint_id = thread_id, checkpoint_id
    new_row.review_metadata = {
        **(new_row.review_metadata or {}),
        "tenant_id": str(tenant.id),
        "document_id": str(arranged.document_id),
    }
    await db.commit()
    await db.refresh(new_row)
    return new_row


async def test_genuinely_new_final_decision_is_audited_separately(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,
    snapshot_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    N17_RUNS.clear()

    first = await _post_reject(
        request_sessions,
        tenant.id,
        arranged.review_item_id,
        saver=saver,
        app=arranged.app,
        sessions=independent_sessions,
    )
    assert first.current_status == ReviewStatus.REJECTED

    new_row = await _rerun_to_new_review(db, tenant, saver, arranged, register)
    new_row_id = new_row.id
    assert new_row.item_id == arranged.review_item_id

    for _ in range(2):  # the new decision, plus a double click on it
        second = await _post_approve(
            request_sessions,
            tenant.id,
            arranged.review_item_id,
            saver=saver,
            app=arranged.app,
            sessions=independent_sessions,
        )
        assert second.current_status == ReviewStatus.APPROVED
        assert second.row_id == new_row_id

    corrections = sorted(
        await _events(db, arranged.project_id, HITL_CORRECTION),
        key=lambda e: (e.occurred_at, str(e.event_id)),
    )
    assert [e.payload["decision"] for e in corrections] == [
        ReviewStatus.REJECTED.value,
        ReviewStatus.APPROVED.value,
    ], "each distinct final decision is audited exactly once"
    assert corrections[0].resume_operation_id != corrections[1].resume_operation_id
    assert corrections[1].payload["review_row_id"] == str(new_row_id)


# ── CANONICAL TEST A: legacy APPROVED A + V3-finalized APPROVED B -> B ───────


async def _add_legacy_row(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    item_id: UUID,
    project_id: UUID,
    document_id: UUID,
    status: ReviewStatus,
    created_at: datetime,
    approved_at: datetime | None,
    thread_id: str | None = "legacy-thread",
) -> UUID:
    row = ReviewItemORM(
        item_id=item_id,
        item_type="contract",
        current_status=status,
        confidence=0.4,
        impact_level=ImpactLevel.HIGH,
        tenant_id=tenant_id,
        sla_due_date=created_at + timedelta(days=3),
        approved_by="Historical Reviewer" if approved_at else None,
        approved_at=approved_at,
        item_data={"project_id": str(project_id), "document_id": str(document_id)},
        review_metadata={"tenant_id": str(tenant_id)},
        thread_id=thread_id,
        checkpoint_id="legacy-checkpoint" if thread_id else None,
        project_id=project_id,
        document_id=document_id,
        review_type="analysis_critique",
        created_at=created_at,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row.id


async def _canonical_views(
    db: AsyncSession, tenant_id: UUID, project_id: UUID, item_id: UUID
) -> dict[str, Any]:
    repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant_id)
    all_rows = await repo.list_by_status(project_id=project_id)
    approved_rows = await repo.list_by_status(status=ReviewStatus.APPROVED, project_id=project_id)
    single = await repo.get_review_item(item_id)
    return {
        "all": [r.metadata["row_id"] for r in all_rows if r.item_id == item_id],
        "approved": [r.metadata["row_id"] for r in approved_rows if r.item_id == item_id],
        "single": single.metadata["row_id"] if single else None,
        "single_approved_at": single.approved_at if single else None,
        "count_all": await repo.count_by_status(project_id=project_id),
        "count_approved": await repo.count_by_status(
            status=ReviewStatus.APPROVED, project_id=project_id
        ),
    }


async def test_canonical_a_v3_finalized_row_outranks_historical_approved_row(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,
    snapshot_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    """The exact production shape behind "Reviewed: Sep 20, 2026 at 09:08 AM".

    Historical row A: APPROVED on Sep 20, carries a thread_id, and was
    CREATED after the active row B. B was the pending row the user approved;
    V3 finalizes it. Pre-#649 the tie on status fell through to created_at
    and surfaced A.
    """
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    N17_RUNS.clear()

    sep_20 = datetime(2026, 9, 20, 9, 8)
    row_a_id = await _add_legacy_row(
        db,
        tenant_id=tenant.id,
        item_id=arranged.review_item_id,
        project_id=arranged.project_id,
        document_id=arranged.document_id,
        status=ReviewStatus.APPROVED,
        created_at=datetime.now() + timedelta(minutes=5),  # newer than B
        approved_at=sep_20,
    )

    before = await _canonical_views(db, tenant.id, arranged.project_id, arranged.review_item_id)
    assert before["all"] == [str(arranged.review_row_id)], "PENDING B outranks A before approval"

    response = await _post_approve(
        request_sessions,
        tenant.id,
        arranged.review_item_id,
        saver=saver,
        app=arranged.app,
        sessions=independent_sessions,
    )
    assert response.row_id == arranged.review_row_id

    after = await _canonical_views(db, tenant.id, arranged.project_id, arranged.review_item_id)
    b = str(arranged.review_row_id)
    assert after["all"] == [b], f"the V3-finalized row must be canonical, got {after}"
    assert after["approved"] == [b], f"APPROVED filter must show B, got {after}"
    assert after["single"] == b, "get_review_item(item_id) must agree with the queue"
    assert after["single_approved_at"] != sep_20, "must not show A's Sep 20 decision"
    assert after["count_all"] == 1 and after["count_approved"] == 1

    # History is preserved, untouched.
    row_a = await _reload(db, ReviewItemORM, row_a_id)
    assert row_a.current_status == ReviewStatus.APPROVED.value
    assert row_a.approved_at == sep_20


# ── CANONICAL TEST B / C: seeded lifecycle shapes ────────────────────────────


async def _seed_project(db: AsyncSession, tenant: Tenant) -> tuple[UUID, UUID]:
    from src.documents.adapters.persistence.models import DocumentORM
    from src.projects.adapters.persistence.models import ProjectORM

    project_id, document_id = uuid4(), uuid4()
    db.add(
        ProjectORM(
            id=project_id,
            tenant_id=tenant.id,
            name="Issue 649",
            code="I649",
            start_date=datetime.now(),
        )
    )
    await db.commit()
    db.add(
        DocumentORM(
            id=document_id,
            tenant_id=tenant.id,
            project_id=project_id,
            document_type="contract",
            filename="i649.pdf",
            upload_status="parsed_pending_analysis",
        )
    )
    await db.commit()
    return project_id, document_id


async def _finalized_operation(
    db: AsyncSession, *, tenant_id: UUID, row_id: UUID, phase: str
) -> None:
    """A durable V3 operation that finalized this EXACT row."""
    op_id = uuid4()
    await db.execute(
        text(
            "INSERT INTO resume_operations (id, tenant_id, review_row_id, fencing_token, "
            " decision_revision, decision, phase, failure_count, operation_metadata, "
            " created_at, updated_at) VALUES (cast(:id as uuid), cast(:t as uuid), "
            " cast(:r as uuid), 1, 1, 'approve', :phase, 0, '{}'::jsonb, "
            " clock_timestamp(), clock_timestamp())"
        ),
        {"id": str(op_id), "t": str(tenant_id), "r": str(row_id), "phase": phase},
    )
    await db.execute(
        text(
            "UPDATE review_items SET review_metadata = review_metadata || "
            " jsonb_build_object('resume_operation_id', cast(:op as text)) "
            " WHERE id = cast(:r as uuid)"
        ),
        {"op": str(op_id), "r": str(row_id)},
    )
    await db.commit()


async def test_canonical_b_pending_row_still_outranks_every_approved_row(
    db: AsyncSession, test_user: User
) -> None:
    tenant = await db.get(Tenant, test_user.tenant_id)
    project_id, document_id = await _seed_project(db, tenant)
    item_id = document_id
    base = datetime(2026, 9, 1, 8, 0)
    common = {
        "tenant_id": tenant.id,
        "item_id": item_id,
        "project_id": project_id,
        "document_id": document_id,
    }

    # The pending row is the OLDEST and has no thread -- every heuristic
    # below the lifecycle tier favours the others, so only the PENDING
    # priority can make it win.
    pending = await _add_legacy_row(
        db,
        status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        created_at=base,
        approved_at=None,
        thread_id=None,
        **common,
    )
    legacy = await _add_legacy_row(
        db,
        status=ReviewStatus.APPROVED,
        created_at=base + timedelta(days=3),
        approved_at=base + timedelta(days=3),
        **common,
    )
    v3 = await _add_legacy_row(
        db,
        status=ReviewStatus.APPROVED,
        created_at=base + timedelta(days=1),
        approved_at=base + timedelta(days=4),
        **common,
    )
    await _finalized_operation(db, tenant_id=tenant.id, row_id=v3, phase="FINALIZED_APPROVED")

    views = await _canonical_views(db, tenant.id, project_id, item_id)
    assert views["all"] == [str(pending)]
    assert views["single"] == str(pending)
    # An explicit APPROVED filter excludes the pending row; then the durable
    # V3 finalization wins over the historical row.
    assert views["approved"] == [str(v3)]

    repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant.id)
    active = await repo.find_active_review(document_id=document_id, review_type="analysis_critique")
    assert active is not None and active.metadata["row_id"] == str(pending)
    assert legacy  # preserved


async def test_canonical_b2_latest_v3_finalization_wins_and_non_final_ops_do_not_count(
    db: AsyncSession, test_user: User
) -> None:
    """Only a FINALIZED operation is effective-decision provenance.

    Two rows each finalized by V3 (a re-review): the later finalization is
    the effective one. A row whose operation never finalized (FAILED /
    OPERATOR_REQUIRED) is not.
    """
    tenant = await db.get(Tenant, test_user.tenant_id)
    project_id, document_id = await _seed_project(db, tenant)
    item_id = document_id
    base = datetime(2026, 9, 1, 8, 0)
    common = {
        "tenant_id": tenant.id,
        "item_id": item_id,
        "project_id": project_id,
        "document_id": document_id,
    }

    older_final = await _add_legacy_row(
        db,
        status=ReviewStatus.REJECTED,
        created_at=base + timedelta(days=5),
        approved_at=base + timedelta(days=6),
        **common,
    )
    newer_final = await _add_legacy_row(
        db,
        status=ReviewStatus.APPROVED,
        created_at=base + timedelta(days=1),
        approved_at=base + timedelta(days=8),
        **common,
    )
    not_final = await _add_legacy_row(
        db,
        status=ReviewStatus.APPROVED,
        created_at=base + timedelta(days=9),
        approved_at=base + timedelta(days=9),
        **common,
    )
    await _finalized_operation(
        db, tenant_id=tenant.id, row_id=older_final, phase="FINALIZED_REJECTED"
    )
    await _finalized_operation(
        db, tenant_id=tenant.id, row_id=newer_final, phase="FINALIZED_APPROVED"
    )
    await _finalized_operation(db, tenant_id=tenant.id, row_id=not_final, phase="OPERATOR_REQUIRED")

    views = await _canonical_views(db, tenant.id, project_id, item_id)
    assert views["all"] == [str(newer_final)]
    assert views["single"] == str(newer_final)
    assert views["approved"] == [str(newer_final)]


async def test_canonical_c_legacy_only_selection_is_deterministic_and_unchanged(
    db: AsyncSession, test_user: User
) -> None:
    """No V3 provenance anywhere: the pre-#649 precedence stands, plus a
    final primary-key tiebreak so exact timestamp ties cannot flap."""
    tenant = await db.get(Tenant, test_user.tenant_id)
    project_id, document_id = await _seed_project(db, tenant)
    item_id = document_id
    base = datetime(2026, 9, 1, 8, 0)
    common = {
        "tenant_id": tenant.id,
        "item_id": item_id,
        "project_id": project_id,
        "document_id": document_id,
    }

    await _add_legacy_row(
        db,
        status=ReviewStatus.APPROVED,
        created_at=base + timedelta(days=9),
        approved_at=base + timedelta(days=9),
        thread_id=None,
        **common,
    )
    with_thread_old = await _add_legacy_row(
        db, status=ReviewStatus.APPROVED, created_at=base, approved_at=base, **common
    )
    with_thread_new = await _add_legacy_row(
        db,
        status=ReviewStatus.APPROVED,
        created_at=base + timedelta(days=2),
        approved_at=base + timedelta(days=1),
        **common,
    )

    views = [await _canonical_views(db, tenant.id, project_id, item_id) for _ in range(3)]
    for v in views:
        assert v["all"] == [str(with_thread_new)], "thread_id, then created_at (unchanged)"
        assert v["single"] == str(with_thread_new)
        assert v["approved"] == [str(with_thread_new)]
    assert with_thread_old

    # Exact tie on every heuristic -> the primary key decides, identically
    # for list and single lookup.
    tie_item = uuid4()
    tie_common = {**common, "item_id": tie_item}
    tie_ids = [
        await _add_legacy_row(
            db, status=ReviewStatus.APPROVED, created_at=base, approved_at=base, **tie_common
        )
        for _ in range(3)
    ]
    expected = str(max(tie_ids, key=str))
    for _ in range(3):
        v = await _canonical_views(db, tenant.id, project_id, tie_item)
        assert v["all"] == [expected]
        assert v["single"] == expected


# ── the boundary is the database, not application memory ────────────────────


async def test_dedupe_boundary_is_the_database_unique_index(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,
    snapshot_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Even a writer that bypassed every application check cannot append a
    second correction for the same finalized operation."""
    from sqlalchemy.exc import IntegrityError

    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    N17_RUNS.clear()

    await _post_approve(
        request_sessions,
        tenant.id,
        arranged.review_item_id,
        saver=saver,
        app=arranged.app,
        sessions=independent_sessions,
    )
    (correction,) = await _events(db, arranged.project_id, HITL_CORRECTION)

    with pytest.raises(IntegrityError):
        async with independent_sessions(tenant.id) as s:
            now = datetime.now()
            s.add(
                ProjectEventORM(
                    event_id=uuid4(),
                    project_id=arranged.project_id,
                    tenant_id=tenant.id,
                    event_type=HITL_CORRECTION,
                    payload={"decision": "APPROVED"},
                    evidence_refs=[],
                    occurred_at=now,
                    created_at=now,
                    resume_operation_id=correction.resume_operation_id,
                )
            )
            await s.flush()
    assert len(await _events(db, arranged.project_id, HITL_CORRECTION)) == 1


# ── a finalized rejection is immutable (Codex review of #650) ────────────────


async def _stored_review(db: AsyncSession, row_id: UUID) -> ReviewItemORM:
    return await _reload(db, ReviewItemORM, row_id)


async def _operation(sessions: Any, tenant_id: UUID, row_id: UUID) -> Any:
    async with sessions(tenant_id) as s:
        return (
            await s.execute(
                text(
                    "SELECT id, phase, decision, decision_hash, current_attempt_id, "
                    "       (SELECT count(*) FROM resume_operations o2 "
                    "         WHERE o2.review_row_id = o.review_row_id) AS n "
                    "  FROM resume_operations o WHERE o.review_row_id = cast(:r as uuid)"
                ),
                {"r": str(row_id)},
            )
        ).one()


async def test_finalized_reject_reason_is_immutable_under_different_reason_replay(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,
    snapshot_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    N17_RUNS.clear()
    common = {"saver": saver, "app": arranged.app, "sessions": independent_sessions}

    first = await _post_reject(
        request_sessions,
        tenant.id,
        arranged.review_item_id,
        reason="reason A",
        reviewer_name="Reviewer A",
        **common,
    )
    assert first.current_status == ReviewStatus.REJECTED
    stored = await _stored_review(db, arranged.review_row_id)
    assert stored.review_metadata.get("rejection_reason") == "reason A"
    assert stored.review_decision == "reason A"
    approved_at_a = stored.approved_at

    replay = await _post_reject(
        request_sessions,
        tenant.id,
        arranged.review_item_id,
        reason="reason B",
        reviewer_name="Reviewer B",
        **common,
    )
    assert replay.current_status == ReviewStatus.REJECTED
    assert replay.row_id == arranged.review_row_id
    assert replay.approved_by == "Reviewer A", "replay returns the STORED decision"

    stored = await _stored_review(db, arranged.review_row_id)
    assert stored.current_status == ReviewStatus.REJECTED.value
    assert stored.review_metadata.get("rejection_reason") == "reason A", (
        "an idempotent replay must never rewrite a finalized rejection reason"
    )
    assert stored.review_decision == "reason A"
    assert stored.approved_by == "Reviewer A"
    assert stored.approved_at == approved_at_a

    op = await _operation(independent_sessions, tenant.id, arranged.review_row_id)
    assert op.phase == "FINALIZED_REJECTED" and op.n == 1
    assert N17_RUNS == []
    analyses = (
        (await db.execute(select(Analysis).where(Analysis.project_id == arranged.project_id)))
        .scalars()
        .all()
    )
    assert analyses == []
    corrections = await _events(db, arranged.project_id, HITL_CORRECTION)
    assert len(corrections) == 1
    assert corrections[0].payload["reason"] == "reason A"


async def test_concurrent_different_reason_rejects_store_the_winning_operations_reason(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,
    snapshot_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    """The winner is whoever V3 ownership says finalized -- not arrival order.

    Correctness is defined by provenance coherence: the stored reason, the
    finalized operation's decision hash and the single correction event must
    all describe the SAME decision, and later replays cannot change it.
    """
    from src.modules.hitl.adapters.persistence.resume_ownership import decision_hash

    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    N17_RUNS.clear()
    common = {"saver": saver, "app": arranged.app, "sessions": independent_sessions}

    results = await asyncio.gather(
        _post_reject(
            request_sessions,
            tenant.id,
            arranged.review_item_id,
            reason="A",
            reviewer_name="Reviewer A",
            **common,
        ),
        _post_reject(
            request_sessions,
            tenant.id,
            arranged.review_item_id,
            reason="B",
            reviewer_name="Reviewer B",
            **common,
        ),
        return_exceptions=True,
    )
    assert any(not isinstance(r, BaseException) for r in results), results

    stored = await _stored_review(db, arranged.review_row_id)
    winning_reason = stored.review_metadata.get("rejection_reason")
    assert winning_reason in {"A", "B"}
    assert stored.review_decision == winning_reason
    assert stored.approved_by == f"Reviewer {winning_reason}"

    op = await _operation(independent_sessions, tenant.id, arranged.review_row_id)
    assert op.phase == "FINALIZED_REJECTED" and op.n == 1
    assert op.decision_hash == decision_hash("reject", winning_reason), (
        "stored reason must be the finalized operation's own feedback"
    )
    corrections = await _events(db, arranged.project_id, HITL_CORRECTION)
    assert len(corrections) == 1
    assert corrections[0].payload["reason"] == winning_reason
    assert str(corrections[0].resume_attempt_id) == str(op.current_attempt_id)

    # Afterwards, neither reason can overwrite the finalized decision.
    for reason in ("A", "B", "C"):
        await _post_reject(
            request_sessions,
            tenant.id,
            arranged.review_item_id,
            reason=reason,
            reviewer_name=f"Reviewer {reason}",
            **common,
        )
    stored = await _stored_review(db, arranged.review_row_id)
    assert stored.review_metadata.get("rejection_reason") == winning_reason
    assert stored.review_decision == winning_reason
    assert stored.approved_by == f"Reviewer {winning_reason}"
    assert len(await _events(db, arranged.project_id, HITL_CORRECTION)) == 1
    assert N17_RUNS == []


async def test_reconciled_rejection_completes_the_same_human_decision(
    real_saver,  # noqa: F811
    independent_sessions,  # noqa: F811
    request_sessions,
    snapshot_enqueues,
    db: AsyncSession,
    test_user: User,
) -> None:
    """The reconciler may FINISH a human decision; it must not author one.

    A rejection's worker dies after acquiring ownership. The sweep that
    completes it must finalize the human's own reason under the SAME
    decision revision -- not a synthetic empty-feedback revision -- so its
    single hitl.correction describes the decision the human actually made.
    """
    from src.core.tasks import hitl_resume_reconciler as reconciler
    from tests.modules.integration.test_p0b_crash_safe_resume_recovery import _sweep

    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    N17_RUNS.clear()

    class _HardDeath:
        checkpointer = saver

        async def ainvoke(self, *_a: Any, **_k: Any) -> dict:
            raise BaseException("SIGKILL")  # noqa: TRY002

    with pytest.raises(BaseException, match="SIGKILL"):
        async with request_sessions() as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant', :t, true)"),
                {"t": str(tenant.id)},
            )
            await ResumeWorkflowUseCase(
                review_queue_repo=SqlAlchemyReviewQueueRepository(
                    session=session, tenant_id=tenant.id
                ),
                checkpoint_service=CheckpointService(checkpointer=saver),
                graph_app=_HardDeath(),
                claim_session_factory=independent_sessions,
            ).execute(
                review_id=arranged.review_item_id,
                request=ResumeWorkflowRequest(
                    decision=WorkflowDecision.REJECT,
                    feedback="human reason",
                    approved_by="Reviewer A",
                ),
            )

    async with independent_sessions(tenant.id) as s:
        await s.execute(
            text(
                "UPDATE resume_operations "
                "   SET lease_expires_at = clock_timestamp() - interval '1 hour' "
                " WHERE review_row_id = cast(:r as uuid)"
            ),
            {"r": str(arranged.review_row_id)},
        )

    swept = await _sweep(reconciler, independent_sessions, tenant, saver, arranged.app)
    assert swept["recovered"] == 1, swept

    stored = await _stored_review(db, arranged.review_row_id)
    assert stored.current_status == ReviewStatus.REJECTED.value
    assert stored.review_metadata.get("rejection_reason") == "human reason"
    assert stored.review_decision == "human reason"
    assert stored.approved_by == "Reviewer A"

    async with independent_sessions(tenant.id) as s:
        revision = (
            await s.execute(
                text(
                    "SELECT decision_revision FROM resume_operations WHERE review_row_id = cast(:r as uuid)"
                ),
                {"r": str(arranged.review_row_id)},
            )
        ).scalar_one()
    assert revision == 1, "completing a decision is not a new decision revision"
    corrections = await _events(db, arranged.project_id, HITL_CORRECTION)
    assert len(corrections) == 1
    assert corrections[0].payload["reason"] == "human reason"
    assert corrections[0].payload["decision_revision"] == 1
    assert N17_RUNS == []
