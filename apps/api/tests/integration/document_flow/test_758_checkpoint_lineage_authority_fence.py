"""#758 — LangGraph checkpoint lineage must be fenced across processing takeover.

The #711 authority fence protects the application's durable writes, but
AsyncPostgresSaver checkpoint writes happen OUTSIDE that database
transaction. Analysis used one shared checkpoint thread per document
(``document:{document_id}:analysis``), so a stale worker A could keep
appending checkpoints to the very thread the current owner B was using --
and ``_persist_real_checkpoint_id`` selected "latest state for the thread"
BEFORE fencing the metadata write. The fence therefore protected the write
while the value being written could belong to a stale attempt.

These tests drive the REAL production path -- ``_run_document_analysis``
acquires/fences/settles for real, a REAL compiled LangGraph app runs on
whatever thread id production hands it, and the REAL
``_persist_real_checkpoint_id`` binds the review. Nothing here hard-codes
the thread naming: the tests observe what production does, so they keep
their meaning after the lineage identity changes.

Ownership is read out of the checkpoint itself. ``critique_notes`` carries
the writing worker's name: it is a real ``ProjectState`` channel, so it
lands in ``channel_values`` and travels with the persisted checkpoint,
which makes "who wrote the checkpoint this review resolves to" an
observable fact rather than an inference from the thread string.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command
from psycopg_pool import AsyncConnectionPool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.analysis.adapters.graph import workflow
from src.analysis.adapters.graph.nodes import (
    _claim_checkpoint_lineage_for_current_attempt,
    human_interrupt_node,
    route_after_human_interrupt,
)
from src.analysis.adapters.graph.schema import ProjectState
from src.core import checkpoint_lineage as lineage
from src.core import processing_authority as pa
from src.core.tasks import ingestion_tasks
from src.documents.adapters.rag import rag_service as rag_service_module
from src.modules.hitl.adapters.checkpoint_service import CheckpointService
from src.temporal.application import project_snapshot_trigger

pytestmark = pytest.mark.asyncio


# ── harness ──────────────────────────────────────────────────────────────────


def _dsn(db: AsyncSession) -> str:
    url = db.get_bind().url
    if url.get_driver_name() != "asyncpg":
        url = url.set(drivername="postgresql+asyncpg")
    return url.render_as_string(hide_password=False)


@pytest.fixture
async def real_saver(db: AsyncSession):
    """A REAL AsyncPostgresSaver on the test database."""
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
async def worker(db: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Analysis workers on their own engine; only non-subject edges faked."""
    engine = create_async_engine(_dsn(db), pool_size=10, max_overflow=10)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def raw_session():
        async with maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    @asynccontextmanager
    async def tenant_session(tenant_id: UUID):
        async with maker() as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant', :t, true)"), {"t": str(tenant_id)}
            )
            yield session
            await session.commit()

    async def _no_init() -> None:
        return None

    async def _no_heartbeat(**_: Any) -> None:
        # A stalled worker is frozen: it emits no heartbeat either.
        await asyncio.Event().wait()

    async def _fake_embed(texts: list[str]) -> list[list[float]]:
        return [[0.001 * (i + 1)] * 1536 for i, _ in enumerate(texts)]

    monkeypatch.setattr(ingestion_tasks, "get_raw_session", raw_session)
    monkeypatch.setattr(ingestion_tasks, "init_db", _no_init)
    monkeypatch.setattr(ingestion_tasks, "_document_processing_heartbeat_loop", _no_heartbeat)
    monkeypatch.setattr(rag_service_module, "_embed_texts", _fake_embed)
    monkeypatch.setattr(project_snapshot_trigger, "get_session_with_tenant", tenant_session)
    monkeypatch.setattr(project_snapshot_trigger, "enqueue_project_snapshot", lambda **_: None)

    class _Worker:
        pass

    w = _Worker()
    w.maker = maker
    w.tenant_session = tenant_session
    try:
        yield w
    finally:
        await engine.dispose()


