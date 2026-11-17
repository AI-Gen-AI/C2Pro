"""N12 budget authorization needs a real matching checkpoint, not a claim."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.analysis.adapters.ai.n12_checkpoint_escrow_port import (
    N12CheckpointIdentityError,
)
from src.analysis.adapters.graph import workflow
from src.analysis.adapters.graph.n12_checkpoint_witness import (
    verify_n12_durable_predecessor,
)

SOURCE = "Source: The supplier shall publish daily operational reports in SLA-A."


def _state():
    return {
        "tenant_id": str(uuid4()),
        "project_id": str(uuid4()),
        "document_id": str(uuid4()),
        "document_revision_id": str(uuid4()),
        "thread_id": str(uuid4()),
        "retry_count": 0,
        "doc_type": "other",
        "extracted_risks": [{"title": "Service delivery", "status": "PROPOSED"}],
        "extracted_wbs": [],
        "anonymized_text": SOURCE,
    }


class StoredGraph:
    def __init__(self, state, *, persistent=True, pending=("critique",)):
        # Stub saver TYPE only; individual unit test never claims genuine PG I/O.
        self.checkpointer = AsyncPostgresSaver(conn=None) if persistent else MemorySaver()
        self.state = state
        self.pending = pending
        self.invocations = 0

    async def aget_state(self, config):
        self.invocations += 1
        c = config["configurable"]
        return SimpleNamespace(
            config={"configurable": {
                **dict(c),
                "checkpoint_id": "checkpoint-001",
            }},
            values=deepcopy(self.state),
            next=self.pending,
        )


def _config(s, *, checkpoint="checkpoint-001"):
    return {
        "configurable": {
            "thread_id": s["thread_id"],
            "checkpoint_ns": "",
            "checkpoint_id": checkpoint,
        }
    }


@pytest.mark.asyncio
async def test_matching_postgres_checkpoint_snapshot_allows_idempotency_binding(monkeypatch):
    state = _state()
    graph = StoredGraph(state)
    monkeypatch.setattr(workflow, "get_graph_app", lambda: graph)
    await verify_n12_durable_predecessor(
        state=state, model_safe_source=SOURCE, config=_config(state),
    )
    assert graph.invocations == 1


@pytest.mark.asyncio
async def test_backend_saved_checkpoint_is_authoritative_when_runtime_omits_id(monkeypatch):
    state = _state()
    graph = StoredGraph(state)
    monkeypatch.setattr(workflow, "get_graph_app", lambda: graph)
    config = _config(state)
    config["configurable"].pop("checkpoint_id")
    await verify_n12_durable_predecessor(
        state=state, model_safe_source=SOURCE, config=config,
    )
    assert graph.invocations == 1


@pytest.mark.asyncio
async def test_n12_task_namespace_uses_persisted_root_predecessor(monkeypatch):
    state = _state()
    graph = StoredGraph(state)
    monkeypatch.setattr(workflow, "get_graph_app", lambda: graph)
    config = _config(state)
    config["configurable"]["checkpoint_ns"] = "critique:" + str(uuid4())
    config["configurable"].pop("checkpoint_id", None)
    await verify_n12_durable_predecessor(
        state=state, model_safe_source=SOURCE, config=config,
    )
    assert graph.invocations == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", [
    "missing_config", "wrong_thread", "memory_only",
    "missing_n12_route", "tenant_changed", "revision_changed",
    "risk_changed", "source_changed", "missing_revision", "wrong_checkpoint_ns",
])
async def test_budget_witness_fails_closed_on_missing_or_stale_state(monkeypatch, mutation):
    state = _state()
    graph = StoredGraph(state, persistent=mutation != "memory_only")
    monkeypatch.setattr(workflow, "get_graph_app", lambda: graph)
    config = _config(state)
    if mutation == "missing_config":
        config = None
    elif mutation == "wrong_thread":
        config["configurable"]["thread_id"] = str(uuid4())
    elif mutation == "missing_n12_route":
        graph.pending = ("save_to_db",)
    elif mutation == "tenant_changed":
        graph.state = dict(state, tenant_id=str(uuid4()))
    elif mutation == "revision_changed":
        graph.state = dict(state, document_revision_id=str(uuid4()))
    elif mutation == "risk_changed":
        graph.state = dict(state, extracted_risks=[{"title": "Different finding"}])
    elif mutation == "source_changed":
        graph.state = dict(state, anonymized_text="Different source text.")
    elif mutation == "missing_revision":
        state.pop("document_revision_id")
    elif mutation == "wrong_checkpoint_ns":
        config["configurable"]["checkpoint_ns"] = "other-graph"
        graph.state = state

    # Namespace case needs a genuine snapshot with a different namespace.
    if mutation == "wrong_checkpoint_ns":
        async def fake_get_state(_config):
            return SimpleNamespace(
                config={"configurable": {
                    "thread_id": state["thread_id"],
                    "checkpoint_id": "checkpoint-001",
                    "checkpoint_ns": "",
                }},
                values=state, next=("critique",),
            )
        graph.aget_state = fake_get_state

    with pytest.raises(N12CheckpointIdentityError):
        await verify_n12_durable_predecessor(
            state=state, model_safe_source=SOURCE, config=config,
        )


@pytest.mark.asyncio
async def test_no_budget_proof_cannot_fall_back_to_legacy_provider(monkeypatch):
    from src.analysis.adapters.graph import nodes

    class SilentProvider:
        tenant_id = None
        async def run_extraction(self, *args, **kwargs):
            raise AssertionError("provider must not be called")
        async def run_full_source_review(self, *args, **kwargs):
            raise AssertionError("provider must not be called")

    monkeypatch.setenv("C2PRO_N12_CHECKPOINT_ESCROW", "1")
    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    monkeypatch.setattr(nodes, "get_ai_service", lambda _tenant: SilentProvider())
    # A direct call has no LangGraph runtime config and no persisted identity.
    state = {
        **_state(), "messages": [], "node_results": [], "critique_notes": "",
        "human_approval_required": False, "confidence_score": 0.97,
        "citations": [], "risk_extraction_outcome": "OK",
    }
    result = await nodes.critique_node(state, config=None)
    assert result["human_approval_required"] is True
    assert result["confidence_score"] is None
    assert any(n.node == "critique" for n in result["node_results"])
