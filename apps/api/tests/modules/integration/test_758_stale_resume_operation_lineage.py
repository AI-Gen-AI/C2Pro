"""#758 P1-3: a resume operation left behind on a superseded lineage.

Rebinding a review's checkpoint lineage moves the REVIEW. It does not touch
the ``resume_operations`` row a human decision (or an earlier recovery
attempt) already created, and the reconciler selects those rows by
``review_row_id`` -- which survives a rebind untouched. So an operation
created for lineage A stayed a perfectly valid recovery candidate after B
took the document over, and its phase decided what it would then do:

* ``FAILED_RETRYABLE``  -> resume the graph on A's checkpoint;
* ``N17_DURABLE``       -> continue A's run and finalize it;
* ``GRAPH_COMPLETED``   -> finalize A's analysis against the CURRENT review
  and document.

The resume fence cannot see any of this: a processing takeover advances no
resume fencing token, so ownership of the operation stays perfectly valid
while the lineage under it has become history.

These tests drive the real thing: a real ``AsyncPostgresSaver``, a real
compiled graph over the real ``human_interrupt_node`` and the real N17 node,
real #711 authority grants, the real ``claim_review_lineage_for_current_attempt``
for the rebind, and the real reconciler sweep. Each phase is reached by
running the production transition that produces it, never by writing a phase
string into the row.

What must hold in every case: nothing resumes, nothing finalizes, and the
durable record survives intact -- historical, and non-actionable. Case D is
the control: with no rebind, recovery still works, so the guard is a lineage
comparison and not a blanket halt.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
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
from src.analysis.adapters.graph.review_lineage import (
    claim_review_lineage_for_current_attempt,
)
from src.analysis.adapters.graph.schema import ProjectState
from src.analysis.adapters.persistence.models import Analysis
from src.analysis.application.persist_resume_analysis import (
    ResumeProvenance,
    persist_resume_analysis_atomically,
)
from src.core import checkpoint_lineage, resume_lineage
from src.core import processing_authority as pa
from src.core.auth.models import User
from src.core.tasks import hitl_resume_reconciler as reconciler
from src.documents.adapters.persistence.models import DocumentORM
from src.modules.hitl.adapters.checkpoint_service import CheckpointService
from src.modules.hitl.adapters.persistence import resume_ownership
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.adapters.persistence.repository import (
    SqlAlchemyReviewQueueRepository,
)
from src.modules.hitl.adapters.persistence.resume_ownership import OwnershipError, Phase
from src.modules.hitl.adapters.persistence.resume_recovery import (
    RecoveryOutcome,
    ResumeRecoveryRequest,
)
from src.modules.hitl.application.resume_workflow_use_case import ResumeWorkflowUseCase
from src.projects.adapters.persistence.models import ProjectORM
from src.temporal.adapters.persistence.models import ProjectEventORM

pytestmark = pytest.mark.asyncio

#: Documents whose graph was resumed past the HITL gate. A stale-lineage
#: operation must never add to this, which makes "no graph resume" observable
#: rather than inferred.
N17_RUNS: list[str] = []


# ── real infrastructure ──────────────────────────────────────────────────────


def _dsn(db: AsyncSession) -> str:
    url = db.get_bind().url
    if url.get_driver_name() != "asyncpg":
        url = url.set(drivername="postgresql+asyncpg")
    return url.render_as_string(hide_password=False)


@pytest.fixture
async def real_saver(db: AsyncSession):
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
async def sessions(db: AsyncSession):
    """A session factory on its OWN engine, so CAS is arbitrated by PostgreSQL."""
    engine = create_async_engine(_dsn(db), pool_size=10, max_overflow=10)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def factory(tenant_id: UUID | None):
        async with maker() as session:
            if tenant_id is not None:
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


@pytest.fixture(autouse=True)
async def _clean_recovery_discovery_rows(db: AsyncSession, test_user: User):
    """The #711 discovery index is migration-owned and survives the schema reset."""
    tenant_id = test_user.tenant_id
    yield
    await db.rollback()
    await db.execute(
        text("DELETE FROM system_recovery.document_work_index WHERE tenant_id = :t"),
        {"t": tenant_id},
    )
    await db.commit()