async def _seed_analysable(db: AsyncSession, test_user: Any) -> Any:
    """A parsed document with a chunk: the state analysis starts from.

    Seeded through the ORM models so the row satisfies every column the
    application itself requires, rather than a hand-maintained INSERT.
    """
    from datetime import datetime

    from src.documents.adapters.persistence.models import DocumentORM
    from src.projects.adapters.persistence.models import ProjectORM

    tenant = test_user.tenant_id
    project = ProjectORM(
        id=uuid4(),
        tenant_id=tenant,
        name="p758",
        code=f"P-{uuid4().hex[:8]}",
        start_date=datetime.now(),
    )
    db.add(project)
    await db.commit()

    document = DocumentORM(
        id=uuid4(),
        tenant_id=tenant,
        project_id=project.id,
        document_type="contract",
        filename="c758.pdf",
        upload_status="parsed_pending_analysis",
        document_metadata={
            "parsed_text": "Clause 1: the contractor shall deliver the works."
        },
    )
    db.add(document)
    await db.commit()

    await db.execute(
        text(
            "INSERT INTO document_chunks (id, tenant_id, document_id, project_id, content, "
            "embedding, metadata) VALUES (:id, :t, :d, :p, 'chunk', CAST(:e AS vector), '{}')"
        ),
        {
            "id": uuid4(),
            "t": tenant,
            "d": document.id,
            "p": project.id,
            "e": "[" + ",".join(["0.001"] * 1536) + "]",
        },
    )
    await db.commit()
    # Plain ids: the session expires ORM instances on commit, and a later
    # synchronous attribute touch would raise MissingGreenlet.
    return SimpleNamespace(id=document.id, project_id=project.id)


# ── a real compiled graph that really interrupts ─────────────────────────────


async def _entry(state: ProjectState) -> ProjectState:
    state["human_approval_required"] = True
    return state


#: Documents whose graph ran past the HITL gate. Empty until a real resume
#: consumes the interrupt, which is what makes "the approval resumed THIS
#: lineage" an observable fact rather than an assumption.
DOWNSTREAM_RUNS: list[str] = []


async def _downstream(state: ProjectState) -> ProjectState:
    DOWNSTREAM_RUNS.append(str(state.get("critique_notes")))
    return state


def _build_interrupting_graph(saver: AsyncPostgresSaver):
    """entry -> REAL human_interrupt_node (creates the ReviewItem) -> interrupt."""
    g = StateGraph(ProjectState)
    g.add_node("entry", _entry)
    g.add_node("human_interrupt", human_interrupt_node)
    g.add_node("downstream", _downstream)
    g.set_entry_point("entry")
    g.add_edge("entry", "human_interrupt")
    g.add_conditional_edges(
        "human_interrupt",
        route_after_human_interrupt,
        {"enrichment_dispatch": "downstream", "terminated": END},
    )
    g.add_edge("downstream", END)
    return g.compile(checkpointer=saver)


class _RealGraphWorker:
    """Orchestrator that runs a REAL LangGraph app on production's thread id.

    Mirrors ``run_orchestration``: invoke, then attach the real checkpoint id
    through the REAL ``_persist_real_checkpoint_id``. It never chooses a
    thread id of its own -- whatever production computes is what gets used,
    which is precisely the identity under test.
    """

    def __init__(
        self,
        name: str,
        saver: AsyncPostgresSaver,
        register: Any,
        *,
        entered: asyncio.Event | None = None,
        release: asyncio.Event | None = None,
        bind: bool = True,
        fail_bind: bool = False,
    ) -> None:
        self.name = name
        self.saver = saver
        self.register = register
        self.entered = entered
        self.release = release
        self.bind = bind
        self.fail_bind = fail_bind
        self.thread_id: str | None = None
        self.checkpoint_ids: list[str] = []
        self.app: Any = None
        self.config: dict[str, Any] | None = None

    async def run(self, state: dict[str, Any], *, thread_id: str) -> dict[str, Any]:
        self.thread_id = thread_id
        self.register(thread_id)
        self.app = _build_interrupting_graph(self.saver)
        self.config = {"configurable": {"thread_id": thread_id}}

        if self.entered is not None:
            self.entered.set()
        if self.release is not None:
            await self.release.wait()

        # critique_notes is a real ProjectState channel, so the writer's name
        # is persisted INSIDE the checkpoint and travels with it.
        run_state = {**state, "critique_notes": self.name}
        result = await self.app.ainvoke(run_state, self.config)
        self.checkpoint_ids.append(await self._latest_checkpoint_id())

        if result.get("human_approval_required") and self.bind:
            # fail_bind drives the REAL helper through its REAL failure path.
            # Every failure mode it can hit -- checkpoint capture, the tenant
            # session, find_active_review, the update/commit -- converges on
            # the same `except Exception: log; return`, so a raising
            # aget_state reproduces all of them observably.
            app: Any = self.app
            if self.fail_bind:

                class _CaptureFails:
                    checkpointer = self.saver

                    async def aget_state(self, _config: dict[str, Any]) -> Any:
                        raise RuntimeError("injected: checkpoint binding failed")

                app = _CaptureFails()
            await workflow._persist_real_checkpoint_id(
                app,
                self.config,
                thread_id=thread_id,
                document_id=state.get("document_id"),
                tenant_id=state.get("tenant_id"),
            )
        return {"analysis_id": None, "human_approval_required": True}

    async def _latest_checkpoint_id(self) -> str:
        snapshot = await self.app.aget_state(self.config)
        return str((snapshot.config or {})["configurable"]["checkpoint_id"])

    async def append_stale_checkpoint(self) -> str:
        """The stale worker appends a LATER checkpoint to its own lineage.

        A worker that lost its lease keeps running: LangGraph has no fence,
        so this write always succeeds. What must be impossible is for it to
        become selectable as the current lineage.
        """
        assert self.app is not None and self.config is not None
        await self.app.aupdate_state(self.config, {"critique_notes": self.name})
        appended = await self._latest_checkpoint_id()
        self.checkpoint_ids.append(appended)
        return appended


