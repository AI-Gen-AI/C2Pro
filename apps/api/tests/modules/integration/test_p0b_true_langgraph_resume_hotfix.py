"""
C2PRO P0b TRUE LANGGRAPH RESUME + EXACTLY-ONCE HITL HOTFIX.

Decisive proof runs against a REAL CompiledStateGraph, the REAL production
``human_interrupt_node`` / ``save_to_db_node`` / ``route_after_human_interrupt``,
a REAL ``interrupt()``, REAL ``Command(resume=...)`` and a REAL
``AsyncPostgresSaver`` on real PostgreSQL. No fake graph app at the
decisive boundary -- a fake was exactly what hid these defects: the previous
suites stubbed ``ainvoke`` to call ``save_to_db_node`` directly, so the
resume path itself was never exercised.

RED evidence this file encodes (all independently reproduced against
langgraph 1.2.10 / langgraph-checkpoint-postgres 3.1.2 before any fix):

1. The shipped pattern -- ``aupdate_state(thread-only)`` followed by
   ``ainvoke(None, thread-only)`` -- does NOT resume an interrupt. The
   interrupt node re-enters FROM THE TOP, ``interrupt()`` raises again, the
   call returns another ``__interrupt__`` and downstream/N17 never runs.
   That is precisely the production symptom: decision recorded, no
   analysis, document stuck at parsed_pending_analysis.
2. ``Command(resume=...)`` IS the supported primitive; the value it carries
   is what ``interrupt()`` returns inside the node.
3. A resumed node re-executes from its beginning, so every pre-interrupt
   side effect runs again.
4. Sequential AND concurrent double approves each executed downstream
   TWICE, persisting duplicate work.
5. A wrong/stale checkpoint_id silently no-ops -- it returns without
   running anything and WITHOUT raising, so an unchecked resume cannot tell
   success from "nothing happened".
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command
from psycopg_pool import AsyncConnectionPool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from src.modules.hitl.application.resume_workflow_use_case import (
    ResumeWorkflowRequest,
    ResumeWorkflowUseCase,
    WorkflowDecision,
)
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus
from src.projects.adapters.persistence.models import ProjectORM
from src.temporal.adapters.persistence.models import ProjectEventORM

pytestmark = pytest.mark.asyncio


# ── real checkpointer ────────────────────────────────────────────────────────


def _psycopg_dsn() -> str:
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("DATABASE_URL/TEST_DATABASE_URL not set -- cannot reach real Postgres")
    return dsn.replace("postgresql+asyncpg://", "postgresql://")


@pytest.fixture
async def real_saver():
    pool = AsyncConnectionPool(
        conninfo=_psycopg_dsn(),
        min_size=0,
        max_size=8,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": None},
    )
    await pool.open(wait=True, timeout=15)
    saver = AsyncPostgresSaver(conn=pool)
    threads: list[str] = []

    def register(thread_id: str) -> str:
        threads.append(thread_id)
        return thread_id

    try:
        yield saver, register
    finally:
        async with pool.connection() as conn, conn.cursor() as cur:
            for t in threads:
                await cur.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s", (t,))
                await cur.execute("DELETE FROM checkpoint_blobs WHERE thread_id = %s", (t,))
                await cur.execute("DELETE FROM checkpoints WHERE thread_id = %s", (t,))
        await pool.close()


# ── real graph built from the REAL production nodes ──────────────────────────

_DOWNSTREAM_RUNS: list[str] = []


async def _entry(state: ProjectState) -> ProjectState:
    return state


async def _counting_save_to_db(state: ProjectState) -> ProjectState:
    """The REAL N17, with an execution counter around it.

    The counter is what proves exactly-once: it increments per real
    invocation of the production persistence node, so a duplicate resume is
    visible even if the DB were to swallow it.
    """
    _DOWNSTREAM_RUNS.append(str(state.get("document_id")))
    return await save_to_db_node(state)


def _build_real_graph(saver: AsyncPostgresSaver):
    """Compile a REAL StateGraph over the REAL production HITL nodes.

    Trimmed to the decisive segment (entry -> N13 interrupt -> conditional
    -> N17) so the test is deterministic without the AI extractor nodes --
    but every node and the routing function here are the production ones,
    and the interrupt/resume boundary is fully real.
    """
    g = StateGraph(ProjectState)
    g.add_node("entry", _entry)
    g.add_node("human_interrupt", human_interrupt_node)
    g.add_node("save_to_db", _counting_save_to_db)
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
            name="True Resume Hotfix Project",
            code="P0B-TRUE",
            start_date=datetime.now(),
        )
    )
    await db.commit()
    document = DocumentORM(
        id=document_id,
        tenant_id=tenant.id,
        project_id=project_id,
        document_type="contract",
        filename="true_resume.pdf",
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
    created_at: datetime | None = None,
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
        created_at=created_at or datetime.now(UTC).replace(tzinfo=None),
        approved_by="Prior Reviewer" if approved_at else None,
        approved_at=approved_at,
    )


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
                "proof_marker": "p0b-true-resume",
            }
        },
        "node_results": [],
    }


async def _run_to_interrupt(app, document, tenant, thread_id) -> tuple[dict, str]:
    cfg = {"configurable": {"thread_id": thread_id}}
    result = await app.ainvoke(_initial_state(document, tenant, thread_id), cfg)
    assert "__interrupt__" in result, "the real graph must pause at the human interrupt"
    snapshot = await app.aget_state(cfg)
    return cfg, snapshot.config["configurable"]["checkpoint_id"]


def _use_case(db, tenant, saver, app, session_factory) -> ResumeWorkflowUseCase:
    return ResumeWorkflowUseCase(
        review_queue_repo=SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant.id),
        checkpoint_service=CheckpointService(checkpointer=saver),
        graph_app=app,
        claim_session_factory=session_factory,
    )


@pytest.fixture
def claim_session_factory(db: AsyncSession):
    """Route the exactly-once claim at the test's own session.

    In production the claim opens its own short transaction via
    get_session_with_tenant precisely so it commits independently of the
    request; under test we point it at the test session so the claim is
    visible to the same transaction the assertions read.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _factory(_tenant_id: UUID):
        yield db
        await db.commit()

    return _factory


