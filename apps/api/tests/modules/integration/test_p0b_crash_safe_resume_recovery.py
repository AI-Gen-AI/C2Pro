"""
C2PRO P0b CRASH-SAFE HITL RESUME RECOVERY.

Gemini's review of #646 was PARTIAL: the exactly-once claim was correct for
concurrent requests but had no crash story. This suite proves the recovery
semantics, using a REAL CompiledStateGraph, a REAL AsyncPostgresSaver, a
REAL interrupt()/Command(resume), real PostgreSQL and deterministic faults
injected at the exact durability boundaries.

Crash points covered (CP1-CP6 of the required matrix):

CP1 after durable claim, before graph invocation
CP2 during graph, before N17
CP3 after N17 committed, before the completion marker  (the dangerous one)
CP4 after finalization, before the HTTP response
CP5 document-status write failure
CP6 hard death leaving a stale claim -> no permanent deadlock

The guarantee proven here is EFFECTIVELY_ONCE_RECOVERABLE, not global
exactly-once: a crash can still replay the graph, and the graph's own
non-N17 nodes would re-execute. What is fenced is the DURABLE effect --
N17's analysis is keyed by a stable per-operation idempotency key with a
partial unique index, so a replay adopts the existing analysis and emits no
second graph.completed.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph
from psycopg_pool import AsyncConnectionPool
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.analysis.adapters.graph.nodes import (
    human_interrupt_node,
    route_after_human_interrupt,
    save_to_db_node,
)
from src.analysis.adapters.graph.schema import ProjectState
from src.analysis.adapters.persistence.models import Analysis
from src.core.auth.models import Tenant, User
from src.documents.adapters.persistence.models import DocumentORM
from src.modules.hitl.adapters.checkpoint_service import CheckpointService
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.adapters.persistence.repository import (
    SqlAlchemyReviewQueueRepository,
)
from src.modules.hitl.adapters.persistence.resume_operations import ResumePhase
from src.modules.hitl.application.resume_workflow_use_case import (
    ResumeWorkflowRequest,
    ResumeWorkflowUseCase,
    WorkflowDecision,
)
from src.modules.hitl.domain.entities import ReviewStatus
from src.projects.adapters.persistence.models import ProjectORM
from src.temporal.adapters.persistence.models import ProjectEventORM

pytestmark = pytest.mark.asyncio

N17_RUNS: list[str] = []


class InjectedCrash(RuntimeError):
    """Stands in for hard process loss at a durability boundary."""


# ── real infrastructure ──────────────────────────────────────────────────────


def _dsn() -> str:
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("DATABASE_URL/TEST_DATABASE_URL not set")
    return dsn


@pytest.fixture
async def real_saver():
    pool = AsyncConnectionPool(
        conninfo=_dsn().replace("postgresql+asyncpg://", "postgresql://"),
        min_size=0,
        max_size=8,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": None},
    )
    await pool.open(wait=True, timeout=15)
    saver = AsyncPostgresSaver(conn=pool)
    threads: list[str] = []
    try:
        yield saver, threads.append
    finally:
        async with pool.connection() as conn, conn.cursor() as cur:
            for t in threads:
                await cur.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s", (t,))
                await cur.execute("DELETE FROM checkpoint_blobs WHERE thread_id = %s", (t,))
                await cur.execute("DELETE FROM checkpoints WHERE thread_id = %s", (t,))
        await pool.close()


@pytest.fixture
async def independent_sessions():
    """A session factory on its OWN engine/connections.

    The operation store must be driven through genuinely separate
    transactions -- sharing the test's AsyncSession would hide exactly the
    cross-connection behaviour (visibility, CAS arbitration) being proven.
    """
    engine = create_async_engine(_dsn(), pool_size=10, max_overflow=10)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def factory(tenant_id: UUID):
        async with maker() as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant', :t, true)"),
                {"t": str(tenant_id)},
            )
            yield session
            await session.commit()

    try:
        yield factory
    finally:
        await engine.dispose()


# ── the real graph over the real production nodes ────────────────────────────


async def _entry(state: ProjectState) -> ProjectState:
    return state


async def _counting_n17(state: ProjectState) -> ProjectState:
    N17_RUNS.append(str(state.get("document_id")))
    return await save_to_db_node(state)


def _build_real_graph(saver: AsyncPostgresSaver):
    g = StateGraph(ProjectState)
    g.add_node("entry", _entry)
    g.add_node("human_interrupt", human_interrupt_node)
    g.add_node("save_to_db", _counting_n17)
    g.set_entry_point("entry")
    g.add_edge("entry", "human_interrupt")
    g.add_conditional_edges(
        "human_interrupt",
        route_after_human_interrupt,
        {"enrichment_dispatch": "save_to_db", "terminated": END},
    )
    g.add_edge("save_to_db", END)
    return g.compile(checkpointer=saver)


# ── seeding ──────────────────────────────────────────────────────────────────


async def _seed(db: AsyncSession, tenant: Tenant) -> DocumentORM:
    project_id, document_id = uuid4(), uuid4()
    db.add(
        ProjectORM(
            id=project_id,
            tenant_id=tenant.id,
            name="Crash Safe Resume Project",
            code="P0B-CRASH",
            start_date=datetime.now(),
        )
    )
    await db.commit()
    document = DocumentORM(
        id=document_id,
        tenant_id=tenant.id,
        project_id=project_id,
        document_type="contract",
        filename="crash_safe.pdf",
        upload_status="parsed_pending_analysis",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


def _initial_state(document: DocumentORM, tenant: Tenant, thread_id: str) -> dict[str, Any]:
    return {
        "project_id": str(document.project_id),
        "document_id": str(document.id),
        "tenant_id": str(tenant.id),
        "thread_id": thread_id,
        "doc_type": "contract",
        "document_text": "",
        "retry_count": 0,
        "confidence_score": 0.0,
        "critique_notes": "",
        "messages": [],
        "extracted_risks": [],
        "extracted_wbs": [],
        "coherence_score": 90,
        "coherence_breakdown": {"overall": 90},
        "single_document_assessment": {
            "single_document_assessment": {
                "evidence_granularity": "document",
                "proof_marker": "p0b-crash-safe",
            }
        },
        "node_results": [],
    }


async def _arrange(db, tenant, saver, register):
    """Seed a document, run the real graph to its interrupt, wire the review."""
    document = await _seed(db, tenant)
    thread_id = register(f"document:{document.id}:analysis") or f"document:{document.id}:analysis"
    app = _build_real_graph(saver)
    cfg = {"configurable": {"thread_id": thread_id}}
    result = await app.ainvoke(_initial_state(document, tenant, thread_id), cfg)
    assert "__interrupt__" in result
    checkpoint_id = (await app.aget_state(cfg)).config["configurable"]["checkpoint_id"]

    review = (
        await db.execute(select(ReviewItemORM).where(ReviewItemORM.document_id == document.id))
    ).scalars().one()
    review.thread_id, review.checkpoint_id = thread_id, checkpoint_id
    review.review_metadata = {
        **(review.review_metadata or {}),
        "tenant_id": str(tenant.id),
        "document_id": str(document.id),
    }
    await db.commit()
    await db.refresh(review)
    await db.refresh(document)
    # Plain values: the session expires ORM objects on commit, and a later
    # synchronous attribute touch on an expired instance raises
    # MissingGreenlet instead of lazily reloading.
    return _Arranged(
        document_id=document.id,
        project_id=document.project_id,
        app=app,
        review_row_id=review.id,
        review_item_id=review.item_id,
        checkpoint_id=checkpoint_id,
    )


@dataclass(frozen=True)
class _Arranged:
    document_id: UUID
    project_id: UUID
    app: Any
    review_row_id: UUID
    review_item_id: UUID
    checkpoint_id: str


async def _reload(db: AsyncSession, model: Any, pk: UUID) -> Any:
    """Re-read a row's CURRENT database state.

    populate_existing refreshes the instance already in the identity map --
    necessary because finalization commits in its own transaction, so the
    test session's cached copy is stale by design.
    """
    return (
        await db.execute(
            select(model).where(model.id == pk).execution_options(populate_existing=True)
        )
    ).scalars().one()


def _use_case(db, tenant, saver, app, sessions, *, fault=None, lease_seconds=120):
    return ResumeWorkflowUseCase(
        review_queue_repo=SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant.id),
        checkpoint_service=CheckpointService(checkpointer=saver),
        graph_app=app,
        claim_session_factory=sessions,
        lease_seconds=lease_seconds,
        fault=fault,
    )


def _approve(approved_by: str = "Reviewer") -> ResumeWorkflowRequest:
    return ResumeWorkflowRequest(
        decision=WorkflowDecision.APPROVE, feedback="", approved_by=approved_by
    )


async def _operation_row(sessions, tenant_id: UUID, review_row_id: UUID) -> Any:
    async with sessions(tenant_id) as s:
        return (
            await s.execute(
                text(
                    "SELECT phase, analysis_id, attempts, idempotency_key "
                    "FROM hitl_resume_operations WHERE review_row_id = cast(:r as uuid)"
                ),
                {"r": str(review_row_id)},
            )
        ).first()


async def _counts(db: AsyncSession, project_id: UUID) -> tuple[int, int]:
    analyses = (
        await db.execute(select(Analysis).where(Analysis.project_id == project_id))
    ).scalars().all()
    events = (
        await db.execute(
            select(ProjectEventORM).where(
                ProjectEventORM.project_id == project_id,
                ProjectEventORM.event_type == "graph.completed",
            )
        )
    ).scalars().all()
    return len(analyses), len(events)


# ── CP1: crash after claim, before graph ─────────────────────────────────────


async def test_cp1_crash_after_claim_before_graph_recovers(
    real_saver, independent_sessions, db: AsyncSession, test_user: User
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    app = arranged.app
    N17_RUNS.clear()

    class _NeverRuns:
        checkpointer = saver

        async def ainvoke(self, *_a: Any, **_k: Any) -> dict:
            raise InjectedCrash("worker lost after claim, before graph")

    with pytest.raises(InjectedCrash):
        await _use_case(db, tenant, saver, _NeverRuns(), independent_sessions).execute(
            review_id=arranged.review_item_id, request=_approve()
        )

    assert N17_RUNS == []
    refreshed = await _reload(db, ReviewItemORM, arranged.review_row_id)
    assert refreshed.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED.value

    # The operation is retryable, NOT a permanent deadlock.
    op = await _operation_row(independent_sessions, tenant.id, arranged.review_row_id)
    assert op.phase == ResumePhase.FAILED_RETRYABLE.value

    # ...and a retry genuinely succeeds.
    response = await _use_case(db, tenant, saver, app, independent_sessions).execute(
        review_id=arranged.review_item_id, request=_approve()
    )
    assert response.status == "resumed"
    assert len(N17_RUNS) == 1
    assert await _counts(db, arranged.project_id) == (1, 1)


# ── CP2: crash during graph, before N17 ──────────────────────────────────────


async def test_cp2_crash_during_graph_before_n17_recovers(
    real_saver, independent_sessions, db: AsyncSession, test_user: User
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    app = arranged.app
    N17_RUNS.clear()

    class _DiesBeforeN17:
        checkpointer = saver

        async def ainvoke(self, *_a: Any, **_k: Any) -> dict:
            raise InjectedCrash("died mid-graph before N17")

    with pytest.raises(InjectedCrash):
        await _use_case(db, tenant, saver, _DiesBeforeN17(), independent_sessions).execute(
            review_id=arranged.review_item_id, request=_approve()
        )

    assert N17_RUNS == []
    assert await _counts(db, arranged.project_id) == (0, 0)
    assert (await _reload(db, ReviewItemORM, arranged.review_row_id)).current_status == (
        ReviewStatus.PENDING_REVIEW_REQUIRED.value
    )
    refreshed_doc = await _reload(db, DocumentORM, arranged.document_id)
    assert refreshed_doc.upload_status == "parsed_pending_analysis"

    response = await _use_case(db, tenant, saver, app, independent_sessions).execute(
        review_id=arranged.review_item_id, request=_approve()
    )
    assert response.status == "resumed"
    assert len(N17_RUNS) == 1
    assert await _counts(db, arranged.project_id) == (1, 1)


# ── CP3: crash after N17 committed, before the completion marker ─────────────


async def test_cp3_crash_after_n17_before_completion_marker_does_not_duplicate(
    real_saver, independent_sessions, db: AsyncSession, test_user: User
) -> None:
    """The dangerous window: the analysis is already durable but nothing has
    recorded that yet. A retry MUST NOT produce a second analysis.
    """
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    app = arranged.app
    N17_RUNS.clear()

    async def crash_after_graph(point: str) -> None:
        if point == "after_graph_before_completion_marker":
            raise InjectedCrash("worker lost after N17 commit, before marker")

    with pytest.raises(InjectedCrash):
        await _use_case(
            db, tenant, saver, app, independent_sessions, fault=crash_after_graph
        ).execute(review_id=arranged.review_item_id, request=_approve())

    # N17 really did run and really did commit.
    assert len(N17_RUNS) == 1
    assert await _counts(db, arranged.project_id) == (1, 1)
    assert (await _reload(db, ReviewItemORM, arranged.review_row_id)).current_status == (
        ReviewStatus.PENDING_REVIEW_REQUIRED.value
    ), "no false approval from a crash"

    # Retry: the graph replays (we have no marker), but N17 is FENCED.
    response = await _use_case(db, tenant, saver, app, independent_sessions).execute(
        review_id=arranged.review_item_id, request=_approve()
    )
    assert response.status == "resumed"

    analyses, events = await _counts(db, arranged.project_id)
    assert analyses == 1, "the idempotency key must prevent a second analysis"
    assert events == 1, "and a second graph.completed event"

    assert (await _reload(db, ReviewItemORM, arranged.review_row_id)).current_status == (
        ReviewStatus.APPROVED.value
    )
    assert (await _reload(db, DocumentORM, arranged.document_id)).upload_status == "analyzed"


# ── CP3b: crash after the marker, before finalization ────────────────────────


async def test_cp3b_crash_after_completion_marker_finalizes_without_replaying_graph(
    real_saver, independent_sessions, db: AsyncSession, test_user: User
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    app = arranged.app
    N17_RUNS.clear()

    async def crash_before_finalize(point: str) -> None:
        if point == "after_completion_marker_before_finalize":
            raise InjectedCrash("worker lost after marker, before finalization")

    with pytest.raises(InjectedCrash):
        await _use_case(
            db, tenant, saver, app, independent_sessions, fault=crash_before_finalize
        ).execute(review_id=arranged.review_item_id, request=_approve())

    assert len(N17_RUNS) == 1
    op = await _operation_row(independent_sessions, tenant.id, arranged.review_row_id)
    assert op.phase == ResumePhase.GRAPH_COMPLETED.value
    assert op.analysis_id is not None, "durable completion identity recorded"

    # Recovery finalizes WITHOUT touching the graph at all.
    class _MustNotRun:
        checkpointer = saver

        async def ainvoke(self, *_a: Any, **_k: Any) -> dict:
            raise AssertionError("graph must NOT be replayed after GRAPH_COMPLETED")

    response = await _use_case(db, tenant, saver, _MustNotRun(), independent_sessions).execute(
        review_id=arranged.review_item_id, request=_approve()
    )
    assert response.status == "resumed"
    assert len(N17_RUNS) == 1, "N17 must not run again"
    assert await _counts(db, arranged.project_id) == (1, 1)

    assert (await _reload(db, ReviewItemORM, arranged.review_row_id)).current_status == (
        ReviewStatus.APPROVED.value
    )
    assert (await _reload(db, DocumentORM, arranged.document_id)).upload_status == "analyzed"
    op = await _operation_row(independent_sessions, tenant.id, arranged.review_row_id)
    assert op.phase == ResumePhase.FINALIZED.value


# ── CP4: crash after finalization, before the HTTP response ──────────────────


async def test_cp4_retry_after_finalization_is_idempotent(
    real_saver, independent_sessions, db: AsyncSession, test_user: User
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    app = arranged.app
    N17_RUNS.clear()

    first = await _use_case(db, tenant, saver, app, independent_sessions).execute(
        review_id=arranged.review_item_id, request=_approve()
    )
    assert first.status == "resumed"

    # The response never reached the client; the operator retries.
    class _MustNotRun:
        checkpointer = saver

        async def ainvoke(self, *_a: Any, **_k: Any) -> dict:
            raise AssertionError("a finalized operation must never re-run the graph")

    second = await _use_case(db, tenant, saver, _MustNotRun(), independent_sessions).execute(
        review_id=arranged.review_item_id, request=_approve()
    )
    assert second.status in {"resumed", ReviewStatus.APPROVED.value}
    assert len(N17_RUNS) == 1
    assert await _counts(db, arranged.project_id) == (1, 1)


# ── CP5: document-status write failure must not be a false success ───────────


async def test_cp5_document_status_failure_is_surfaced_and_recoverable(
    real_saver, independent_sessions, db: AsyncSession, test_user: User
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    app = arranged.app
    N17_RUNS.clear()

    async def fail_document_write(point: str) -> None:
        if point == "document":
            raise InjectedCrash("document status write failed")

    with pytest.raises(InjectedCrash):
        await _use_case(
            db, tenant, saver, app, independent_sessions, fault=fail_document_write
        ).execute(review_id=arranged.review_item_id, request=_approve())

    # NO false success: the whole finalization rolled back together.
    assert (await _reload(db, ReviewItemORM, arranged.review_row_id)).current_status == (
        ReviewStatus.PENDING_REVIEW_REQUIRED.value
    ), "review must not be APPROVED when the document transition failed"
    assert (await _reload(db, DocumentORM, arranged.document_id)).upload_status == (
        "parsed_pending_analysis"
    )
    assert await _counts(db, arranged.project_id) == (1, 1)

    op = await _operation_row(independent_sessions, tenant.id, arranged.review_row_id)
    assert op.phase == ResumePhase.GRAPH_COMPLETED.value, "recoverable, graph not replayable"

    # Recovery completes the finalization without re-running the graph.
    class _MustNotRun:
        checkpointer = saver

        async def ainvoke(self, *_a: Any, **_k: Any) -> dict:
            raise AssertionError("graph must NOT be replayed to fix a document write")

    response = await _use_case(db, tenant, saver, _MustNotRun(), independent_sessions).execute(
        review_id=arranged.review_item_id, request=_approve()
    )
    assert response.status == "resumed"
    assert len(N17_RUNS) == 1
    assert (await _reload(db, ReviewItemORM, arranged.review_row_id)).current_status == (
        ReviewStatus.APPROVED.value
    )
    assert (await _reload(db, DocumentORM, arranged.document_id)).upload_status == "analyzed"
    assert await _counts(db, arranged.project_id) == (1, 1)


# ── CP6: stale claim from a hard death must not deadlock forever ─────────────


async def test_cp6_stale_claim_does_not_deadlock_forever(
    real_saver, independent_sessions, db: AsyncSession, test_user: User
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    app = arranged.app
    N17_RUNS.clear()

    # A worker claims and is then lost WITHOUT any handler running -- the
    # claim is simply abandoned in CLAIMED with a live-looking lease.
    class _HardDeath:
        checkpointer = saver

        async def ainvoke(self, *_a: Any, **_k: Any) -> dict:
            raise BaseException("SIGKILL")  # noqa: TRY002 - not caught by except Exception

    with pytest.raises(BaseException, match="SIGKILL"):
        await _use_case(db, tenant, saver, _HardDeath(), independent_sessions).execute(
            review_id=arranged.review_item_id, request=_approve()
        )

    op = await _operation_row(independent_sessions, tenant.id, arranged.review_row_id)
    assert op.phase == ResumePhase.CLAIMED.value, "abandoned mid-flight, nothing released it"

    # While the lease is alive, a second caller is correctly refused.
    with pytest.raises(ValueError, match="already being resumed"):
        await _use_case(db, tenant, saver, app, independent_sessions).execute(
            review_id=arranged.review_item_id, request=_approve()
        )

    # Age the heartbeat past the lease: the worker is genuinely gone.
    async with independent_sessions(tenant.id) as s:
        await s.execute(
            text(
                "UPDATE hitl_resume_operations SET heartbeat_at = :ts "
                "WHERE review_row_id = cast(:r as uuid)"
            ),
            {
                "ts": datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
                "r": str(arranged.review_row_id),
            },
        )

    response = await _use_case(db, tenant, saver, app, independent_sessions).execute(
        review_id=arranged.review_item_id, request=_approve()
    )
    assert response.status == "resumed", "a stale claim must be recoverable, not permanent"
    assert len(N17_RUNS) == 1
    assert await _counts(db, arranged.project_id) == (1, 1)

    op = await _operation_row(independent_sessions, tenant.id, arranged.review_row_id)
    assert op.attempts >= 2, "takeover is recorded as a new attempt"


async def test_live_lease_is_not_taken_over(
    real_saver, independent_sessions, db: AsyncSession, test_user: User
) -> None:
    """A healthy long-running worker must not be stolen from mid-flight."""
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    app = arranged.app
    N17_RUNS.clear()

    started = asyncio.Event()
    release = asyncio.Event()

    class _SlowGraph:
        checkpointer = saver

        async def ainvoke(self, resume_signal: Any, config: dict) -> dict:
            started.set()
            await release.wait()
            return await app.ainvoke(resume_signal, config)

    slow = asyncio.create_task(
        _use_case(
            db, tenant, saver, _SlowGraph(), independent_sessions, lease_seconds=3
        ).execute(review_id=arranged.review_item_id, request=_approve())
    )
    await asyncio.wait_for(started.wait(), timeout=10)

    # Heartbeats keep renewing well past the 3s lease.
    await asyncio.sleep(5)
    with pytest.raises(ValueError, match="already being resumed"):
        await _use_case(
            db, tenant, saver, app, independent_sessions, lease_seconds=3
        ).execute(review_id=arranged.review_item_id, request=_approve())

    release.set()
    assert (await slow).status == "resumed"
    assert len(N17_RUNS) == 1
    assert await _counts(db, arranged.project_id) == (1, 1)


# ── real multi-connection concurrency ────────────────────────────────────────


async def test_real_multi_connection_concurrent_approve_runs_graph_once(
    real_saver, independent_sessions, db: AsyncSession, test_user: User
) -> None:
    """Gemini's point: the previous race test shared one AsyncSession.

    Here each competing caller gets its OWN engine-backed session and its own
    connection/transaction, so the CAS is arbitrated by PostgreSQL across
    connections exactly as it is in production across API workers.
    """
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    app = arranged.app
    N17_RUNS.clear()

    engine = create_async_engine(_dsn(), pool_size=10, max_overflow=10)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def competing_caller() -> Any:
        async with maker() as own_session:
            await own_session.execute(
                text("SELECT set_config('app.current_tenant', :t, true)"),
                {"t": str(tenant.id)},
            )
            use_case = ResumeWorkflowUseCase(
                review_queue_repo=SqlAlchemyReviewQueueRepository(
                    session=own_session, tenant_id=tenant.id
                ),
                checkpoint_service=CheckpointService(checkpointer=saver),
                graph_app=app,
                claim_session_factory=independent_sessions,
            )
            try:
                return await use_case.execute(
                    review_id=arranged.review_item_id, request=_approve()
                )
            finally:
                await own_session.commit()

    try:
        results = await asyncio.gather(
            competing_caller(), competing_caller(), competing_caller(),
            return_exceptions=True,
        )
    finally:
        await engine.dispose()

    succeeded = [r for r in results if not isinstance(r, BaseException)]
    refused = [r for r in results if isinstance(r, ValueError)]
    assert succeeded, f"at least one caller must win: {results}"
    assert refused, "the losers must be refused deterministically, not deadlocked"

    assert len(N17_RUNS) == 1, f"exactly one graph execution, got {N17_RUNS}"
    assert await _counts(db, arranged.project_id) == (1, 1)

    assert (await _reload(db, ReviewItemORM, arranged.review_row_id)).current_status == (
        ReviewStatus.APPROVED.value
    )
    rows = (
        await db.execute(select(ReviewItemORM).where(ReviewItemORM.document_id == arranged.document_id))
    ).scalars().all()
    assert len(rows) == 1, "no fifth review row"


# ── reject path ──────────────────────────────────────────────────────────────


async def test_reject_is_crash_safe_and_never_runs_n17(
    real_saver, independent_sessions, db: AsyncSession, test_user: User
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    app = arranged.app
    N17_RUNS.clear()

    reject = ResumeWorkflowRequest(
        decision=WorkflowDecision.REJECT, feedback="bad extraction", approved_by="R"
    )

    # A failed rejection leaves no permanent claim and no false success.
    class _Dies:
        checkpointer = saver

        async def ainvoke(self, *_a: Any, **_k: Any) -> dict:
            raise InjectedCrash("died during rejection")

    with pytest.raises(InjectedCrash):
        await _use_case(db, tenant, saver, _Dies(), independent_sessions).execute(
            review_id=arranged.review_item_id, request=reject
        )
    op = await _operation_row(independent_sessions, tenant.id, arranged.review_row_id)
    assert op.phase == ResumePhase.FAILED_RETRYABLE.value
    assert (await _reload(db, ReviewItemORM, arranged.review_row_id)).current_status == (
        ReviewStatus.PENDING_REVIEW_REQUIRED.value
    )

    response = await _use_case(db, tenant, saver, app, independent_sessions).execute(
        review_id=arranged.review_item_id, request=reject
    )
    assert response.status == "rejected"
    assert N17_RUNS == [], "a rejection must never reach N17"
    assert await _counts(db, arranged.project_id) == (0, 0)

    assert (await _reload(db, ReviewItemORM, arranged.review_row_id)).current_status == (
        ReviewStatus.REJECTED.value
    )
    # A rejection must NOT mark the document analyzed.
    assert (await _reload(db, DocumentORM, arranged.document_id)).upload_status == (
        "parsed_pending_analysis"
    )
    op = await _operation_row(independent_sessions, tenant.id, arranged.review_row_id)
    assert op.phase == ResumePhase.FINALIZED.value


# ── tenant isolation of the operation store ──────────────────────────────────


async def test_cross_tenant_cannot_claim_or_recover(
    real_saver,
    independent_sessions,
    db: AsyncSession,
    test_user: User,
    test_tenant_2: Tenant,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    app = arranged.app
    N17_RUNS.clear()

    other = ResumeWorkflowUseCase(
        review_queue_repo=SqlAlchemyReviewQueueRepository(
            session=db, tenant_id=test_tenant_2.id
        ),
        checkpoint_service=CheckpointService(checkpointer=saver),
        graph_app=app,
        claim_session_factory=independent_sessions,
    )
    with pytest.raises(ValueError):
        await other.execute(review_id=arranged.review_item_id, request=_approve("Intruder"))

    assert N17_RUNS == []
    assert (await _reload(db, ReviewItemORM, arranged.review_row_id)).current_status == (
        ReviewStatus.PENDING_REVIEW_REQUIRED.value
    )