# ── observation helpers ──────────────────────────────────────────────────────


async def _review(db: AsyncSession, document_id: UUID) -> Any:
    """The review rows for this document's analysis gate.

    thread_id/checkpoint_id are first-class COLUMNS: update_review_item pops
    them out of the domain metadata dict and _to_domain projects them back,
    so the columns -- not review_metadata -- are where the bound lineage
    actually lives.
    """
    return (
        await db.execute(
            text(
                "SELECT id, thread_id, checkpoint_id, review_metadata, "
                "       current_status::text AS current_status "
                "  FROM review_items "
                " WHERE document_id = :d AND review_type = 'analysis_critique' "
                " ORDER BY created_at"
            ),
            {"d": document_id},
        )
    ).all()


async def _owner_of(saver: AsyncPostgresSaver, thread_id: str, checkpoint_id: str | None) -> str:
    """Which worker wrote the checkpoint this (thread, id) resolves to."""
    restored = await CheckpointService(checkpointer=saver).restore_checkpoint(
        thread_id=thread_id, checkpoint_id=checkpoint_id
    )
    assert restored is not None, f"no checkpoint for {thread_id}/{checkpoint_id}"
    return str(restored.checkpoint.get("channel_values", {}).get("critique_notes"))


async def _op(db: AsyncSession, document_id: UUID) -> Any:
    return (
        await db.execute(
            text("SELECT * FROM document_processing_operations WHERE document_id = :d"),
            {"d": document_id},
        )
    ).first()


async def _expire_lease() -> None:
    await asyncio.sleep(1.4)


# ── the canonical #758 race ──────────────────────────────────────────────────


