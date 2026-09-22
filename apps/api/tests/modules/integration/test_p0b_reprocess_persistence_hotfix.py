"""
C2PRO P0b PROD HITL PERSISTENCE + REPROCESS IDEMPOTENCY HOTFIX.

Reproduces the exact production shape and proves the full, corrected
lifecycle end to end:

  4 legacy duplicate reviews exist (item_id=document_id, thread_id=NULL,
  checkpoint_id=NULL, review_type=analysis_critique, all PENDING -- exactly
  what production has for project 2b7f3509-4b0f-4cc3-90f4-9f55c1964392 /
  document 369cdc8f-50ed-4a15-9fe1-5167e4eb4862)
  -> initial RAG ingestion (N chunks)
  -> reprocess / graph run finds the existing active review (adopts a
     legacy row instead of creating a 5th) -> stable thread_id assigned
     -> a REAL LangGraph checkpoint id is captured and persisted onto that
     SAME row (this is the exact step that previously raised inside
     SqlAlchemyReviewQueueRepository.update_review_item -- see
     src/modules/hitl/adapters/persistence/repository.py's row_id fix)
  -> exactly one active, checkpoint-linked review; the other 3 legacy rows
     are untouched, and no new (5th) row was created
  -> task reports waiting_for_review, will_retry=False
  -> RAG re-ingestion (simulating the reprocess's own RAG step) leaves
     chunk count stable at N, not 2N
  -> approve through ResumeWorkflowUseCase -> the real N17 save_to_db_node
     executes -> an analyses row persists -> a real graph.completed
     ProjectEvent is emitted -> the document becomes ANALYZED -> the
     persisted single_document_assessment fragment (Health's read model)
     is readable in analyses.result_json.

Only the LangGraph pregel/checkpoint boundary is faked; every other step is
the real production code, against the real local test database.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.graph import workflow
from src.core.auth.models import Tenant
from src.core.tasks import ingestion_tasks
from src.documents.adapters.persistence.models import DocumentChunkORM, DocumentORM
from src.documents.adapters.rag import rag_service as rag_service_module
from src.documents.adapters.rag.rag_service import RagService
from src.documents.domain.models import Document, DocumentStatus, DocumentType
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus
from src.projects.adapters.persistence.models import ProjectORM

pytestmark = pytest.mark.asyncio


def _fake_embed(dimension: int = 1536):
    async def _embed(texts: list[str]) -> list[list[float]]:
        return [[0.001 * (i + 1)] * dimension for i, _ in enumerate(texts)]

    return _embed


async def _seed_document(db: AsyncSession) -> Document:
    tenant_id, project_id, document_id = uuid4(), uuid4(), uuid4()

    db.add(
        Tenant(
            id=tenant_id,
            name="P0b Reprocess Hotfix Tenant",
            slug=f"p0b-reproc-{tenant_id.hex[:8]}",
            subscription_plan="professional",
            is_active=True,
        )
    )
    await db.commit()
    db.add(
        ProjectORM(
            id=project_id,
            tenant_id=tenant_id,
            name="P0b Reprocess Hotfix Project",
            code="P0B-REPROC",
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


async def _seed_legacy_duplicate_reviews(db: AsyncSession, document: Document, count: int = 4) -> None:
    """Exactly the production shape: item_id=document_id (per
    human_interrupt_node), thread_id=NULL, checkpoint_id=NULL,
    review_type=analysis_critique, all PENDING_REVIEW_REQUIRED.
    """
    for i in range(count):
        db.add(
            ReviewItemORM(
                id=uuid4(),
                item_id=document.id,
                item_type="contract",
                current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
                confidence=0.0,
                impact_level=ImpactLevel.HIGH,
                tenant_id=document.tenant_id,
                sla_due_date=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=3),
                item_data={},
                review_metadata={},
                checkpoint_id=None,
                thread_id=None,
                project_id=document.project_id,
                document_id=document.id,
                review_type="analysis_critique",
                created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=count - i),
            )
        )
    await db.commit()


def _make_document_session() -> AsyncMock:
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    chunk_count_result = Mock()
    chunk_count_result.scalar_one.return_value = 5
    session.execute.return_value = chunk_count_result
    return session


class _FakeInterruptingApp:
    """Simulates the compiled LangGraph app exactly at the point
    human_interrupt_node pauses -- routes through the REAL
    HumanInTheLoopService/SqlAlchemyReviewQueueRepository against the real
    local test database, then reports a real, distinguishable checkpoint id
    via aget_state.
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
                item_id=UUID(state["document_id"]),
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