# ── the real graph over the real production nodes ────────────────────────────


async def _entry(state: ProjectState) -> ProjectState:
    return state


async def _counting_n17(state: ProjectState) -> ProjectState:
    N17_RUNS.append(str(state.get("document_id")))
    return await save_to_db_node(state)


def _build_real_graph(saver: AsyncPostgresSaver) -> Any:
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


def _initial_state(document_id: UUID, project_id: UUID, tenant_id: UUID, thread_id: str):
    return {
        "project_id": str(project_id),
        "document_id": str(document_id),
        "tenant_id": str(tenant_id),
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
                "proof_marker": "issue-758-p1-3",
            }
        },
        "node_results": [],
    }


@dataclass(frozen=True)
class _Arranged:
    document_id: UUID
    project_id: UUID
    app: Any
    review_row_id: UUID
    thread_a: str
    checkpoint_id: str
    authority_a: pa.ProcessingAuthority


async def _arrange(
    db: AsyncSession, tenant_id: UUID, saver: AsyncPostgresSaver, register: Any
) -> _Arranged:
    """A document paused at the HITL gate, owned by processing attempt A.

    The thread comes from the REAL authority-scoped naming, so the rebind
    below is a genuine lineage change rather than a renamed string, and the
    review is stamped by the real N13 claim.
    """
    project_id, document_id = uuid4(), uuid4()
    db.add(
        ProjectORM(
            id=project_id,
            tenant_id=tenant_id,
            name="758 P1-3 Project",
            code=f"P-{uuid4().hex[:8]}",
            start_date=datetime.now(),
        )
    )
    await db.commit()
    db.add(
        DocumentORM(
            id=document_id,
            tenant_id=tenant_id,
            project_id=project_id,
            document_type="contract",
            filename="stale_lineage.pdf",
            upload_status="parsed_pending_analysis",
        )
    )
    await db.commit()

    authority_a = await _grant(db, tenant_id, document_id)
    thread_a = checkpoint_lineage.analysis_thread_id(
        document_id=document_id, authority=authority_a
    )
    register(thread_a)

    app = _build_real_graph(saver)
    cfg = {"configurable": {"thread_id": thread_a}}
    with pa.bound_authority(authority_a):
        result = await app.ainvoke(
            _initial_state(document_id, project_id, tenant_id, thread_a), cfg
        )
    assert "__interrupt__" in result
    checkpoint_id = (await app.aget_state(cfg)).config["configurable"]["checkpoint_id"]

    review = (
        await db.execute(
            select(ReviewItemORM)
            .where(ReviewItemORM.document_id == document_id)
            .execution_options(populate_existing=True)
        )
    ).scalars().one()
    review.checkpoint_id = checkpoint_id
    review.review_metadata = {
        **(review.review_metadata or {}),
        "tenant_id": str(tenant_id),
        "document_id": str(document_id),
    }
    await db.commit()
    review_row_id = review.id

    lineage = await _lineage(db, tenant_id, review_row_id)
    assert lineage is not None and lineage.thread_id == thread_a
    assert lineage.is_fenced, "the N13 claim must stamp the attempt that bound it"
    assert lineage.is_current_for_document

    return _Arranged(
        document_id=document_id,
        project_id=project_id,
        app=app,
        review_row_id=review_row_id,
        thread_a=thread_a,
        checkpoint_id=checkpoint_id,
        authority_a=authority_a,
    )


# ── processing-authority helpers ─────────────────────────────────────────────


async def _grant(
    db: AsyncSession, tenant_id: UUID, document_id: UUID
) -> pa.ProcessingAuthority:
    result = await pa.acquire(
        db,
        tenant_id=tenant_id,
        document_id=document_id,
        stage=pa.ProcessingStage.ANALYSIS,
    )
    await db.commit()
    assert result.authority is not None, result.outcome
    return result.authority


async def _expire_lease(db: AsyncSession, document_id: UUID) -> None:
    """Let A's lease lapse by the DATABASE clock, which is the only authority."""
    await db.execute(
        text(
            "UPDATE document_processing_operations "
            "   SET lease_expires_at = (clock_timestamp() AT TIME ZONE 'UTC') "
            "                          - make_interval(secs => 1) "
            " WHERE document_id = :d"
        ),
        {"d": document_id},
    )
    await db.commit()