async def test_stale_attempt_checkpoint_is_never_bound_or_resumed_after_takeover(
    db: AsyncSession,
    test_user: Any,
    worker: Any,
    real_saver: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A owns N and checkpoints; B takes over at N+1; stale A checkpoints again.

    The current review must resolve to a B-owned checkpoint, and A's later
    write must be unreachable -- both by explicit id and through the
    thread-only "latest" fallback.
    """
    saver, register = real_saver
    document = await _seed_analysable(db, test_user)
    tenant = test_user.tenant_id

    a_entered, a_release = asyncio.Event(), asyncio.Event()
    a = _RealGraphWorker("A", saver, register, entered=a_entered, release=a_release)
    b = _RealGraphWorker("B", saver, register)

    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 1)
    task_a = asyncio.create_task(
        ingestion_tasks._run_document_analysis(
            tenant_id=tenant, document_id=document.id, orchestrator=a
        )
    )
    await asyncio.wait_for(a_entered.wait(), 10)
    fence_a = int((await _op(db, document.id)).fencing_token)

    # A completes its graph and binds its own checkpoint: it got that far
    # before stalling, which is exactly why a naive "already bound" guard
    # leaves the review pointing at a stale lineage.
    a_release.set()
    await asyncio.wait_for(task_a, 30)
    assert a.checkpoint_ids, "A must have written a real checkpoint"

    # The lease genuinely expires (PostgreSQL clock), then B takes over.
    await _expire_lease()
    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 60)
    result_b = await ingestion_tasks._run_document_analysis(
        tenant_id=tenant, document_id=document.id, orchestrator=b
    )
    # A HITL interrupt is a legitimate, durably-checkpointed pause.
    assert result_b["status"] == "waiting_for_review", result_b
    op_b = await _op(db, document.id)
    assert int(op_b.fencing_token) == fence_a + 1, "B must own a newer fence"
    assert b.checkpoint_ids, "B must have written a real checkpoint"

    # The stale worker wakes up and appends a LATER checkpoint.
    stale = await a.append_stale_checkpoint()

    rows = await _review(db, document.id)
    assert len(rows) == 1, f"takeover must not duplicate the review: {rows}"
    bound_thread = rows[0].thread_id
    bound_checkpoint = rows[0].checkpoint_id
    assert bound_thread and bound_checkpoint, f"review must bind a lineage: {rows[0]}"

    # 1. The binding belongs to the CURRENT owner, not the stale attempt.
    assert bound_checkpoint not in a.checkpoint_ids, (
        "the current review is bound to a checkpoint written by the STALE attempt "
        f"(bound={bound_checkpoint}, A wrote {a.checkpoint_ids})"
    )
    assert bound_checkpoint in b.checkpoint_ids, (
        f"expected a B-owned checkpoint, got {bound_checkpoint}"
    )
    assert await _owner_of(saver, bound_thread, bound_checkpoint) == "B"

    # 2. Resolving the recorded lineage WITHOUT an explicit checkpoint id --
    #    the deliberate thread-only fallback -- must not cross into A.
    assert await _owner_of(saver, bound_thread, None) == "B", (
        "the thread-only latest lookup crossed a processing authority boundary "
        f"and resolved the stale attempt's checkpoint {stale}"
    )

    # 3. A's stale append must not be reachable on the current lineage at all.
    assert stale not in b.checkpoint_ids
    restored_stale = await CheckpointService(checkpointer=saver).restore_checkpoint(
        thread_id=bound_thread, checkpoint_id=stale
    )
    assert restored_stale is None, (
        "the stale attempt's checkpoint is addressable on the CURRENT lineage"
    )


async def test_takeover_binds_b_even_when_a_crashed_before_attaching_metadata(
    db: AsyncSession,
    test_user: Any,
    worker: Any,
    real_saver: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Crash window: A checkpoints and creates the review, then dies before binding.

    human_interrupt_node records ITS OWN thread id on the review at creation,
    so after a takeover the review already names the superseded attempt's
    lineage even though no checkpoint was ever bound. B must overwrite it,
    not merely fill in the missing checkpoint id.
    """
    saver, register = real_saver
    document = await _seed_analysable(db, test_user)
    tenant = test_user.tenant_id

    a = _RealGraphWorker("A", saver, register, bind=False)
    b = _RealGraphWorker("B", saver, register)

    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 1)
    await ingestion_tasks._run_document_analysis(
        tenant_id=tenant, document_id=document.id, orchestrator=a
    )
    rows = await _review(db, document.id)
    assert len(rows) == 1
    assert rows[0].thread_id == a.thread_id, "the review was created naming A's lineage"
    assert rows[0].checkpoint_id is None, "A never attached a checkpoint"

    await _expire_lease()
    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 60)
    await ingestion_tasks._run_document_analysis(
        tenant_id=tenant, document_id=document.id, orchestrator=b
    )

    rows = await _review(db, document.id)
    assert len(rows) == 1, "takeover must not duplicate the review"
    assert rows[0].thread_id == b.thread_id, (
        "the review still names the crashed attempt's thread; a resume would "
        "replay a lineage the current owner does not own"
    )
    assert rows[0].checkpoint_id in b.checkpoint_ids
    assert await _owner_of(saver, rows[0].thread_id, rows[0].checkpoint_id) == "B"
    assert await _owner_of(saver, rows[0].thread_id, None) == "B"


async def test_no_takeover_resume_replays_the_exact_bound_checkpoint(
    db: AsyncSession,
    test_user: Any,
    worker: Any,
    real_saver: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ordinary path: one owner, and HITL resumes its exact checkpoint.

    Proves the fix did not disturb what #649/#650 guarantees -- the persisted
    tuple is replayed verbatim and the interrupt is genuinely consumed.
    """
    saver, register = real_saver
    document = await _seed_analysable(db, test_user)
    tenant = test_user.tenant_id
    DOWNSTREAM_RUNS.clear()

    a = _RealGraphWorker("A", saver, register)
    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 60)
    await ingestion_tasks._run_document_analysis(
        tenant_id=tenant, document_id=document.id, orchestrator=a
    )

    rows = await _review(db, document.id)
    bound_thread, bound_checkpoint = rows[0].thread_id, rows[0].checkpoint_id
    assert bound_thread == a.thread_id and bound_checkpoint in a.checkpoint_ids
    assert DOWNSTREAM_RUNS == [], "the graph must still be paused at the gate"

    # The EXACT persisted tuple, replayed verbatim.
    restored = await CheckpointService(checkpointer=saver).restore_checkpoint(
        thread_id=bound_thread, checkpoint_id=bound_checkpoint
    )
    assert restored is not None
    assert restored.checkpoint_id == bound_checkpoint, "exact checkpoint identity"

    resumed = await a.app.ainvoke(
        Command(resume={"decision": "approve", "feedback": ""}), restored.config
    )
    assert "__interrupt__" not in resumed, "the resume must consume the interrupt"
    assert DOWNSTREAM_RUNS == ["A"], "approval resumed A's own lineage"


async def test_approval_after_takeover_resumes_the_b_owned_checkpoint(
    db: AsyncSession,
    test_user: Any,
    worker: Any,
    real_saver: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Approval after a takeover must replay B's lineage, never the stale one."""
    saver, register = real_saver
    document = await _seed_analysable(db, test_user)
    tenant = test_user.tenant_id
    DOWNSTREAM_RUNS.clear()

    a = _RealGraphWorker("A", saver, register)
    b = _RealGraphWorker("B", saver, register)

    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 1)
    await ingestion_tasks._run_document_analysis(
        tenant_id=tenant, document_id=document.id, orchestrator=a
    )
    await _expire_lease()
    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 60)
    await ingestion_tasks._run_document_analysis(
        tenant_id=tenant, document_id=document.id, orchestrator=b
    )
    await a.append_stale_checkpoint()

    rows = await _review(db, document.id)
    restored = await CheckpointService(checkpointer=saver).restore_checkpoint(
        thread_id=rows[0].thread_id, checkpoint_id=rows[0].checkpoint_id
    )
    assert restored is not None
    resumed = await b.app.ainvoke(
        Command(resume={"decision": "approve", "feedback": ""}), restored.config
    )
    assert "__interrupt__" not in resumed
    assert DOWNSTREAM_RUNS == ["B"], (
        f"approval replayed the wrong attempt's lineage: {DOWNSTREAM_RUNS}"
    )


