"""
C2PRO P0b PROD CHECKPOINTTUPLE RESTORE HOTFIX -- real Postgres checkpointer
integration.

Objective 6: the CheckpointTuple positional-unpack + missing-checkpoint_id-
forwarding defect (see test_checkpoint_service.py's module docstring for
full root-cause detail) escaped mocking in the original TASK-BCK-031 test
suite because that suite mocked ``aget_tuple`` to return a bare 3-tuple, not
the real 5-field ``langgraph.checkpoint.base.CheckpointTuple`` the actual
installed langgraph-checkpoint-postgres==3.1.2 / langgraph-checkpoint==4.2.0
packages return. A unit-level mock fix alone is therefore not sufficient
proof -- this file drives a REAL ``AsyncPostgresSaver`` against the real
local Postgres checkpoint schema (``checkpoints``/``checkpoint_blobs``/
``checkpoint_writes``, provisioned by scripts/checkpoint_bootstrap.py, the
same schema production runs), the same connection mechanics
scripts/checkpoint_bootstrap.py itself uses (psycopg AsyncConnectionPool,
DSN with the asyncpg driver prefix stripped).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from psycopg_pool import AsyncConnectionPool
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
from src.temporal.adapters.persistence.models import ProjectEventORM

pytestmark = pytest.mark.asyncio


def _psycopg_dsn() -> str:
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("DATABASE_URL/TEST_DATABASE_URL not set -- cannot reach real Postgres")
    return dsn.replace("postgresql+asyncpg://", "postgresql://")


@pytest.fixture
async def real_postgres_saver():
    """A REAL AsyncPostgresSaver against the local test Postgres checkpoint
    schema -- not a mock, not MemorySaver. Cleans up its own rows after the
    test so this file leaves no state behind.
    """
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    pool = AsyncConnectionPool(
        conninfo=_psycopg_dsn(),
        min_size=0,
        max_size=2,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": None},
    )
    await pool.open(wait=True, timeout=10)
    saver = AsyncPostgresSaver(conn=pool)
    thread_ids: list[str] = []

    def _register(thread_id: str) -> str:
        thread_ids.append(thread_id)
        return thread_id

    try:
        yield saver, _register
    finally:
        async with pool.connection() as conn, conn.cursor() as cur:
            for thread_id in thread_ids:
                await cur.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s", (thread_id,))
                await cur.execute("DELETE FROM checkpoint_blobs WHERE thread_id = %s", (thread_id,))
                await cur.execute("DELETE FROM checkpoints WHERE thread_id = %s", (thread_id,))
        await pool.close()


async def _write_real_checkpoint(saver, thread_id: str, *, step_label: str, version: str) -> str:
    """Write one real, durable checkpoint for thread_id via the actual
    AsyncPostgresSaver.aput() -- the same write path
    src.analysis.adapters.graph.workflow's compiled graph uses on an
    interrupt. Returns the real checkpoint_id LangGraph assigned.

    `version` must be unique per checkpoint written for the same thread_id:
    checkpoint_blobs is keyed by (thread_id, checkpoint_ns, channel,
    version) with ON CONFLICT DO NOTHING, so two checkpoints reusing the
    same version for the same channel would silently share one blob row.
    """
    from langgraph.checkpoint.base import empty_checkpoint

    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {"__root__": {"step": step_label, "human_approval_required": True}}
    # __root__'s value is a dict (non-primitive), so AsyncPostgresSaver
    # routes it into the checkpoint_blobs table, keyed by the channel
    # version recorded in BOTH the checkpoint's own channel_versions AND
    # the new_versions argument passed to aput -- omitting either leaves
    # the blob unwritten and channel_values empty on reload.
    checkpoint["channel_versions"] = {"__root__": version}
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    await saver.aput(config, checkpoint, {"source": "loop", "step": 0, "parents": {}}, {"__root__": version})
    return str(checkpoint["id"])


async def test_real_postgres_checkpoint_tuple_has_five_fields(real_postgres_saver) -> None:
    """Contract check against the real saver's actual return value (not the
    base-class introspection test in test_checkpoint_service.py) -- proves
    AsyncPostgresSaver.aget_tuple genuinely returns the 5-field
    CheckpointTuple in this installed version, end to end.
    """
    saver, register = real_postgres_saver
    thread_id = register("p0b-checkpoint-restore-fields")
    checkpoint_id = await _write_real_checkpoint(saver, thread_id, step_label="only", version="1")

    tup = await saver.aget_tuple({"configurable": {"thread_id": thread_id}})

    assert tup is not None
    assert tup._fields == ("config", "checkpoint", "metadata", "parent_config", "pending_writes")
    assert tup.checkpoint["id"] == checkpoint_id


async def test_load_checkpoint_against_real_saver_no_unpack_error(real_postgres_saver) -> None:
    """The exact regression: CheckpointService.load_checkpoint() must not
    raise "too many values to unpack" against a REAL AsyncPostgresSaver
    response -- this is what a mock-only fix cannot prove.
    """
    from src.modules.hitl.adapters.checkpoint_service import CheckpointService

    saver, register = real_postgres_saver
    thread_id = register("p0b-checkpoint-restore-no-unpack")
    checkpoint_id = await _write_real_checkpoint(saver, thread_id, step_label="interrupted", version="1")

    service = CheckpointService(checkpointer=saver)
    result = await service.load_checkpoint(thread_id=thread_id, checkpoint_id=checkpoint_id)

    assert result is not None
    assert result["id"] == checkpoint_id
    state = service.extract_state(result)
    assert state["step"] == "interrupted"
    assert state["human_approval_required"] is True


async def test_load_checkpoint_explicit_checkpoint_id_loads_older_not_latest(real_postgres_saver) -> None:
    """Objective 3/4's real-world proof: write TWO real checkpoints for one
    thread, then request the OLDER one explicitly by checkpoint_id. The old
    (pre-fix) code never forwarded checkpoint_id into `configurable`, so
    AsyncPostgresSaver always resolved the LATEST -- this reproduces
    exactly that class of bug against a real saver, not a mock that could
    be made to look correct either way.
    """
    from src.modules.hitl.adapters.checkpoint_service import CheckpointService

    saver, register = real_postgres_saver
    thread_id = register("p0b-checkpoint-restore-explicit-older")
    older_id = await _write_real_checkpoint(saver, thread_id, step_label="first", version="1")
    newer_id = await _write_real_checkpoint(saver, thread_id, step_label="second", version="2")
    assert older_id != newer_id

    service = CheckpointService(checkpointer=saver)

    explicit = await service.load_checkpoint(thread_id=thread_id, checkpoint_id=older_id)
    assert explicit is not None
    assert explicit["id"] == older_id, "requesting the OLDER checkpoint must not silently return the latest"

    fallback = await service.load_checkpoint(thread_id=thread_id, checkpoint_id=None)
    assert fallback is not None
    assert fallback["id"] == newer_id, "thread-only fallback (no checkpoint_id) must still resolve to latest"


async def test_load_checkpoint_nonexistent_checkpoint_id_fails_closed(real_postgres_saver) -> None:
    """A real thread with real checkpoints, but an explicit checkpoint_id
    that was never written for it, must return None -- never fall back to
    a different (latest/sibling) checkpoint for that thread.
    """
    from src.modules.hitl.adapters.checkpoint_service import CheckpointService

    saver, register = real_postgres_saver
    thread_id = register("p0b-checkpoint-restore-nonexistent")
    await _write_real_checkpoint(saver, thread_id, step_label="only", version="1")

    service = CheckpointService(checkpointer=saver)
    result = await service.load_checkpoint(
        thread_id=thread_id, checkpoint_id="00000000-0000-0000-0000-000000000000"
    )

    assert result is None


async def test_load_checkpoint_unknown_thread_returns_none(real_postgres_saver) -> None:
    """A thread with no checkpoints at all -- the genuine "not found" path,
    end to end against real Postgres.
    """
    from src.modules.hitl.adapters.checkpoint_service import CheckpointService

    saver, register = real_postgres_saver
    thread_id = register("p0b-checkpoint-restore-unknown-thread")

    service = CheckpointService(checkpointer=saver)
    result = await service.load_checkpoint(thread_id=thread_id, checkpoint_id=None)

    assert result is None


# -- Objective 7: full HITL prod-shape lifecycle through the real approve
# route, against a REAL AsyncPostgresSaver -- not a fake checkpoint service.
# This is the end-to-end proof that the checkpoint fix, the #640 canonical-
# selection fix, and the approve-route resume flow all compose correctly.


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


async def _seed_project_and_document(db: AsyncSession, tenant: Tenant) -> DocumentORM:
    project_id, document_id = uuid4(), uuid4()
    db.add(
        ProjectORM(
            id=project_id,
            tenant_id=tenant.id,
            name="Checkpoint Restore Hotfix Project",
            code="P0B-CKPT",
            start_date=datetime.now(),
        )
    )
    await db.commit()
    document = DocumentORM(
        id=document_id,
        tenant_id=tenant.id,
        project_id=project_id,
        document_type="contract",
        filename="checkpoint_restore.pdf",
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


async def test_full_prod_shape_lifecycle_through_real_checkpointer_and_approve_route(
    real_postgres_saver,
    authenticated_client: AsyncClient,
    app,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Objective 7: reuse the #640 prod-shape lifecycle (one item_id, four
    rows -- A: historical APPROVED, B: active PENDING with a real
    thread_id/checkpoint_id, C/D: legacy PENDING duplicates with none) but
    this time B's checkpoint is a REAL checkpoint written via
    AsyncPostgresSaver.aput(), loaded through the REAL (fixed)
    CheckpointService against the REAL saver -- not a fake checkpoint
    service. Approves through the exact route the UI uses
    (POST /queue/{item_id}/approve) and proves the entire chain: canonical
    B selected -> exact real checkpoint B loaded (no unpack error) ->
    decision recorded -> the SAME workflow resumes -> real N17/
    save_to_db_node executes -> analysis persists -> graph.completed ->
    document ANALYZED -- while A/C/D and the row count stay untouched.
    """
    saver, register = real_postgres_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed_project_and_document(db, tenant)
    thread_id = register(f"document:{document.id}:analysis")
    now = datetime.now(UTC).replace(tzinfo=None)

    resume_state = {
        "project_id": str(document.project_id),
        "tenant_id": str(tenant.id),
        "document_id": str(document.id),
        "extracted_risks": [],
        "extracted_wbs": [],
        "coherence_score": 91,
        "coherence_breakdown": {"overall": 91},
        "single_document_assessment": {
            "single_document_assessment": {
                "evidence_granularity": "document",
                "proof_marker": "p0b-checkpoint-restore-health-readable",
            }
        },
        "messages": [],
        "node_results": [],
    }

    # Write B's checkpoint for real, through the real AsyncPostgresSaver --
    # this IS what run_orchestration durably persists at the interrupt.
    from langgraph.checkpoint.base import empty_checkpoint

    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {"__root__": resume_state}
    checkpoint["channel_versions"] = {"__root__": "1"}
    await saver.aput(
        {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}},
        checkpoint,
        {"source": "loop", "step": 0, "parents": {}},
        {"__root__": "1"},
    )
    checkpoint_id = str(checkpoint["id"])

    row_d = _review_row(
        tenant_id=tenant.id, project_id=document.project_id, document_id=document.id,
        status=ReviewStatus.PENDING_REVIEW_REQUIRED, thread_id=None, checkpoint_id=None,
        created_at=now - timedelta(hours=3),
    )
    row_c = _review_row(
        tenant_id=tenant.id, project_id=document.project_id, document_id=document.id,
        status=ReviewStatus.PENDING_REVIEW_REQUIRED, thread_id=None, checkpoint_id=None,
        created_at=now - timedelta(hours=2),
    )
    row_b = _review_row(
        tenant_id=tenant.id, project_id=document.project_id, document_id=document.id,
        status=ReviewStatus.PENDING_REVIEW_REQUIRED, thread_id=thread_id, checkpoint_id=checkpoint_id,
        created_at=now - timedelta(minutes=14),
    )
    row_a = _review_row(
        tenant_id=tenant.id, project_id=document.project_id, document_id=document.id,
        status=ReviewStatus.APPROVED, thread_id=thread_id, checkpoint_id="historical-checkpoint-unrelated",
        created_at=now, approved_at=now,
    )
    db.add_all([row_a, row_b, row_c, row_d])
    await db.commit()
    for row in (row_a, row_b, row_c, row_d):
        await db.refresh(row)
    original_a_approved_at = row_a.approved_at

    def _real_resume_use_case() -> ResumeWorkflowUseCase:
        from src.modules.hitl.adapters.checkpoint_service import CheckpointService

        repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=tenant.id)
        return ResumeWorkflowUseCase(
            review_queue_repo=repo,
            checkpoint_service=CheckpointService(checkpointer=saver),
            graph_app=_FakeResumingGraphApp(resume_state),
        )

    app.dependency_overrides[get_resume_workflow_use_case] = _real_resume_use_case

    response = await authenticated_client.post(
        f"/api/v1/hitl/queue/{row_b.item_id}/approve",
        json={},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["row_id"] == str(row_b.id), "the real checkpoint load must have resolved canonical row B"
    assert body["current_status"] == "APPROVED"

    analyses = (
        await db.execute(select(Analysis).where(Analysis.project_id == document.project_id))
    ).scalars().all()
    assert len(analyses) == 1, "N17/save_to_db_node must have run for real exactly once"
    assert (
        analyses[0].result_json.get("single_document_assessment", {}).get("proof_marker")
        == "p0b-checkpoint-restore-health-readable"
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

    refreshed_b = await db.get(ReviewItemORM, row_b.id)
    await db.refresh(refreshed_b)
    assert refreshed_b.current_status == ReviewStatus.APPROVED.value

    refreshed_a = await db.get(ReviewItemORM, row_a.id)
    await db.refresh(refreshed_a)
    assert refreshed_a.current_status == ReviewStatus.APPROVED.value
    assert refreshed_a.approved_at == original_a_approved_at, "historical row A must not be re-mutated"

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
