"""N12 graph-budget handoff with a REAL AsyncPostgresSaver on scratch PG.

Checks that runtime-injected checkpoint_id is read back from the saver, not
synthesized. The AI response is a stub; never claim real-model performance.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph
from psycopg_pool import AsyncConnectionPool

from src.analysis.adapters.graph import nodes, workflow
from src.analysis.adapters.graph.schema import ProjectState

# The built-in test_engine fixture is bound to the isolated Ops job database,
# including the project's canonical test-database ownership guard. No external
# DSN, production fallback, or optional skip path is allowed.
pytestmark = pytest.mark.asyncio

SOURCE = (
    "SLA-A. Provider shall make service status reports available on the "
    "customer portal by 08:00 each working day, unless customer data is missing."
)




def _state():
    return {
        "document_text": SOURCE,
        "anonymized_text": SOURCE,
        "tenant_id": str(uuid4()), "project_id": str(uuid4()),
        "document_id": str(uuid4()), "document_revision_id": str(uuid4()),
        "thread_id": "n12-checkpoint-" + str(uuid4()),
        "retry_count": 0, "doc_type": "other",
        "extracted_risks": [{
            "title": "Nonstandard SLA exposure", "confidence": 0.97,
            "source_quote": SOURCE,
            "source_quote_status": "VERIFIED",
        }],
        "extracted_wbs": [], "messages": [], "node_results": [],
        "confidence_score": 0.97,
        "human_approval_required": False, "critique_notes": "",
    }


class RecordingBudgetReview:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.governed_ids = []

    async def run_full_source_review(
        self, system_prompt, user_content, *, governed_request_id=None,
    ):
        self.governed_ids.append(governed_request_id)
        return {"status": "OK", "notes": "No issues found"}


async def _no_temporal_gate(_state):
    return None


def _graph_with_checkpointer(checkpointer):
    g = StateGraph(ProjectState)

    async def _previous(s: ProjectState):
        return {"doc_type": s["doc_type"]}

    g.add_node("extractor", _previous)
    g.add_node("critique", nodes.critique_node)
    g.set_entry_point("extractor")
    g.add_edge("extractor", "critique")
    g.add_edge("critique", END)
    return g.compile(checkpointer=checkpointer)


@pytest.mark.parametrize("real_postgres", [True, False])
async def test_n12_request_uses_saved_postgres_checkpoint_or_calls_no_provider(
    monkeypatch, real_postgres, test_engine,
):
    state = _state()
    service = RecordingBudgetReview(state["tenant_id"])
    # Test-only diagnostics: synthetic document and tenant IDs, no production
    # exception payload or provider call is ever logged.
    checkpoint_errors = []
    from src.analysis.adapters.graph import n12_checkpoint_witness
    original_witness = n12_checkpoint_witness.verify_n12_durable_predecessor

    async def witness_with_test_diagnostics(**kwargs):
        try:
            return await original_witness(**kwargs)
        except Exception as err:
            cause = err.__cause__
            checkpoint_errors.append({
                "error": type(err).__name__,
                "cause_type": type(cause).__name__ if cause else None,
                "cause": str(cause)[:350] if cause else None,
            })
            raise

    monkeypatch.setattr(
        n12_checkpoint_witness,
        "verify_n12_durable_predecessor",
        witness_with_test_diagnostics,
    )
    monkeypatch.setenv("C2PRO_N12_CHECKPOINT_ESCROW", "1")
    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    monkeypatch.setattr(nodes, "get_ai_service", lambda _tenant: service)
    monkeypatch.setattr(nodes, "_apply_temporal_review_gate", _no_temporal_gate)

    async def _no_error_db_writes(_state, _node_result):
        return None

    monkeypatch.setattr(nodes, "_persist_node_error", _no_error_db_writes)

    async def _invoke(saver):
        app = _graph_with_checkpointer(saver)
        monkeypatch.setattr(workflow, "get_graph_app", lambda: app)
        return await app.ainvoke(
            state, {"configurable": {"thread_id": state["thread_id"]}}
        )

    if real_postgres:
        # test_engine has already verified and initialized the authorized
        # scratch database. Reuse *that exact connection target* for saver.
        test_database_url = test_engine.url.render_as_string(hide_password=False)
        async with AsyncConnectionPool(
            conninfo=test_database_url.replace("postgresql+asyncpg://", "postgresql://"),
            min_size=0, max_size=3, kwargs={"autocommit": True},
        ) as pool:
            saver = AsyncPostgresSaver(conn=pool)
            await saver.setup()
            result = await _invoke(saver)
        assert len(service.governed_ids) == 1, checkpoint_errors or [
            {
                "node": str(getattr(n, "node", "")),
                "error_type": str(getattr(getattr(n, "error", None), "error_type", "")),
                "error_message": str(getattr(getattr(n, "error", None), "message", ""))[:160],
            }
            for n in result.get("node_results", [])
        ]
        assert service.governed_ids[0].startswith("n12c-")
        assert result["human_approval_required"] is True
        assert result["risk_pre_hitl_evidence_passed"] is True
    else:
        result = await _invoke(MemorySaver())
        assert service.governed_ids == []
        assert result["human_approval_required"] is True
        assert result["confidence_score"] is None