async def test_thread_only_lookup_cannot_cross_a_processing_authority_boundary(
    db: AsyncSession,
    test_user: Any,
    worker: Any,
    real_saver: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Absence of a checkpoint id must not silently reach another attempt.

    This is structural, not a filter: each attempt owns its own thread, so
    "latest on the thread" has only one attempt's checkpoints to choose from.
    """
    saver, register = real_saver
    document = await _seed_analysable(db, test_user)
    tenant = test_user.tenant_id

    a = _RealGraphWorker("A", saver, register)
    b = _RealGraphWorker("B", saver, register)

    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 1)
    await ingestion_tasks._run_document_analysis(
        tenant_id=tenant, document_id=document.id, orchestrator=a
    )
    await _expire_lease()
    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 60)
    await ingestion_tasks._run_document_analysis(
        tenant_id=tenant, document_id=document.id, orchestrator=b
    )
    # A keeps writing after losing authority -- repeatedly.
    await a.append_stale_checkpoint()
    await a.append_stale_checkpoint()

    assert a.thread_id != b.thread_id, "each attempt must own its own lineage"
    assert lineage.is_authority_scoped_analysis_thread(a.thread_id)
    assert lineage.is_authority_scoped_analysis_thread(b.thread_id)

    # Latest-on-thread, with no checkpoint id at all, stays inside one attempt.
    assert await _owner_of(saver, a.thread_id, None) == "A"
    assert await _owner_of(saver, b.thread_id, None) == "B"

    # And no checkpoint of A's is addressable on B's lineage.
    service = CheckpointService(checkpointer=saver)
    for stale in a.checkpoint_ids:
        assert await service.restore_checkpoint(
            thread_id=b.thread_id, checkpoint_id=stale
        ) is None, f"A's checkpoint {stale} is reachable on B's lineage"


async def test_redelivered_recovery_message_adds_no_second_lineage(
    db: AsyncSession,
    test_user: Any,
    worker: Any,
    real_saver: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redelivery of a recovery message must not fork the lineage.

    The grant carried in the message is adopted exactly once, so a duplicate
    delivery is refused outright: no second checkpoint thread, no second
    review, and the binding still names the lineage the first delivery built.
    Together with the deterministic identity proven in
    ``test_lineage_identity_is_deterministic_and_attempt_unique``, this is
    what keeps an ordinary retry from orphaning its own checkpoint.
    """
    saver, register = real_saver
    document = await _seed_analysable(db, test_user)
    tenant = test_user.tenant_id
    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 60)

    # A recovery sweep claims an exact grant; the message carries it.
    async with worker.tenant_session(tenant) as s:
        claimed = await pa.claim_for_recovery(
            s,
            tenant_id=tenant,
            document_id=document.id,
            stage=pa.ProcessingStage.ANALYSIS,
            revision_id=None,
        )
    # claim_for_recovery returns the grant itself, not an AcquireResult.
    assert claimed is not None
    message = claimed.to_message()

    first = _RealGraphWorker("A", saver, register)
    await ingestion_tasks._run_document_analysis(
        tenant_id=tenant, document_id=document.id, orchestrator=first, authority=message
    )
    assert first.thread_id is not None
    expected_thread = first.thread_id

    second = _RealGraphWorker("A2", saver, register)
    redelivered = await ingestion_tasks._run_document_analysis(
        tenant_id=tenant, document_id=document.id, orchestrator=second, authority=message
    )

    assert second.thread_id is None, (
        f"a redelivered grant must not run the graph again: {redelivered}"
    )
    rows = await _review(db, document.id)
    assert len(rows) == 1, f"redelivery must not duplicate the review: {rows}"
    assert rows[0].thread_id == expected_thread
    assert await _owner_of(saver, rows[0].thread_id, rows[0].checkpoint_id) == "A"