class _FakeResumingGraphApp:
    """Resumes by invoking the REAL N17 save_to_db_node."""

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


def _install_graph(monkeypatch: pytest.MonkeyPatch, document: Document, fake_app) -> Mock:
    session = _make_document_session()
    monkeypatch.setattr(ingestion_tasks, "get_raw_session", lambda: session)
    repo = Mock()
    repo.get_by_id = AsyncMock(return_value=document)
    repo.update_status = AsyncMock()
    monkeypatch.setattr(ingestion_tasks, "SqlAlchemyDocumentRepository", lambda *, session: repo)
    monkeypatch.setattr(workflow, "ensure_checkpointer_ready", AsyncMock())
    monkeypatch.setattr(workflow, "_build_checkpointer", lambda: object())
    monkeypatch.setattr(
        workflow, "compile_workflow", lambda *, checkpointer, persist_diagram: fake_app
    )

    class _WorkflowOrchestrator:
        async def run(self, initial_state: dict, *, thread_id: str) -> dict:
            return await workflow.run_orchestration(initial_state, thread_id)

    class _Factory:
        @staticmethod
        def create() -> _WorkflowOrchestrator:
            return _WorkflowOrchestrator()

    monkeypatch.setattr(ingestion_tasks, "AnalysisOrchestratorFactory", _Factory)
    return repo


