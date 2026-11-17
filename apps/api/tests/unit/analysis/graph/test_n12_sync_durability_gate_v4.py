"""V4: N12 budget escrow changes LangGraph durability only when opted in."""
from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.analysis.adapters.graph import workflow


class RecordingGraph:
    def __init__(self):
        self.kwargs: list[dict] = []
        self.states: list[dict] = []

    async def ainvoke(self, state, config, **kwargs):
        self.states.append(state)
        self.kwargs.append(kwargs)
        return {
            "project_id": state.get("project_id"),
            "doc_type": "contract",
            "human_approval_required": False,
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("flag,uses_sync", [
    ("1", True), ("0", False), ("", False),
])
async def test_n12_escrow_flag_requires_sync_checkpoint_commit(
    monkeypatch: pytest.MonkeyPatch, flag: str, uses_sync: bool
):
    graph = RecordingGraph()
    monkeypatch.setattr(workflow, "get_graph_app", lambda: graph)
    monkeypatch.setattr(workflow, "ensure_checkpointer_ready", AsyncMock())
    monkeypatch.setenv("C2PRO_N12_CHECKPOINT_ESCROW", flag)

    initial = {
        "project_id": str(uuid4()),
        "document_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "doc_type": "contract",
    }
    result = await workflow.run_orchestration(initial, thread_id="unique-test-thread")
    assert result["human_approval_required"] is False
    assert graph.states == [initial]
    assert len(graph.kwargs) == 1
    if uses_sync:
        assert graph.kwargs[0] == {"durability": "sync"}
    else:
        assert graph.kwargs[0] == {}


@pytest.mark.asyncio
async def test_unset_budget_flag_preserves_existing_graph_invocation(monkeypatch):
    graph = RecordingGraph()
    monkeypatch.setattr(workflow, "get_graph_app", lambda: graph)
    monkeypatch.setattr(workflow, "ensure_checkpointer_ready", AsyncMock())
    monkeypatch.delenv("C2PRO_N12_CHECKPOINT_ESCROW", raising=False)
    await workflow.run_orchestration(
        {"project_id": str(uuid4()), "doc_type": "other"},
        thread_id="legacy-mode",
    )
    assert graph.kwargs == [{}]