async def test_reprocess_generation_starts_an_isolated_lineage(
    db: AsyncSession,
    test_user: Any,
    worker: Any,
    real_saver: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A new generation is a new lineage; the old one cannot be selected."""
    saver, register = real_saver
    document = await _seed_analysable(db, test_user)
    tenant = test_user.tenant_id
    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 60)

    first = _RealGraphWorker("A", saver, register)
    await ingestion_tasks._run_document_analysis(
        tenant_id=tenant, document_id=document.id, orchestrator=first
    )
    rows = await _review(db, document.id)
    assert rows[0].thread_id == first.thread_id

    # Reprocess: a new generation, and analysis becomes claimable again.
    async with worker.tenant_session(tenant) as s:
        await pa.begin_generation(s, tenant_id=tenant, document_id=document.id, revision_id=None)
    async with worker.tenant_session(tenant) as s:
        await s.execute(
            text(
                "UPDATE document_processing_operations SET stage = 'ANALYSIS', phase = 'PENDING' "
                " WHERE document_id = :d"
            ),
            {"d": document.id},
        )

    second = _RealGraphWorker("C", saver, register)
    await ingestion_tasks._run_document_analysis(
        tenant_id=tenant, document_id=document.id, orchestrator=second
    )

    assert second.thread_id != first.thread_id, "a new generation must not reuse the lineage"
    assert await _owner_of(saver, first.thread_id, None) == "A"
    assert await _owner_of(saver, second.thread_id, None) == "C"
    service = CheckpointService(checkpointer=saver)
    for old in first.checkpoint_ids:
        assert await service.restore_checkpoint(
            thread_id=second.thread_id, checkpoint_id=old
        ) is None


async def test_direct_user_resume_is_not_contaminated_by_ambient_authority(
    db: AsyncSession,
    test_user: Any,
    worker: Any,
    real_saver: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resume replays the RECORDED lineage, never one recomputed from context.

    A HITL resume runs outside a processing worker, so no authority is bound;
    but even with one ambiently bound (a worker-hosted resume), the recorded
    tuple is what gets replayed.
    """
    saver, register = real_saver
    document = await _seed_analysable(db, test_user)
    tenant = test_user.tenant_id
    DOWNSTREAM_RUNS.clear()
    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 60)

    a = _RealGraphWorker("A", saver, register)
    await ingestion_tasks._run_document_analysis(
        tenant_id=tenant, document_id=document.id, orchestrator=a
    )
    rows = await _review(db, document.id)
    bound_thread, bound_checkpoint = rows[0].thread_id, rows[0].checkpoint_id

    # No ambient authority: what a real HITL resume sees.
    assert pa.current_authority() is None
    assert lineage.analysis_thread_id(
        document_id=document.id, authority=None
    ) == lineage.legacy_shared_analysis_thread_id(document.id)

    # A DIFFERENT authority bound ambiently must not redirect the resume.
    async with worker.tenant_session(tenant) as s:
        other = await pa.acquire(
            s, tenant_id=tenant, document_id=document.id, stage=pa.ProcessingStage.ANALYSIS
        )
    foreign = other.authority
    assert foreign is not None and foreign.fencing_token > 0
    with pa.bound_authority(foreign):
        restored = await CheckpointService(checkpointer=saver).restore_checkpoint(
            thread_id=bound_thread, checkpoint_id=bound_checkpoint
        )
        assert restored is not None
        assert restored.checkpoint_id == bound_checkpoint
        resumed = await a.app.ainvoke(
            Command(resume={"decision": "approve", "feedback": ""}), restored.config
        )
    assert "__interrupt__" not in resumed
    assert DOWNSTREAM_RUNS == ["A"], "the recorded lineage must win"


