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
from src.modules.hitl.adapters.persistence.resume_ownership import Phase
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


def _dsn(db) -> str:
    """The async DSN of the database the harness actually bootstrapped.

    Taken from the bound engine rather than the environment: the harness
    resolves and normalises the test URL itself, so re-reading env vars can
    (and did) yield a *sync* `postgresql://` DSN pointing at a database the
    fixtures never prepared.
    """
    url = db.get_bind().url
    if url.get_driver_name() != "asyncpg":
        url = url.set(drivername="postgresql+asyncpg")
    return url.render_as_string(hide_password=False)


@pytest.fixture
async def real_saver(db):
    pool = AsyncConnectionPool(
        conninfo=_dsn(db).replace("postgresql+asyncpg://", "postgresql://"),
        min_size=0,
        max_size=8,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": None},
    )
    await pool.open(wait=True, timeout=15)
    saver = AsyncPostgresSaver(conn=pool)
    await saver.setup()
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
async def independent_sessions(db):
    """A session factory on its OWN engine/connections.

    The operation store must be driven through genuinely separate
    transactions -- sharing the test's AsyncSession would hide exactly the
    cross-connection behaviour (visibility, CAS arbitration) being proven.

    Depends on `db` deliberately: the test_engine fixture is function-scoped
    and destructively resets the public schema per test, so an engine built
    BEFORE that bootstrap would hold connections whose schema no longer
    exists.
    """
    _ = db
    engine = create_async_engine(_dsn(db), pool_size=10, max_overflow=10)
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
                    "SELECT o.phase, o.analysis_id, o.fencing_token, "
                    "       o.decision_revision, o.failure_count, "
                    "       o.terminal_checkpoint_id, "
                    "       (SELECT count(*) FROM resume_operation_attempts a "
                    "          WHERE a.operation_id = o.id) AS attempts "
                    "  FROM resume_operations o "
                    " WHERE o.review_row_id = cast(:r as uuid)"
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


