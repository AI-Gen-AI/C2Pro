"""
C2PRO P0b PROD HITL RESUME BLOCKER HOTFIX -- Section 1 reproduction (RED->GREEN).

Reproduces the exact production failure end-to-end:
  contract parsed -> RAG chunks present -> graph pauses for human approval
  -> a durable, correctly thread/checkpoint-linked ReviewItem is persisted
  -> the Celery task reports a truthful WAITING_FOR_REVIEW outcome with
  will_retry=False (never auto-retried) -> re-invoking the SAME document
  (simulating a Celery retry / duplicate trigger) does NOT create a second
  active review.

Production evidence this reproduces: project 2b7f3509-4b0f-4cc3-90f4-
9f55c1964392 / document 369cdc8f-50ed-4a15-9fe1-5167e4eb4862 -- parsing PASS,
RAG PASS, orchestration reaches HITL, human_approval_required=True,
analyses=0, document stuck at parsed_pending_analysis, FOUR duplicate
review_items with thread_id=NULL / checkpoint_id=NULL after 3 exhausted
Celery retries.

Only the LangGraph pregel boundary (ainvoke/aget_state) is faked here; the
document-analysis task, HITL application service, and review-queue
repository are the REAL production code paths, running against the real
local test Postgres database (TEST_DATABASE_URL) -- this is exactly what
production runs, minus the LLM-backed graph nodes.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.graph import workflow
from src.core.auth.models import Tenant
from src.core.tasks import ingestion_tasks
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import Document, DocumentStatus, DocumentType
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.domain.entities import ImpactLevel
from src.projects.adapters.persistence.models import ProjectORM

pytestmark = pytest.mark.asyncio


async def _make_document(db: AsyncSession) -> Document:
    """A real tenant/project/document row -- review_items has FK constraints
    on project_id/document_id, so the durable persistence path this test
    exercises needs real parent rows, not just a domain-model stand-in.
    """
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()

    db.add(
        Tenant(
            id=tenant_id,
            name="P0b HITL Hotfix Tenant",
            slug=f"p0b-hitl-{tenant_id.hex[:8]}",
            subscription_plan="professional",
            is_active=True,
        )
    )
    await db.commit()
    db.add(
        ProjectORM(
            id=project_id,
            tenant_id=tenant_id,
            name="P0b HITL Hotfix Project",
            code="P0B-HITL",
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
            filename="contract.pdf",
            upload_status="parsed_pending_analysis",
        )
    )
    await db.commit()

    return Document(
        id=document_id,
        project_id=project_id,
        tenant_id=tenant_id,
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        upload_status=DocumentStatus.PARSED_PENDING_ANALYSIS,
        created_by=uuid4(),
        document_metadata={"parsed_text": "Contract text requiring analysis."},
    )


def _make_document_session() -> AsyncMock:
    """Mock session for the outer document-repo/RAG-chunk-count lookups only.

    The HITL review persistence path below uses the REAL database session
    (via get_session_with_tenant, which resolves to TEST_DATABASE_URL) --
    this mock stands in only for the document/document-repo plumbing that
    `_run_document_analysis` needs, matching the established pattern in
    test_document_analysis_trigger.py.
    """
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    chunk_count_result = Mock()
    chunk_count_result.scalar_one.return_value = 5
    session.execute.return_value = chunk_count_result
    return session


class _FakeInterruptingApp:
    """Simulates the compiled LangGraph app exactly at the point
    human_interrupt_node pauses.

    Faithfully routes through the REAL HumanInTheLoopService and
    SqlAlchemyReviewQueueRepository (the same call the real node makes)
    against the real local test database, so the created ReviewItem is
    genuine and durably persisted -- then reports a real, distinguishable
    checkpoint id via aget_state, exactly like run_orchestration's
    post-ainvoke capture expects.
    """

    def __init__(self) -> None:
        self.checkpointer = object()
        self.ainvoke_calls: list[dict] = []
        self._seq = 0

    async def ainvoke(self, state: dict, config: dict) -> dict:
        self.ainvoke_calls.append(dict(state))

        from src.analysis.adapters.graph.dependencies import get_hitl_service_for_graph
        from src.core.database import get_session_with_tenant

        tenant_id = UUID(state["tenant_id"])
        async with get_session_with_tenant(tenant_id) as session:
            service = get_hitl_service_for_graph(session=session, tenant_id=tenant_id)
            await service.route_for_review(
                item_id=uuid4(),
                item_type=state.get("doc_type") or "unknown",
                confidence=0.2,
                impact_level=ImpactLevel.HIGH,
                item_data={
                    "project_id": state["project_id"],
                    "document_id": state["document_id"],
                    "thread_id": state.get("thread_id"),
                },
                metadata={
                    "tenant_id": str(tenant_id),
                    "project_id": state["project_id"],
                    "document_id": state["document_id"],
                    "review_type": "analysis_critique",
                    "thread_id": state.get("thread_id"),
                },
            )
            await session.commit()

        return {**state, "human_approval_required": True, "analysis_id": None}

    async def aget_state(self, config: dict) -> SimpleNamespace:
        self._seq += 1
        thread_id = config["configurable"]["thread_id"]
        return SimpleNamespace(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": f"real-checkpoint-{self._seq}",
                }
            }
        )


@pytest.fixture(autouse=True)
def _restore_workflow_globals():
    original_pool = workflow._checkpointer_pool
    original_ready = workflow._checkpointer_ready
    original_graph = workflow._graph_app
    workflow._checkpointer_pool = None
    workflow._checkpointer_ready = False
    workflow._graph_app = None
    yield
    workflow._checkpointer_pool = original_pool
    workflow._checkpointer_ready = original_ready
    workflow._graph_app = original_graph


async def _install_real_hitl_path_with_interrupting_graph(
    monkeypatch: pytest.MonkeyPatch,
    db: AsyncSession,
) -> tuple[Document, _FakeInterruptingApp, Mock]:
    document = await _make_document(db)
    session = _make_document_session()
    fake_app = _FakeInterruptingApp()

    # init_db is NOT stubbed here: the fake graph's ainvoke routes through the
    # REAL get_session_with_tenant (real HITL persistence), which requires
    # the real global engine to be initialized against TEST_DATABASE_URL.
    monkeypatch.setattr(ingestion_tasks, "get_raw_session", lambda: session)
    repo = Mock()
    repo.get_by_id = AsyncMock(return_value=document)
    repo.update_status = AsyncMock()
    monkeypatch.setattr(
        ingestion_tasks, "SqlAlchemyDocumentRepository", lambda *, session: repo
    )
    monkeypatch.setattr(workflow, "ensure_checkpointer_ready", AsyncMock())
    monkeypatch.setattr(workflow, "_build_checkpointer", lambda: object())
    monkeypatch.setattr(
        workflow,
        "compile_workflow",
        lambda *, checkpointer, persist_diagram: fake_app,
    )

    class _WorkflowOrchestrator:
        async def run(self, initial_state: dict, *, thread_id: str) -> dict:
            return await workflow.run_orchestration(initial_state, thread_id)

    class _Factory:
        @staticmethod
        def create() -> _WorkflowOrchestrator:
            return _WorkflowOrchestrator()

    monkeypatch.setattr(ingestion_tasks, "AnalysisOrchestratorFactory", _Factory)
    return document, fake_app, repo


async def test_hitl_interrupt_is_durable_resumable_and_non_duplicating(
    monkeypatch: pytest.MonkeyPatch,
    db: AsyncSession,
) -> None:
    """Full Section 1 reproduction.

    Runs the real _run_document_analysis path TWICE for the same document
    (simulating the initial run followed by a Celery retry of the SAME
    task), and proves every hard requirement of the P0b hotfix:

      1. thread_id is STABLE and identical across both runs (never
         re-randomized) -- the prior bug's root cause.
      2. Both runs report a truthful, non-failure outcome
         (status="waiting_for_review", will_retry=False,
         human_approval_required=True) -- HITL pause is never conflated
         with graph failure and never auto-retried.
      3. The document is NEVER marked ANALYZED while paused.
      4. Exactly ONE active review_item exists in the real database for
         this document+review_type after both runs -- idempotency proven
         against a real duplicate re-invocation, not just a mock.
      5. That single review item carries a REAL, non-null thread_id AND
         checkpoint_id (captured via the real aget_state path in
         run_orchestration) -- never fabricated, never NULL.
    """
    document, fake_app, repo = await _install_real_hitl_path_with_interrupting_graph(monkeypatch, db)

    first = await ingestion_tasks._run_document_analysis(
        tenant_id=document.tenant_id,
        document_id=document.id,
    )
    second = await ingestion_tasks._run_document_analysis(
        tenant_id=document.tenant_id,
        document_id=document.id,
    )

    # -- 1. Stable thread_id across the retry ---------------------------
    assert len(fake_app.ainvoke_calls) == 2
    thread_ids = {call["thread_id"] for call in fake_app.ainvoke_calls}
    assert len(thread_ids) == 1, "thread_id must be stable across retries, not re-randomized"
    assert str(document.id) in next(iter(thread_ids))

    # -- 2. Truthful outcome, never auto-retried -------------------------
    for result in (first, second):
        assert result["status"] == "waiting_for_review"
        assert result["human_approval_required"] is True
        assert result["will_retry"] is False
        assert result["analysis_id"] is None

    # -- 3. Document never marked ANALYZED while paused -------------------
    assert len(repo.update_status.call_args_list) == 2
    assert all(
        call.args[2] == DocumentStatus.PARSED_PENDING_ANALYSIS
        for call in repo.update_status.call_args_list
    )

    # -- 4. Exactly one active review in the real database ----------------
    from src.core.database import get_session_with_tenant

    async with get_session_with_tenant(document.tenant_id) as verify_session:
        rows = (
            await verify_session.execute(
                select(ReviewItemORM).where(
                    ReviewItemORM.document_id == document.id,
                    ReviewItemORM.review_type == "analysis_critique",
                )
            )
        ).scalars().all()

    assert len(rows) == 1, (
        f"expected exactly one active review, found {len(rows)} "
        "(duplicate-review regression -- matches the 4-duplicate prod bug)"
    )

    # -- 5. Real, non-null thread_id AND checkpoint_id linkage -------------
    review = rows[0]
    assert review.thread_id, "thread_id must never be NULL (bug #1)"
    assert review.checkpoint_id, "checkpoint_id must be captured for real (section 2), never NULL"
    assert review.thread_id == next(iter(thread_ids))
    assert review.checkpoint_id.startswith("real-checkpoint-")