def test_lineage_identity_is_deterministic_and_attempt_unique() -> None:
    """Same attempt -> same thread; any different attempt -> different thread."""
    document_id = uuid4()

    def authority(*, generation: int, fence: int) -> pa.ProcessingAuthority:
        return pa.ProcessingAuthority(
            tenant_id=uuid4(),
            document_id=document_id,
            revision_id=None,
            generation=generation,
            stage=pa.ProcessingStage.ANALYSIS,
            attempt_id=uuid4(),
            owner_token=uuid4(),
            fencing_token=fence,
        )

    a = authority(generation=1, fence=7)
    same = lineage.analysis_thread_id(document_id=document_id, authority=a)
    assert same == lineage.analysis_thread_id(document_id=document_id, authority=a)
    assert lineage.is_authority_scoped_analysis_thread(same)
    assert not lineage.is_legacy_shared_analysis_thread(same)
    assert len(same) <= 255, "must fit review_items.thread_id"

    takeover = lineage.analysis_thread_id(
        document_id=document_id, authority=authority(generation=1, fence=8)
    )
    reprocess = lineage.analysis_thread_id(
        document_id=document_id, authority=authority(generation=2, fence=9)
    )
    assert len({same, takeover, reprocess}) == 3

    legacy = lineage.analysis_thread_id(document_id=document_id, authority=None)
    assert lineage.is_legacy_shared_analysis_thread(legacy)
    assert not lineage.is_authority_scoped_analysis_thread(legacy)


# ── the rebind-failure window (#758 principal review) ────────────────────────


async def test_rebind_failure_must_not_leave_the_review_resumable_through_a(
    db: AsyncSession,
    test_user: Any,
    worker: Any,
    real_saver: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B takes over, then FAILS to attach its lineage. The review must not stay A's.

    `route_for_review` deduplicates on the document, so B's interrupt adopts
    the review A created -- still carrying A's thread and checkpoint. If B's
    binding then fails, the only active review remains resumable through a
    SUPERSEDED lineage, and a later HITL approval runs outside processing
    authority, so #711 cannot repair it at approval time.

    Either the attempt fails closed (retryable, nothing declared ready) or
    the review is bound to B's lineage before the interrupt is actionable.
    Reporting `waiting_for_review` while the review still points at A is the
    defect.
    """
    saver, register = real_saver
    document = await _seed_analysable(db, test_user)
    tenant = test_user.tenant_id

    a = _RealGraphWorker("A", saver, register)
    b = _RealGraphWorker("B", saver, register, fail_bind=True)

    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 1)
    await ingestion_tasks._run_document_analysis(
        tenant_id=tenant, document_id=document.id, orchestrator=a
    )
    rows = await _review(db, document.id)
    assert rows[0].thread_id == a.thread_id
    assert rows[0].checkpoint_id in a.checkpoint_ids, "A really did bind its own lineage"

    await _expire_lease()
    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 60)
    result_b = await ingestion_tasks._run_document_analysis(
        tenant_id=tenant, document_id=document.id, orchestrator=b
    )
    assert b.thread_id is not None and b.thread_id != a.thread_id

    rows = await _review(db, document.id)
    assert len(rows) == 1, f"takeover must not duplicate the review: {rows}"
    bound_thread, bound_checkpoint = rows[0].thread_id, rows[0].checkpoint_id

    # The review must never remain addressable through the superseded lineage.
    assert bound_thread != a.thread_id, (
        "the only active review still names the SUPERSEDED attempt's lineage after "
        f"B's binding failed (thread={bound_thread}, checkpoint={bound_checkpoint}); "
        f"status={result_b['status']}"
    )
    assert bound_checkpoint not in a.checkpoint_ids

    if result_b["status"] == "waiting_for_review":
        # Declared ready: the lineage must be B-pure, with or without an
        # exact checkpoint id (capture stays best-effort by design).
        assert bound_thread == b.thread_id
        assert await _owner_of(saver, bound_thread, bound_checkpoint) == "B"
    else:
        # Failed closed: nothing was declared ready, and the attempt is
        # retryable rather than silently reporting a stale review.
        assert result_b["status"] != "completed", result_b


async def test_rebind_failure_leaves_a_resumable_b_pure_lineage(
    db: AsyncSession,
    test_user: Any,
    worker: Any,
    real_saver: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After a failed checkpoint capture, thread-only resume must still be B-pure.

    checkpoint_id capture is deliberately best-effort and must stay that way
    (making it mandatory would break legacy reviews that have none). What must
    hold is that the thread the review names belongs to the current attempt,
    so the thread-only fallback resolves the current owner's checkpoint.
    """
    saver, register = real_saver
    document = await _seed_analysable(db, test_user)
    tenant = test_user.tenant_id
    DOWNSTREAM_RUNS.clear()

    a = _RealGraphWorker("A", saver, register)
    b = _RealGraphWorker("B", saver, register, fail_bind=True)

    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 1)
    await ingestion_tasks._run_document_analysis(
        tenant_id=tenant, document_id=document.id, orchestrator=a
    )
    await _expire_lease()
    monkeypatch.setattr(pa, "LEASE_TTL_SECONDS", 60)
    result_b = await ingestion_tasks._run_document_analysis(
        tenant_id=tenant, document_id=document.id, orchestrator=b
    )
    if result_b["status"] != "waiting_for_review":
        pytest.skip("attempt failed closed; the resumability contract is the other test")

    # A keeps writing to its own lineage after losing authority.
    await a.append_stale_checkpoint()

    rows = await _review(db, document.id)
    restored = await CheckpointService(checkpointer=saver).restore_checkpoint(
        thread_id=rows[0].thread_id, checkpoint_id=rows[0].checkpoint_id
    )
    assert restored is not None, "the review must remain resumable"
    resumed = await b.app.ainvoke(
        Command(resume={"decision": "approve", "feedback": ""}), restored.config
    )
    assert "__interrupt__" not in resumed
    assert DOWNSTREAM_RUNS == ["B"], (
        f"approval replayed the superseded attempt's lineage: {DOWNSTREAM_RUNS}"
    )