# ── 1. RED: the shipped pattern does not resume ──────────────────────────────


async def test_red_thread_only_ainvoke_none_does_not_resume(
    real_saver, db: AsyncSession, test_user: User
) -> None:
    """RED: aupdate_state(thread-only) + ainvoke(None, thread-only) fails.

    The interrupt node re-enters from the top, interrupt() raises again, the
    call returns another __interrupt__, and N17 NEVER runs.
    """
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed(db, tenant)
    thread_id = register(f"document:{document.id}:analysis")
    app = _build_real_graph(saver)
    _DOWNSTREAM_RUNS.clear()

    cfg, checkpoint_id = await _run_to_interrupt(app, document, tenant, thread_id)
    snapshot = await app.aget_state(cfg)

    state = dict(snapshot.values)
    state["human_approval_required"] = False
    state["human_decision"] = "approve"
    await app.aupdate_state(cfg, state)
    out = await app.ainvoke(None, cfg)

    assert "__interrupt__" in out, (
        "RED: ainvoke(None, ...) must be shown NOT to resume -- it re-interrupts"
    )
    assert _DOWNSTREAM_RUNS == [], "RED: N17 must never have executed on this path"

    analyses = (
        await db.execute(select(Analysis).where(Analysis.project_id == document.project_id))
    ).scalars().all()
    assert analyses == []


# ── 2. GREEN: Command(resume) against the exact checkpoint config ────────────