async def _take_over_and_rebind(
    db: AsyncSession, tenant_id: UUID, arranged: _Arranged
) -> str:
    """B takes the document over and claims the review's lineage, for real."""
    await _expire_lease(db, arranged.document_id)
    authority_b = await _grant(db, tenant_id, arranged.document_id)
    assert authority_b.fencing_token > arranged.authority_a.fencing_token
    thread_b = checkpoint_lineage.analysis_thread_id(
        document_id=arranged.document_id, authority=authority_b
    )
    with pa.bound_authority(authority_b):
        await claim_review_lineage_for_current_attempt(
            thread_id=thread_b,
            tenant_id=str(tenant_id),
            document_id=str(arranged.document_id),
        )
    lineage = await _lineage(db, tenant_id, arranged.review_row_id)
    assert lineage is not None and lineage.thread_id == thread_b != arranged.thread_a
    assert lineage.is_current_for_document, "B's own lineage must be current"
    return thread_b


# ── observation helpers ──────────────────────────────────────────────────────


async def _lineage(
    db: AsyncSession, tenant_id: UUID, review_row_id: UUID
) -> resume_lineage.ReviewLineage | None:
    await db.rollback()
    return await resume_lineage.read_review_lineage(
        db, review_row_id=review_row_id, tenant_id=tenant_id
    )


async def _age_backoff(sessions: Any, tenant_id: UUID, review_row_id: UUID) -> None:
    """Let `record_failure`'s exponential backoff elapse.

    Aged with the database clock rather than slept through: the sweep only
    considers operations whose `next_attempt_at` has passed, so without this
    every case below would pass for the trivial reason that nothing was due.
    """
    async with sessions(tenant_id) as session:
        await session.execute(
            text(
                "UPDATE resume_operations "
                "   SET next_attempt_at = clock_timestamp() - interval '1 hour', "
                "       lease_expires_at = NULL, heartbeat_at = NULL "
                " WHERE review_row_id = cast(:r as uuid)"
            ),
            {"r": str(review_row_id)},
        )


async def _operation(db: AsyncSession, review_row_id: UUID) -> Any:
    await db.rollback()
    return (
        await db.execute(
            text("SELECT * FROM resume_operations WHERE review_row_id = :r"),
            {"r": review_row_id},
        )
    ).first()


async def _reload(db: AsyncSession, model: Any, pk: UUID) -> Any:
    await db.rollback()
    return (
        await db.execute(
            select(model).where(model.id == pk).execution_options(populate_existing=True)
        )
    ).scalars().one()


def _use_case(db: AsyncSession, tenant_id: UUID, saver: Any, app: Any, sessions: Any):
    return ResumeWorkflowUseCase(
        review_queue_repo=SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant_id),
        checkpoint_service=CheckpointService(checkpointer=saver),
        graph_app=app,
        claim_session_factory=sessions,
    )


async def _own(arranged: _Arranged, tenant_id: UUID, sessions: Any) -> Any:
    """A human approval that acquired durable ownership of lineage A."""
    ownership, _phase, refusal = await resume_ownership.acquire(
        review_row_id=arranged.review_row_id,
        tenant_id=tenant_id,
        project_id=arranged.project_id,
        document_id=arranged.document_id,
        thread_id=arranged.thread_a,
        source_checkpoint_id=arranged.checkpoint_id,
        decision="approve",
        feedback="",
        reviewer="Reviewer",
        session_factory=sessions,
    )
    assert ownership is not None, refusal
    return ownership


async def _make_n17_durable(
    arranged: _Arranged, tenant_id: UUID, ownership: Any, sessions: Any
) -> None:
    """Run the REAL N17 for lineage A, so its business effect is genuinely durable."""
    await persist_resume_analysis_atomically(
        state=_initial_state(
            arranged.document_id, arranged.project_id, tenant_id, arranged.thread_a
        ),
        provenance=ResumeProvenance(
            operation_id=ownership.operation_id,
            attempt_id=ownership.attempt_id,
            owner_token=ownership.owner_token,
            fencing_token=ownership.fencing_token,
            decision_revision=ownership.decision_revision,
            tenant_id=tenant_id,
        ),
        session_factory=sessions,
    )