async def _persisted_events(db: AsyncSession, project_id: UUID) -> int:
    """`analysis.persisted` count -- N17's OWN durability event.

    Asserted separately from `graph.completed` on purpose: conflating the
    two is precisely what let a mid-graph crash look like a finished run.
    """
    rows = (
        await db.execute(
            select(ProjectEventORM).where(
                ProjectEventORM.project_id == project_id,
                ProjectEventORM.event_type == "analysis.persisted",
            )
        )
    ).scalars().all()
    return len(rows)


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
    assert op.phase == Phase.FAILED_RETRYABLE.value

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
        if point == "after_graph_before_terminal_marker":
            raise InjectedCrash("worker lost after N17 commit, before marker")

    with pytest.raises(InjectedCrash):
        await _use_case(
            db, tenant, saver, app, independent_sessions, fault=crash_after_graph
        ).execute(review_id=arranged.review_item_id, request=_approve())

    # N17 really did run and really did commit -- and this is exactly the
    # window V3 exists to describe honestly: the analysis is DURABLE, so
    # `analysis.persisted` is recorded, while the graph had not been
    # verified terminal, so `graph.completed` must NOT be. V2 emitted a
    # single conflated event here, which is what made a mid-graph crash
    # indistinguishable from a finished run.
    assert len(N17_RUNS) == 1
    analyses, completed = await _counts(db, arranged.project_id)
    assert analyses == 1, "N17 committed"
    assert completed == 0, "the graph was never verified terminal"
    assert await _persisted_events(db, arranged.project_id) == 1

    op = await _operation_row(independent_sessions, tenant.id, arranged.review_row_id)
    assert op.phase == Phase.N17_DURABLE.value, (
        "durable evidence must survive the failure; overwriting it with "
        "FAILED_RETRYABLE would make the retry replay N17"
    )

    assert (await _reload(db, ReviewItemORM, arranged.review_row_id)).current_status == (
        ReviewStatus.PENDING_REVIEW_REQUIRED.value
    ), "no false approval from a crash"

    # Retry: the graph replays (we have no marker), but N17 is FENCED.
    response = await _use_case(db, tenant, saver, app, independent_sessions).execute(
        review_id=arranged.review_item_id, request=_approve()
    )
    assert response.status == "resumed"

    analyses, events = await _counts(db, arranged.project_id)
    assert analyses == 1, "operation-keyed detection must prevent a second analysis"
    assert events == 1, "exactly one graph.completed, emitted by the retry"
    assert await _persisted_events(db, arranged.project_id) == 1, (
        "and no second analysis.persisted"
    )

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
        if point == "after_terminal_marker_before_finalize":
            raise InjectedCrash("worker lost after marker, before finalization")

    with pytest.raises(InjectedCrash):
        await _use_case(
            db, tenant, saver, app, independent_sessions, fault=crash_before_finalize
        ).execute(review_id=arranged.review_item_id, request=_approve())

    assert len(N17_RUNS) == 1
    op = await _operation_row(independent_sessions, tenant.id, arranged.review_row_id)
    assert op.phase == Phase.GRAPH_COMPLETED.value
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
    assert op.phase == Phase.FINALIZED_APPROVED.value


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
    assert op.phase == Phase.GRAPH_COMPLETED.value, "recoverable, graph not replayable"

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
    assert op.phase == Phase.RUNNING.value, "abandoned mid-flight, nothing released it"

    # While the lease is alive, a second caller is correctly refused.
    with pytest.raises(ValueError, match="already being resumed"):
        await _use_case(db, tenant, saver, app, independent_sessions).execute(
            review_id=arranged.review_item_id, request=_approve()
        )

    # Age the heartbeat past the lease: the worker is genuinely gone.
    async with independent_sessions(tenant.id) as s:
        await s.execute(
            text(
                "UPDATE resume_operations "
                "   SET heartbeat_at = :ts, lease_expires_at = :ts "
                " WHERE review_row_id = cast(:r as uuid)"
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
        """Delays the resume but is otherwise the REAL graph.

        aget_state must delegate: terminal verification is part of the
        contract under test, and a stand-in that cannot report its state
        would fail the resume for a reason unrelated to the lease.
        """

        checkpointer = saver

        async def ainvoke(self, resume_signal: Any, config: dict) -> dict:
            started.set()
            await release.wait()
            return await app.ainvoke(resume_signal, config)

        async def aget_state(self, config: dict) -> Any:
            return await app.aget_state(config)

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

    engine = create_async_engine(_dsn(db), pool_size=10, max_overflow=10)
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
    assert op.phase == Phase.FAILED_RETRYABLE.value
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
    assert op.phase == Phase.FINALIZED_REJECTED.value


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


# ── CP7: takeover must not inherit a superseded attempt's resume ─────────────


def _build_graph_with_failing_n17(saver: AsyncPostgresSaver):
    """The real graph, but N17 dies AFTER the interrupt has been consumed.

    That ordering is the point: the human_interrupt node runs and its
    checkpoint is written, so the thread is left carrying DESCENDANTS of the
    first attempt before anything durable was persisted.
    """

    async def _dying_n17(state: ProjectState) -> ProjectState:
        N17_RUNS.append(str(state.get("document_id")))
        raise InjectedCrash("died inside N17, before any commit")

    g = StateGraph(ProjectState)
    g.add_node("entry", _entry)
    g.add_node("human_interrupt", human_interrupt_node)
    g.add_node("save_to_db", _dying_n17)
    g.set_entry_point("entry")
    g.add_edge("entry", "human_interrupt")
    g.add_conditional_edges(
        "human_interrupt",
        route_after_human_interrupt,
        {"enrichment_dispatch": "save_to_db", "terminated": END},
    )
    g.add_edge("save_to_db", END)
    return g.compile(checkpointer=saver)


async def test_cp7_takeover_applies_its_own_decision_not_the_superseded_one(
    real_saver, independent_sessions, db: AsyncSession, test_user: User
) -> None:
    """The severe case: a CHANGED decision after a crashed attempt.

    LangGraph stores a `Command(resume=...)` payload against the checkpoint
    being resumed, and re-resuming that checkpoint re-delivers the FIRST
    payload. Without a per-attempt fork, this test's takeover would replay
    attempt 1's APPROVE while the reviewer asked for REJECT -- silently
    running N17 and persisting an analysis for a REJECTED review.

    It also pins the selection rule: the takeover must restart from the
    IMMUTABLE interrupt checkpoint, never adopt the superseded attempt's
    descendants.
    """
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    N17_RUNS.clear()

    # Attempt 1: APPROVE, consumes the interrupt, writes descendants, dies
    # inside N17 before committing anything.
    dying = _build_graph_with_failing_n17(saver)
    with pytest.raises(InjectedCrash):
        await _use_case(db, tenant, saver, dying, independent_sessions).execute(
            review_id=arranged.review_item_id, request=_approve()
        )

    assert len(N17_RUNS) == 1, "the first attempt really did reach N17"
    assert await _counts(db, arranged.project_id) == (0, 0), "but committed nothing"
    assert await _persisted_events(db, arranged.project_id) == 0

    # The thread now carries attempt 1's descendants past the interrupt.
    latest = (
        await arranged.app.aget_state(
            {"configurable": {"thread_id": f"document:{arranged.document_id}:analysis"}}
        )
    ).config["configurable"]["checkpoint_id"]
    assert latest != arranged.checkpoint_id, "attempt 1 advanced the thread"

    # Attempt 2: a different reviewer REJECTS.
    reject = ResumeWorkflowRequest(
        decision=WorkflowDecision.REJECT, feedback="not acceptable", approved_by="R2"
    )
    response = await _use_case(
        db, tenant, saver, arranged.app, independent_sessions
    ).execute(review_id=arranged.review_item_id, request=reject)

    assert response.status == "rejected"
    assert len(N17_RUNS) == 1, "the REJECT must never reach N17"
    assert await _counts(db, arranged.project_id) == (0, 0)
    assert await _persisted_events(db, arranged.project_id) == 0

    assert (await _reload(db, ReviewItemORM, arranged.review_row_id)).current_status == (
        ReviewStatus.REJECTED.value
    ), "the takeover's decision must win, not the superseded attempt's"
    assert (await _reload(db, DocumentORM, arranged.document_id)).upload_status == (
        "parsed_pending_analysis"
    )

    op = await _operation_row(independent_sessions, tenant.id, arranged.review_row_id)
    assert op.phase == Phase.FINALIZED_REJECTED.value
    assert op.decision_revision == 2, "a changed decision is a new revision"
    assert op.attempts >= 2, "and a new, separately-recorded attempt"


async def test_superseded_attempt_descendants_are_never_adopted(
    real_saver, independent_sessions, db: AsyncSession, test_user: User
) -> None:
    """Selection must be attempt-specific, not latest-by-thread.

    The resume config a takeover chooses must never be the newest checkpoint
    on the thread: that is a half-advanced state belonging to a dead worker.
    """
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    N17_RUNS.clear()

    dying = _build_graph_with_failing_n17(saver)
    with pytest.raises(InjectedCrash):
        await _use_case(db, tenant, saver, dying, independent_sessions).execute(
            review_id=arranged.review_item_id, request=_approve()
        )

    thread_id = f"document:{arranged.document_id}:analysis"
    stale = (
        await arranged.app.aget_state({"configurable": {"thread_id": thread_id}})
    ).config["configurable"]["checkpoint_id"]

    # Ask the use case which checkpoint the NEXT attempt is entitled to.
    from src.modules.hitl.adapters.persistence.resume_ownership import acquire

    ownership, _phase, _refusal = await acquire(
        review_row_id=arranged.review_row_id,
        tenant_id=tenant.id,
        project_id=arranged.project_id,
        document_id=arranged.document_id,
        thread_id=thread_id,
        source_checkpoint_id=arranged.checkpoint_id,
        decision="approve",
        feedback="",
        reviewer="R2",
        lease_seconds=120,
        session_factory=independent_sessions,
    )
    assert ownership is not None

    use_case = _use_case(db, tenant, saver, arranged.app, independent_sessions)
    restored = await CheckpointService(checkpointer=saver).restore_checkpoint(
        thread_id=thread_id, checkpoint_id=arranged.checkpoint_id
    )
    chosen = await use_case._attempt_resume_config(
        checkpoint_service=CheckpointService(checkpointer=saver),
        graph_app=arranged.app,
        ownership=ownership,
        thread_id=thread_id,
        restored=restored,
    )
    chosen_id = chosen["configurable"]["checkpoint_id"]

    assert chosen_id != stale, "must NOT adopt the superseded attempt's descendant"
    # It is a FORK of the immutable interrupt checkpoint, so it is also not
    # the interrupt checkpoint itself (which still carries attempt 1's
    # resume write) -- but that checkpoint is its parent.
    parent = (
        await saver.aget_tuple({"configurable": {"thread_id": thread_id, "checkpoint_id": chosen_id}})
    ).parent_config["configurable"]["checkpoint_id"]
    assert parent == arranged.checkpoint_id, (
        "a takeover restarts from the immutable original interrupt checkpoint"
    )


# ── 4C: the reconciler actually makes recovery happen ────────────────────────


async def _sweep(reconciler: Any, sessions: Any, tenant: Tenant, saver: Any, app: Any) -> dict:
    """Run one real sweep against the test database and the real graph.

    The sweep's candidate scan is tenant-unscoped in production; here it runs
    through the test tenant's session, which is sufficient to prove the
    selection predicate and the recovery it drives.
    """

    @asynccontextmanager
    async def factory(tenant_id: UUID | None):
        async with sessions(tenant_id or tenant.id) as session:
            yield session

    def build_use_case(session: Any, tenant_id: UUID) -> Any:
        return ResumeWorkflowUseCase(
            review_queue_repo=SqlAlchemyReviewQueueRepository(
                session=session, tenant_id=tenant_id
            ),
            checkpoint_service=CheckpointService(checkpointer=saver),
            graph_app=app,
            claim_session_factory=sessions,
        )

    return await reconciler._sweep_async(
        session_factory=factory, use_case_factory=build_use_case
    )



async def test_reconciler_recovers_an_abandoned_operation(
    real_saver, independent_sessions, db: AsyncSession, test_user: User
) -> None:
    """Fencing makes a takeover safe; the sweep is what makes one HAPPEN.

    Without it a crashed approval sits pending forever, because the only
    thing that would retry it died with the request.
    """
    from src.core.tasks import hitl_resume_reconciler as reconciler

    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    N17_RUNS.clear()

    # A worker dies hard mid-resume: nothing releases the operation.
    class _HardDeath:
        checkpointer = saver

        async def ainvoke(self, *_a: Any, **_k: Any) -> dict:
            raise BaseException("SIGKILL")  # noqa: TRY002

    with pytest.raises(BaseException, match="SIGKILL"):
        await _use_case(db, tenant, saver, _HardDeath(), independent_sessions).execute(
            review_id=arranged.review_item_id, request=_approve()
        )

    op = await _operation_row(independent_sessions, tenant.id, arranged.review_row_id)
    assert op.phase == Phase.RUNNING.value

    # While the lease is alive the sweep must leave it alone -- taking over a
    # healthy worker is the failure mode this guards against.
    quiet = await _sweep(reconciler, independent_sessions, tenant, saver, arranged.app)
    assert quiet["scanned"] == 0, "a live lease must not be reconciled"

    # The worker is genuinely gone: age the lease past expiry.
    async with independent_sessions(tenant.id) as s:
        await s.execute(
            text(
                "UPDATE resume_operations "
                "   SET lease_expires_at = clock_timestamp() - interval '1 hour', "
                "       heartbeat_at = clock_timestamp() - interval '1 hour' "
                " WHERE review_row_id = cast(:r as uuid)"
            ),
            {"r": str(arranged.review_row_id)},
        )

    swept = await _sweep(reconciler, independent_sessions, tenant, saver, arranged.app)
    assert swept["scanned"] == 1
    assert swept["recovered"] == 1, swept

    assert len(N17_RUNS) == 1, "the sweep drove exactly one graph execution"
    assert await _counts(db, arranged.project_id) == (1, 1)
    assert await _persisted_events(db, arranged.project_id) == 1
    assert (await _reload(db, ReviewItemORM, arranged.review_row_id)).current_status == (
        ReviewStatus.APPROVED.value
    )
    assert (await _reload(db, DocumentORM, arranged.document_id)).upload_status == "analyzed"

    op = await _operation_row(independent_sessions, tenant.id, arranged.review_row_id)
    assert op.phase == Phase.FINALIZED_APPROVED.value

    # A second sweep finds nothing: a finalized operation is terminal.
    again = await _sweep(reconciler, independent_sessions, tenant, saver, arranged.app)
    assert again["scanned"] == 0
    assert len(N17_RUNS) == 1


async def test_reconciler_never_picks_up_operator_required(
    real_saver, independent_sessions, db: AsyncSession, test_user: User
) -> None:
    """OPERATOR_REQUIRED is a halt, not a slow retry."""
    from src.core.tasks import hitl_resume_reconciler as reconciler

    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    N17_RUNS.clear()

    class _Dies:
        checkpointer = saver

        async def ainvoke(self, *_a: Any, **_k: Any) -> dict:
            raise InjectedCrash("down")

    with pytest.raises(InjectedCrash):
        await _use_case(db, tenant, saver, _Dies(), independent_sessions).execute(
            review_id=arranged.review_item_id, request=_approve()
        )

    async with independent_sessions(tenant.id) as s:
        await s.execute(
            text(
                "UPDATE resume_operations SET phase = 'OPERATOR_REQUIRED', "
                "       lease_expires_at = NULL, next_attempt_at = NULL "
                " WHERE review_row_id = cast(:r as uuid)"
            ),
            {"r": str(arranged.review_row_id)},
        )

    swept = await _sweep(reconciler, independent_sessions, tenant, saver, arranged.app)
    assert swept["scanned"] == 0, "an operation halted for an operator must stay halted"
    assert N17_RUNS == []