async def test_command_resume_consumes_interrupt_and_runs_downstream_once(
    real_saver, db: AsyncSession, test_user: User
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed(db, tenant)
    thread_id = register(f"document:{document.id}:analysis")
    app = _build_real_graph(saver)
    _DOWNSTREAM_RUNS.clear()

    cfg, checkpoint_id = await _run_to_interrupt(app, document, tenant, thread_id)

    restored = await CheckpointService(checkpointer=saver).restore_checkpoint(
        thread_id=thread_id, checkpoint_id=checkpoint_id
    )
    assert restored is not None
    assert restored.checkpoint_id == checkpoint_id
    assert restored.config["configurable"]["thread_id"] == thread_id
    assert "checkpoint_ns" in restored.config["configurable"], (
        "the exact-resume config must carry checkpoint_ns, which thread_id alone cannot supply"
    )

    out = await app.ainvoke(
        Command(resume={"decision": "approve", "feedback": "looks good"}), restored.config
    )

    assert "__interrupt__" not in out, "Command(resume) must consume the interrupt"
    assert out.get("human_decision") == "approve", "the node must CONSUME interrupt()'s return"
    assert out.get("human_approval_required") is False
    assert len(_DOWNSTREAM_RUNS) == 1, "N17 must execute exactly once"
    assert out.get("analysis_id")


async def test_reject_via_command_resume_never_runs_n17(
    real_saver, db: AsyncSession, test_user: User
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed(db, tenant)
    thread_id = register(f"document:{document.id}:analysis")
    app = _build_real_graph(saver)
    _DOWNSTREAM_RUNS.clear()

    cfg, checkpoint_id = await _run_to_interrupt(app, document, tenant, thread_id)
    restored = await CheckpointService(checkpointer=saver).restore_checkpoint(
        thread_id=thread_id, checkpoint_id=checkpoint_id
    )

    out = await app.ainvoke(
        Command(resume={"decision": "reject", "feedback": "bad extraction"}), restored.config
    )

    assert "__interrupt__" not in out
    assert out.get("human_decision") == "reject"
    assert out.get("workflow_terminated") is True
    assert _DOWNSTREAM_RUNS == [], "a rejection must never reach N17"
    assert not out.get("analysis_id")

    analyses = (
        await db.execute(select(Analysis).where(Analysis.project_id == document.project_id))
    ).scalars().all()
    assert analyses == []


# ── 3. Full use-case lifecycle through the real graph ────────────────────────


async def test_use_case_approve_resumes_real_graph_to_n17_and_analyzed(
    real_saver, db: AsyncSession, test_user: User, claim_session_factory
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed(db, tenant)
    thread_id = register(f"document:{document.id}:analysis")
    app = _build_real_graph(saver)
    _DOWNSTREAM_RUNS.clear()

    cfg, checkpoint_id = await _run_to_interrupt(app, document, tenant, thread_id)

    # human_interrupt_node created the canonical pending review for real.
    rows = (
        await db.execute(select(ReviewItemORM).where(ReviewItemORM.document_id == document.id))
    ).scalars().all()
    assert len(rows) == 1
    review = rows[0]
    review.thread_id = thread_id
    review.checkpoint_id = checkpoint_id
    review.review_metadata = {**(review.review_metadata or {}), "tenant_id": str(tenant.id)}
    await db.commit()

    use_case = _use_case(db, tenant, saver, app, claim_session_factory)
    response = await use_case.execute(
        review_id=review.item_id,
        request=ResumeWorkflowRequest(
            decision=WorkflowDecision.APPROVE, feedback="", approved_by="Reviewer"
        ),
    )

    assert response.status == "resumed"
    assert len(_DOWNSTREAM_RUNS) == 1

    refreshed = await db.get(ReviewItemORM, review.id)
    await db.refresh(refreshed)
    assert refreshed.current_status == ReviewStatus.APPROVED.value
    assert refreshed.approved_by == "Reviewer"

    analyses = (
        await db.execute(select(Analysis).where(Analysis.project_id == document.project_id))
    ).scalars().all()
    assert len(analyses) == 1, "exactly one analysis"

    events = (
        await db.execute(
            select(ProjectEventORM).where(
                ProjectEventORM.project_id == document.project_id,
                ProjectEventORM.event_type == "graph.completed",
            )
        )
    ).scalars().all()
    assert len(events) == 1, "exactly one graph.completed"

    refreshed_doc = await db.get(DocumentORM, document.id)
    await db.refresh(refreshed_doc)
    assert refreshed_doc.upload_status == "analyzed"

    all_rows = (
        await db.execute(select(ReviewItemORM).where(ReviewItemORM.document_id == document.id))
    ).scalars().all()
    assert len(all_rows) == 1, "the resumed interrupt node must not create another review"


# ── 4. Exactly-once ──────────────────────────────────────────────────────────


async def test_sequential_double_approve_executes_downstream_once(
    real_saver, db: AsyncSession, test_user: User, claim_session_factory
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed(db, tenant)
    thread_id = register(f"document:{document.id}:analysis")
    app = _build_real_graph(saver)
    _DOWNSTREAM_RUNS.clear()

    cfg, checkpoint_id = await _run_to_interrupt(app, document, tenant, thread_id)
    review = (
        await db.execute(select(ReviewItemORM).where(ReviewItemORM.document_id == document.id))
    ).scalars().one()
    review.thread_id, review.checkpoint_id = thread_id, checkpoint_id
    review.review_metadata = {**(review.review_metadata or {}), "tenant_id": str(tenant.id)}
    await db.commit()

    use_case = _use_case(db, tenant, saver, app, claim_session_factory)
    req = ResumeWorkflowRequest(decision=WorkflowDecision.APPROVE, feedback="", approved_by="R")

    first = await use_case.execute(review_id=review.item_id, request=req)
    assert first.status == "resumed"

    second = await use_case.execute(review_id=review.item_id, request=req)
    assert second.status == ReviewStatus.APPROVED.value, "second approve is idempotent, not a re-run"

    assert len(_DOWNSTREAM_RUNS) == 1, "N17 exactly once across two sequential approvals"
    analyses = (
        await db.execute(select(Analysis).where(Analysis.project_id == document.project_id))
    ).scalars().all()
    assert len(analyses) == 1


async def test_red_unguarded_concurrent_resume_duplicates_downstream(
    real_saver, db: AsyncSession, test_user: User
) -> None:
    """RED characterisation: WITHOUT the DB claim, two concurrent
    Command(resume) calls against the same interrupted checkpoint both run
    to completion and execute N17 TWICE.

    This pins the exact race the exactly-once claim exists to close. It
    drives the real compiled graph directly (no use case), so it keeps
    documenting the underlying LangGraph behaviour independently of how the
    application layer is refactored -- the guarantee lives in the claim, NOT
    in the graph.
    """
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed(db, tenant)
    thread_id = register(f"document:{document.id}:analysis")
    app = _build_real_graph(saver)
    _DOWNSTREAM_RUNS.clear()

    cfg, checkpoint_id = await _run_to_interrupt(app, document, tenant, thread_id)
    restored = await CheckpointService(checkpointer=saver).restore_checkpoint(
        thread_id=thread_id, checkpoint_id=checkpoint_id
    )

    await asyncio.gather(
        app.ainvoke(Command(resume={"decision": "approve", "feedback": ""}), restored.config),
        app.ainvoke(Command(resume={"decision": "approve", "feedback": ""}), restored.config),
        return_exceptions=True,
    )

    assert len(_DOWNSTREAM_RUNS) == 2, (
        "RED: unguarded concurrent resume is expected to double-execute N17 -- "
        f"got {_DOWNSTREAM_RUNS}. LangGraph does not serialise this for us."
    )


async def test_concurrent_double_approve_executes_downstream_once(
    real_saver, db: AsyncSession, test_user: User, claim_session_factory
) -> None:
    """The reproduced race: without the DB claim, both callers resumed and
    N17 ran twice (verified against the real graph before the fix).
    """
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed(db, tenant)
    thread_id = register(f"document:{document.id}:analysis")
    app = _build_real_graph(saver)
    _DOWNSTREAM_RUNS.clear()

    cfg, checkpoint_id = await _run_to_interrupt(app, document, tenant, thread_id)
    review = (
        await db.execute(select(ReviewItemORM).where(ReviewItemORM.document_id == document.id))
    ).scalars().one()
    review.thread_id, review.checkpoint_id = thread_id, checkpoint_id
    review.review_metadata = {**(review.review_metadata or {}), "tenant_id": str(tenant.id)}
    await db.commit()

    use_case = _use_case(db, tenant, saver, app, claim_session_factory)
    req = ResumeWorkflowRequest(decision=WorkflowDecision.APPROVE, feedback="", approved_by="R")

    results = await asyncio.gather(
        use_case.execute(review_id=review.item_id, request=req),
        use_case.execute(review_id=review.item_id, request=req),
        return_exceptions=True,
    )

    succeeded = [r for r in results if not isinstance(r, Exception)]
    assert len(succeeded) >= 1, f"at least one approve must succeed: {results}"
    assert len(_DOWNSTREAM_RUNS) == 1, (
        f"N17 must execute exactly once under concurrency, got {_DOWNSTREAM_RUNS}"
    )

    analyses = (
        await db.execute(select(Analysis).where(Analysis.project_id == document.project_id))
    ).scalars().all()
    assert len(analyses) == 1, "exactly one analysis under concurrent approval"

    events = (
        await db.execute(
            select(ProjectEventORM).where(
                ProjectEventORM.project_id == document.project_id,
                ProjectEventORM.event_type == "graph.completed",
            )
        )
    ).scalars().all()
    assert len(events) == 1, "exactly one graph.completed under concurrent approval"


# ── 5. Failure atomicity ─────────────────────────────────────────────────────


async def test_resume_failure_does_not_produce_false_approval(
    real_saver, db: AsyncSession, test_user: User, claim_session_factory
) -> None:
    """A graph-resume failure must never leave a claimed APPROVED state.

    Previously the review was flipped to APPROVED BEFORE the graph ran and
    graph exceptions were swallowed into a "_with_errors" status, so the
    system reported a successful approval while N17 had never executed.
    """
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed(db, tenant)
    thread_id = register(f"document:{document.id}:analysis")
    app = _build_real_graph(saver)
    _DOWNSTREAM_RUNS.clear()

    cfg, checkpoint_id = await _run_to_interrupt(app, document, tenant, thread_id)
    review = (
        await db.execute(select(ReviewItemORM).where(ReviewItemORM.document_id == document.id))
    ).scalars().one()
    review.thread_id, review.checkpoint_id = thread_id, checkpoint_id
    review.review_metadata = {**(review.review_metadata or {}), "tenant_id": str(tenant.id)}
    await db.commit()

    class _ExplodingGraph:
        checkpointer = saver

        async def ainvoke(self, *_a: Any, **_k: Any) -> dict:
            raise RuntimeError("checkpointer connection reset")

    use_case = _use_case(db, tenant, saver, _ExplodingGraph(), claim_session_factory)

    with pytest.raises(RuntimeError):
        await use_case.execute(
            review_id=review.item_id,
            request=ResumeWorkflowRequest(
                decision=WorkflowDecision.APPROVE, feedback="", approved_by="R"
            ),
        )

    refreshed = await db.get(ReviewItemORM, review.id)
    await db.refresh(refreshed)
    assert refreshed.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED.value, (
        "a failed resume must leave the review genuinely pending, not falsely APPROVED"
    )
    assert refreshed.approved_at is None
    assert _DOWNSTREAM_RUNS == []
    analyses = (
        await db.execute(select(Analysis).where(Analysis.project_id == document.project_id))
    ).scalars().all()
    assert analyses == []

    # ...and the claim was released, so the review is genuinely retryable.
    assert (refreshed.review_metadata or {}).get("resume_claim") is None


async def test_wrong_checkpoint_resume_fails_closed(
    real_saver, db: AsyncSession, test_user: User, claim_session_factory
) -> None:
    """A stale/wrong checkpoint_id silently no-ops in LangGraph (returns
    without running anything, raising nothing). It must be detected and
    surfaced as a failure, never reported as a completed approval.
    """
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed(db, tenant)
    thread_id = register(f"document:{document.id}:analysis")
    app = _build_real_graph(saver)
    _DOWNSTREAM_RUNS.clear()

    cfg, checkpoint_id = await _run_to_interrupt(app, document, tenant, thread_id)
    review = (
        await db.execute(select(ReviewItemORM).where(ReviewItemORM.document_id == document.id))
    ).scalars().one()
    review.thread_id = thread_id
    review.checkpoint_id = str(uuid.uuid4())  # never written for this thread
    review.review_metadata = {**(review.review_metadata or {}), "tenant_id": str(tenant.id)}
    await db.commit()

    use_case = _use_case(db, tenant, saver, app, claim_session_factory)

    with pytest.raises(ValueError):
        await use_case.execute(
            review_id=review.item_id,
            request=ResumeWorkflowRequest(
                decision=WorkflowDecision.APPROVE, feedback="", approved_by="R"
            ),
        )

    refreshed = await db.get(ReviewItemORM, review.id)
    await db.refresh(refreshed)
    assert refreshed.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED.value
    assert _DOWNSTREAM_RUNS == []


# ── 6. Legacy shape + tenant isolation ───────────────────────────────────────


async def test_historical_row_a_is_never_targeted_by_resume(
    real_saver, db: AsyncSession, test_user: User, claim_session_factory
) -> None:
    """The #640 canonical selection must still hold under true resume."""
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed(db, tenant)
    thread_id = register(f"document:{document.id}:analysis")
    app = _build_real_graph(saver)
    _DOWNSTREAM_RUNS.clear()

    cfg, checkpoint_id = await _run_to_interrupt(app, document, tenant, thread_id)
    row_b = (
        await db.execute(select(ReviewItemORM).where(ReviewItemORM.document_id == document.id))
    ).scalars().one()
    row_b.thread_id, row_b.checkpoint_id = thread_id, checkpoint_id
    row_b.review_metadata = {**(row_b.review_metadata or {}), "tenant_id": str(tenant.id)}
    row_b.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=14)

    now = datetime.now(UTC).replace(tzinfo=None)
    row_a = _review_row(
        tenant_id=tenant.id,
        project_id=document.project_id,
        document_id=document.id,
        thread_id=thread_id,
        checkpoint_id="historical-unrelated",
        status=ReviewStatus.APPROVED,
        created_at=now,
        approved_at=now,
    )
    db.add(row_a)
    await db.commit()
    original_a_approved_at = row_a.approved_at

    use_case = _use_case(db, tenant, saver, app, claim_session_factory)
    response = await use_case.execute(
        review_id=row_b.item_id,
        request=ResumeWorkflowRequest(
            decision=WorkflowDecision.APPROVE, feedback="", approved_by="R"
        ),
    )
    assert response.status == "resumed"

    refreshed_b = await db.get(ReviewItemORM, row_b.id)
    refreshed_a = await db.get(ReviewItemORM, row_a.id)
    await db.refresh(refreshed_b)
    await db.refresh(refreshed_a)
    assert refreshed_b.current_status == ReviewStatus.APPROVED.value
    assert refreshed_a.approved_at == original_a_approved_at, "historical row A untouched"
    assert len(_DOWNSTREAM_RUNS) == 1

    rows = (
        await db.execute(select(ReviewItemORM).where(ReviewItemORM.document_id == document.id))
    ).scalars().all()
    assert len(rows) == 2, "no extra review row created by the resumed interrupt node"


async def test_cross_tenant_cannot_resume(
    real_saver, db: AsyncSession, test_user: User, test_tenant_2: Tenant, claim_session_factory
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed(db, tenant)
    thread_id = register(f"document:{document.id}:analysis")
    app = _build_real_graph(saver)
    _DOWNSTREAM_RUNS.clear()

    cfg, checkpoint_id = await _run_to_interrupt(app, document, tenant, thread_id)
    review = (
        await db.execute(select(ReviewItemORM).where(ReviewItemORM.document_id == document.id))
    ).scalars().one()
    review.thread_id, review.checkpoint_id = thread_id, checkpoint_id
    review.review_metadata = {**(review.review_metadata or {}), "tenant_id": str(tenant.id)}
    await db.commit()

    # A use case scoped to ANOTHER tenant must not resolve, claim or resume it.
    other = ResumeWorkflowUseCase(
        review_queue_repo=SqlAlchemyReviewQueueRepository(session=db, tenant_id=test_tenant_2.id),
        checkpoint_service=CheckpointService(checkpointer=saver),
        graph_app=app,
        claim_session_factory=claim_session_factory,
    )

    with pytest.raises(ValueError):
        await other.execute(
            review_id=review.item_id,
            request=ResumeWorkflowRequest(
                decision=WorkflowDecision.APPROVE, feedback="", approved_by="Intruder"
            ),
        )

    refreshed = await db.get(ReviewItemORM, review.id)
    await db.refresh(refreshed)
    assert refreshed.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED.value
    assert _DOWNSTREAM_RUNS == []