async def _sweep(saver: Any, app: Any, sessions: Any):
    """One real reconciler sweep, wired to this test's database."""

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
        session_factory=sessions, use_case_factory=build_use_case
    )


async def _recover_directly(
    db: AsyncSession, tenant_id: UUID, saver: Any, app: Any, sessions: Any, operation: Any
) -> RecoveryOutcome:
    """The authoritative CAS, bypassing the scan's hint entirely.

    The candidate scan is cross-tenant and cannot read the fail-closed
    authority table, so skipping a row there is an optimisation, not the
    guarantee. Driving `recover` with the exact scanned identity proves the
    refusal happens where it must: inside the acquisition transaction.
    """
    return await _use_case(db, tenant_id, saver, app, sessions).recover(
        ResumeRecoveryRequest(
            operation_id=UUID(str(operation.id)),
            review_row_id=UUID(str(operation.review_row_id)),
            tenant_id=tenant_id,
            expected_decision=operation.decision,
            expected_decision_hash=operation.decision_hash,
            expected_decision_revision=operation.decision_revision,
            expected_fencing_token=operation.fencing_token,
        )
    )


async def _assert_nothing_was_finalized(
    db: AsyncSession, arranged: _Arranged, *, expected_phase: Phase
) -> None:
    """The review, the document and the operation are all untouched."""
    review = await _reload(db, ReviewItemORM, arranged.review_row_id)
    assert str(review.current_status.value) not in {"APPROVED", "REJECTED"}, (
        "a superseded lineage finalized the CURRENT review"
    )
    document = await _reload(db, DocumentORM, arranged.document_id)
    assert str(document.upload_status) != "analyzed", (
        "a superseded lineage marked the current document ANALYZED"
    )
    operation = await _operation(db, arranged.review_row_id)
    assert operation is not None, "durable evidence must be preserved, not destroyed"
    assert operation.phase == expected_phase.value, (
        f"the durable phase changed: {operation.phase} != {expected_phase.value}"
    )
    assert operation.thread_id == arranged.thread_a, (
        "the operation's own record of WHICH lineage it ran must survive"
    )


# ── A: FAILED_RETRYABLE on a superseded lineage must not resume ─────────────


async def test_failed_retryable_on_a_superseded_lineage_is_not_resumed(
    db: AsyncSession, test_user: User, real_saver: Any, sessions: Any
) -> None:
    saver, register = real_saver
    tenant_id = UUID(str(test_user.tenant_id))
    N17_RUNS.clear()
    arranged = await _arrange(db, tenant_id, saver, register)

    ownership = await _own(arranged, tenant_id, sessions)
    await resume_ownership.record_failure(
        ownership=ownership, error="worker died mid-resume", session_factory=sessions
    )
    await _age_backoff(sessions, tenant_id, arranged.review_row_id)
    operation = await _operation(db, arranged.review_row_id)
    assert operation.phase == Phase.FAILED_RETRYABLE.value

    await _take_over_and_rebind(db, tenant_id, arranged)

    swept = await _sweep(saver, arranged.app, sessions)
    assert swept == {"status": "ok", "scanned": 0, "recovered": 0, "refused": 0,
                     "failed": 0}, swept
    assert (
        await _recover_directly(db, tenant_id, saver, arranged.app, sessions, operation)
        is RecoveryOutcome.LINEAGE_SUPERSEDED
    )
    assert N17_RUNS == [], f"the reconciler resumed a superseded lineage: {N17_RUNS}"
    await _assert_nothing_was_finalized(db, arranged, expected_phase=Phase.FAILED_RETRYABLE)


# ── B: N17_DURABLE on a superseded lineage must not continue ────────────────