# ── legacy lineage compatibility (verified production shape) ─────────────────


async def test_legacy_uuid_review_still_resumes_and_is_never_claimed(
    db: AsyncSession,
    test_user: Any,
    worker: Any,
    real_saver: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production has pending reviews on legacy UUID threads with NO checkpoint id.

    Read-only production inspection found 6 pending analysis_critique reviews,
    all with checkpoint_id NULL, all on 36-character UUID thread ids (not
    `document:{id}:analysis`), all with checkpoint records. They resume today
    purely through the thread-only fallback, so #758 must not touch them:

    * a legacy thread is not authority-scoped, so the lineage claim skips it;
    * a direct resume runs with no ambient authority, so the claim skips it
      again even if it were;
    * and it must still restore and resume with no checkpoint id at all.
    """
    saver, register = real_saver
    document = await _seed_analysable(db, test_user)
    tenant = test_user.tenant_id
    DOWNSTREAM_RUNS.clear()

    # A legacy lineage: a bare UUID thread, exactly production's shape.
    legacy_thread = str(uuid4())
    register(legacy_thread)
    assert len(legacy_thread) == 36
    assert not lineage.is_authority_scoped_analysis_thread(legacy_thread)
    assert not lineage.is_legacy_shared_analysis_thread(legacy_thread)

    app = _build_interrupting_graph(saver)
    legacy_state = {
        "document_text": "",
        "project_id": str(document.project_id),
        "document_id": str(document.id),
        "tenant_id": str(tenant),
        "thread_id": legacy_thread,
        "doc_type": "contract",
        "critique_notes": "LEGACY",
        "messages": [],
        "extracted_risks": [],
        "extracted_wbs": [],
        "retry_count": 0,
        "confidence_score": 0.0,
        "human_feedback": "",
        "human_approval_required": False,
        "analysis_id": None,
        "node_results": [],
    }
    # No ambient authority: this is how a legacy row came to exist and how a
    # direct resume reaches this node.
    assert pa.current_authority() is None
    config = {"configurable": {"thread_id": legacy_thread}}
    await app.ainvoke(legacy_state, config)

    rows = await _review(db, document.id)
    assert len(rows) == 1
    assert rows[0].thread_id == legacy_thread
    assert rows[0].checkpoint_id is None, "production's shape: no checkpoint id"

    # Even with an authority ambiently bound, a legacy thread is never claimed.
    async with worker.tenant_session(tenant) as s:
        granted = await pa.acquire(
            s, tenant_id=tenant, document_id=document.id, stage=pa.ProcessingStage.ANALYSIS
        )
    assert granted.authority is not None
    with pa.bound_authority(granted.authority):
        await _claim_checkpoint_lineage_for_current_attempt(legacy_state)  # type: ignore[arg-type]
    rows = await _review(db, document.id)
    assert rows[0].thread_id == legacy_thread, "a legacy lineage must never be rebound"
    assert rows[0].checkpoint_id is None

    # And it still resumes with no checkpoint id: thread-only fallback.
    restored = await CheckpointService(checkpointer=saver).restore_checkpoint(
        thread_id=rows[0].thread_id, checkpoint_id=rows[0].checkpoint_id
    )
    assert restored is not None, "legacy reviews must remain restorable"
    resumed = await app.ainvoke(
        Command(resume={"decision": "approve", "feedback": ""}), restored.config
    )
    assert "__interrupt__" not in resumed
    assert DOWNSTREAM_RUNS == ["LEGACY"], "the legacy lineage must still resume"