async def test_full_prod_shape_lifecycle_legacy_adoption_rag_idempotency_and_resume(
    monkeypatch: pytest.MonkeyPatch,
    db: AsyncSession,
) -> None:
    from src.analysis.adapters.persistence.models import Analysis
    from src.core.database import get_session_with_tenant
    from src.modules.hitl.adapters.persistence.repository import (
        SqlAlchemyReviewQueueRepository,
    )
    from src.modules.hitl.application.resume_workflow_use_case import (
        ResumeWorkflowRequest,
        ResumeWorkflowUseCase,
        WorkflowDecision,
    )
    from src.temporal.adapters.persistence.models import ProjectEventORM

    document = await _seed_document(db)
    await _seed_legacy_duplicate_reviews(db, document, count=4)

    # -- Initial RAG ingestion (pre-existing N chunks, matching prod's 23) --
    monkeypatch.setattr(rag_service_module, "_embed_texts", _fake_embed())
    rag = RagService(db_session=db)
    text_content = ("Contract clause text for RAG ingestion. " * 60).strip()
    initial_chunk_count = await rag.ingest_document(
        tenant_id=document.tenant_id,
        document_id=document.id,
        project_id=document.project_id,
        text_content=text_content,
    )
    assert initial_chunk_count > 0

    # -- Reprocess / graph run: must find and adopt an existing legacy row -
    fake_app = _FakeInterruptingApp()
    repo_mock = _install_graph(monkeypatch, document, fake_app)

    result = await ingestion_tasks._run_document_analysis(
        tenant_id=document.tenant_id, document_id=document.id
    )
    assert result["status"] == "waiting_for_review"
    assert result["human_approval_required"] is True
    assert result["will_retry"] is False
    assert repo_mock.update_status.call_args.args[2] == DocumentStatus.PARSED_PENDING_ANALYSIS

    async with get_session_with_tenant(document.tenant_id) as verify_session:
        all_reviews = (
            await verify_session.execute(
                select(ReviewItemORM).where(ReviewItemORM.document_id == document.id)
            )
        ).scalars().all()

    # No 5th review created -- the reprocess adopted one of the 4 legacy rows.
    assert len(all_reviews) == 4, "reprocess must not create a new duplicate review row"
    with_checkpoint = [r for r in all_reviews if r.checkpoint_id]
    assert len(with_checkpoint) == 1, "exactly one active, checkpoint-linked review"
    adopted = with_checkpoint[0]
    assert adopted.thread_id == f"document:{document.id}:analysis"
    assert adopted.checkpoint_id.startswith("real-checkpoint-")
    untouched = [r for r in all_reviews if r.id != adopted.id]
    assert len(untouched) == 3
    assert all(r.thread_id is None and r.checkpoint_id is None for r in untouched), (
        "the other legacy rows must be left exactly as they were"
    )

    # -- RAG reprocess idempotency: re-ingest, chunk count stays stable -----
    reprocessed_chunk_count = await rag.ingest_document(
        tenant_id=document.tenant_id,
        document_id=document.id,
        project_id=document.project_id,
        text_content=text_content,
    )
    assert reprocessed_chunk_count == initial_chunk_count

    async with get_session_with_tenant(document.tenant_id) as verify_session:
        chunk_rows = (
            await verify_session.execute(
                select(DocumentChunkORM).where(DocumentChunkORM.document_id == document.id)
            )
        ).scalars().all()
    assert len(chunk_rows) == initial_chunk_count, (
        f"RAG reprocess must stay at {initial_chunk_count} chunks, "
        f"found {len(chunk_rows)} (production regression was 23 -> 46)"
    )

    # -- Approve the adopted review through ResumeWorkflowUseCase ----------
    review_repo = SqlAlchemyReviewQueueRepository(session=db, tenant_id=document.tenant_id)
    resume_state = {
        "project_id": str(document.project_id),
        "tenant_id": str(document.tenant_id),
        "document_id": str(document.id),
        "extracted_risks": [],
        "extracted_wbs": [],
        "coherence_score": 88,
        "coherence_breakdown": {"overall": 88},
        "single_document_assessment": {
            "single_document_assessment": {
                "evidence_granularity": "document",
                "proof_marker": "p0b-reprocess-persist-hotfix-health-readable",
            }
        },
        "messages": [],
        "node_results": [],
    }
    resuming_app = _FakeResumingGraphApp(resume_state)
    checkpoint_service = _FakeResumeCheckpointService(resume_state)
    use_case = ResumeWorkflowUseCase(
        review_queue_repo=review_repo,
        checkpoint_service=checkpoint_service,
        graph_app=resuming_app,
    )

    response = await use_case.execute(
        review_id=adopted.item_id,
        request=ResumeWorkflowRequest(
            decision=WorkflowDecision.APPROVE,
            feedback="Approved after legacy-review adoption.",
        ),
    )
    assert response.status == "resumed"
    assert checkpoint_service.loaded == [(adopted.thread_id, adopted.checkpoint_id)]
    await db.commit()

    # -- N17 executed for real: an analyses row persisted -------------------
    async with get_session_with_tenant(document.tenant_id) as verify_session:
        analyses = (
            await verify_session.execute(
                select(Analysis).where(Analysis.project_id == document.project_id)
            )
        ).scalars().all()
    assert len(analyses) == 1
    analysis_row = analyses[0]

    # -- Health becomes readable ---------------------------------------------
    assert (
        analysis_row.result_json.get("single_document_assessment", {}).get("proof_marker")
        == "p0b-reprocess-persist-hotfix-health-readable"
    )

    # -- graph.completed emitted for real -------------------------------------
    async with get_session_with_tenant(document.tenant_id) as verify_session:
        events = (
            await verify_session.execute(
                select(ProjectEventORM).where(
                    ProjectEventORM.project_id == document.project_id,
                    ProjectEventORM.event_type == "graph.completed",
                )
            )
        ).scalars().all()
    assert len(events) == 1
    assert events[0].payload["analysis_id"] == str(analysis_row.id)

    # -- Document becomes ANALYZED --------------------------------------------
    async with get_session_with_tenant(document.tenant_id) as verify_session:
        refreshed_document = (
            await verify_session.execute(select(DocumentORM).where(DocumentORM.id == document.id))
        ).scalar_one()
    assert refreshed_document.upload_status == DocumentStatus.ANALYZED.value

    # -- The adopted review is APPROVED; the 3 untouched legacy rows remain
    # exactly as they were (never mutated, never deleted).
    async with get_session_with_tenant(document.tenant_id) as verify_session:
        final_reviews = (
            await verify_session.execute(
                select(ReviewItemORM).where(ReviewItemORM.document_id == document.id)
            )
        ).scalars().all()
    assert len(final_reviews) == 4
    final_by_id = {r.id: r for r in final_reviews}
    assert final_by_id[adopted.id].current_status == ReviewStatus.APPROVED.value
    for legacy_row in untouched:
        assert final_by_id[legacy_row.id].current_status == ReviewStatus.PENDING_REVIEW_REQUIRED.value
        assert final_by_id[legacy_row.id].thread_id is None
        assert final_by_id[legacy_row.id].checkpoint_id is None