async def test_n17_durable_on_a_superseded_lineage_is_not_continued(
    db: AsyncSession, test_user: User, real_saver: Any, sessions: Any
) -> None:
    """The dangerous one: A's analysis is already committed.

    Recovery would normally pick this up and finalize it, because the phase
    truthfully says "the business effect is durable". It is -- for lineage A.
    Finalizing it would mark the CURRENT review approved and the CURRENT
    document ANALYZED on the strength of a superseded run.
    """
    saver, register = real_saver
    tenant_id = UUID(str(test_user.tenant_id))
    N17_RUNS.clear()
    arranged = await _arrange(db, tenant_id, saver, register)

    ownership = await _own(arranged, tenant_id, sessions)
    await _make_n17_durable(arranged, tenant_id, ownership, sessions)
    await resume_ownership.record_failure(
        ownership=ownership, error="died after N17", session_factory=sessions
    )
    await _age_backoff(sessions, tenant_id, arranged.review_row_id)
    operation = await _operation(db, arranged.review_row_id)
    assert operation.phase == Phase.N17_DURABLE.value, (
        "record_failure must preserve durable evidence"
    )
    assert operation.analysis_id is not None

    await _take_over_and_rebind(db, tenant_id, arranged)

    swept = await _sweep(saver, arranged.app, sessions)
    assert swept["scanned"] == 0 and swept["recovered"] == 0, swept
    assert (
        await _recover_directly(db, tenant_id, saver, arranged.app, sessions, operation)
        is RecoveryOutcome.LINEAGE_SUPERSEDED
    )
    assert N17_RUNS == [], f"the reconciler continued a superseded lineage: {N17_RUNS}"
    await _assert_nothing_was_finalized(db, arranged, expected_phase=Phase.N17_DURABLE)

    # The analysis A really did persist stays exactly where it is: historical
    # evidence, still keyed to its operation, simply not actionable.
    still_there = await _operation(db, arranged.review_row_id)
    assert still_there.analysis_id == operation.analysis_id


# ── C: GRAPH_COMPLETED on a superseded lineage must not finalize ────────────


async def test_graph_completed_on_a_superseded_lineage_is_not_finalized(
    db: AsyncSession, test_user: User, real_saver: Any, sessions: Any
) -> None:
    saver, register = real_saver
    tenant_id = UUID(str(test_user.tenant_id))
    N17_RUNS.clear()
    arranged = await _arrange(db, tenant_id, saver, register)

    ownership = await _own(arranged, tenant_id, sessions)
    await _make_n17_durable(arranged, tenant_id, ownership, sessions)
    assert await resume_ownership.mark_graph_completed(
        ownership=ownership,
        terminal_checkpoint_id="cp-terminal-758",
        document_id=str(arranged.document_id),
        session_factory=sessions,
    )
    await resume_ownership.record_failure(
        ownership=ownership, error="died after the terminal marker", session_factory=sessions
    )
    await _age_backoff(sessions, tenant_id, arranged.review_row_id)
    operation = await _operation(db, arranged.review_row_id)
    assert operation.phase == Phase.GRAPH_COMPLETED.value

    corrections_before = await _corrections(db, arranged.project_id)

    await _take_over_and_rebind(db, tenant_id, arranged)

    swept = await _sweep(saver, arranged.app, sessions)
    assert swept["scanned"] == 0 and swept["recovered"] == 0, swept
    assert (
        await _recover_directly(db, tenant_id, saver, arranged.app, sessions, operation)
        is RecoveryOutcome.LINEAGE_SUPERSEDED
    )
    await _assert_nothing_was_finalized(db, arranged, expected_phase=Phase.GRAPH_COMPLETED)
    assert await _corrections(db, arranged.project_id) == corrections_before, (
        "a superseded lineage appended a human-decision correction event"
    )


async def _corrections(db: AsyncSession, project_id: UUID) -> int:
    await db.rollback()
    rows = (
        await db.execute(
            select(ProjectEventORM).where(
                ProjectEventORM.project_id == project_id,
                ProjectEventORM.event_type == "hitl.correction",
            )
        )
    ).scalars().all()
    return len(rows)


# ── D: the control -- same-lineage recovery still works ────────────────────


async def test_same_lineage_recovery_still_recovers(
    db: AsyncSession, test_user: User, real_saver: Any, sessions: Any
) -> None:
    """Without a rebind, the reconciler must still complete the human decision.

    This is what keeps the three refusals above honest. The guard has to be a
    comparison against the review's CURRENT lineage; a blanket "never recover
    a durable operation" would pass every test above and silently break the
    crash-recovery guarantee #649/#650 exists to provide.
    """
    saver, register = real_saver
    tenant_id = UUID(str(test_user.tenant_id))
    N17_RUNS.clear()
    arranged = await _arrange(db, tenant_id, saver, register)

    ownership = await _own(arranged, tenant_id, sessions)
    await resume_ownership.record_failure(
        ownership=ownership, error="worker died mid-resume", session_factory=sessions
    )
    await _age_backoff(sessions, tenant_id, arranged.review_row_id)
    operation = await _operation(db, arranged.review_row_id)
    assert operation.phase == Phase.FAILED_RETRYABLE.value

    # No takeover, no rebind: the lineage the operation names is still current.
    lineage = await _lineage(db, tenant_id, arranged.review_row_id)
    assert lineage is not None and lineage.thread_id == arranged.thread_a
    assert lineage.is_current_for_document

    async with sessions(None) as session:
        candidates = (
            await session.execute(
                reconciler._CLAIMABLE_SQL,
                {"phases": list(reconciler._RECOVERABLE_PHASES), "limit": 20},
            )
        ).all()
    assert [UUID(str(row.id)) for row in candidates] == [UUID(str(operation.id))], (
        "a current-lineage operation must remain a recovery candidate"
    )

    outcome = await _recover_directly(
        db, tenant_id, saver, arranged.app, sessions, operation
    )
    assert outcome is RecoveryOutcome.RECOVERED, outcome
    assert [str(arranged.document_id)] == N17_RUNS, (
        f"recovery must replay the graph for its own lineage: {N17_RUNS}"
    )
    review = await _reload(db, ReviewItemORM, arranged.review_row_id)
    assert str(review.current_status.value) == "APPROVED"
    recovered = await _operation(db, arranged.review_row_id)
    assert recovered.phase == Phase.FINALIZED_APPROVED.value


# ── the durable-write fence: rebound AFTER ownership was acquired ───────────


async def test_an_owned_resume_cannot_persist_after_the_review_is_rebound(
    db: AsyncSession, test_user: User, real_saver: Any, sessions: Any
) -> None:
    """Ownership stays valid across a rebind, so the fence alone is not enough.

    Acquisition is checked, but a resume that ALREADY acquired holds a live
    lease and an uncontested fence: a processing takeover advances no resume
    fencing token, so every ownership check this worker performs keeps
    passing while the lineage under it becomes history. Without a lineage
    comparison at the durable seams, such a worker would commit N17 and
    finalize the current review on the strength of a superseded run.

    Both durable writers funnel through `verify_in_transaction`, so both must
    refuse -- and refuse having written nothing.
    """
    saver, register = real_saver
    tenant_id = UUID(str(test_user.tenant_id))
    N17_RUNS.clear()
    arranged = await _arrange(db, tenant_id, saver, register)

    ownership = await _own(arranged, tenant_id, sessions)
    operation_before = await _operation(db, arranged.review_row_id)
    assert operation_before.phase == Phase.RUNNING.value

    # The lease is still live and the fence untouched: by every pre-#758
    # measure this worker is the rightful owner.
    async with sessions(tenant_id) as session:
        await resume_ownership.verify_in_transaction(session, ownership)

    await _take_over_and_rebind(db, tenant_id, arranged)

    with pytest.raises(OwnershipError, match="Lineage superseded"):
        await _make_n17_durable(arranged, tenant_id, ownership, sessions)
    with pytest.raises(OwnershipError, match="Lineage superseded"):
        await resume_ownership.finalize_v3(
            ownership=ownership,
            review_row_id=arranged.review_row_id,
            approved=True,
            approved_by="Reviewer",
            feedback="",
            document_id=arranged.document_id,
            session_factory=sessions,
        )

    analyses = (
        await db.execute(
            select(Analysis).where(Analysis.resume_operation_id == ownership.operation_id)
        )
    ).scalars().all()
    assert analyses == [], "a superseded lineage committed N17"
    await _assert_nothing_was_finalized(db, arranged, expected_phase=Phase.RUNNING)
