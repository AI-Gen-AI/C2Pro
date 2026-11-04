"""ProjectGraph integration seam: real graph order, scoped source inputs, durable output."""
from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.domain.node_result import NodeStatus
from src.coherence.models import Clause, EnrichedCoherenceResult


class Snapshots:
    def __init__(self):
        self.snapshots = []

    async def latest(self, project_id, tenant_id):
        return self.snapshots[-1] if self.snapshots else None

    async def append_snapshot(self, snapshot):
        self.snapshots.append(snapshot)
        return snapshot


@pytest.mark.asyncio
async def test_projectgraph_propagates_current_evidence_into_durable_review_route(monkeypatch):
    from src.analysis.adapters.graph import project_graph
    from langchain_core.tracers import context as tracing
    from langsmith import run_helpers, utils

    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.setattr(run_helpers, "get_tracing_context", lambda: {
        "parent": None, "project_name": None, "enabled": False,
        "metadata": {}, "tags": [],
    })
    monkeypatch.setattr(utils, "tracing_is_enabled", lambda: False)
    monkeypatch.setattr(tracing, "_tracing_v2_is_enabled", lambda: False)

    @contextmanager
    def disabled_tracing(*_args, **_kwargs):
        yield None

    monkeypatch.setattr(tracing, "tracing_v2_enabled", disabled_tracing)

    captured = {}

    async def fake_evaluator(clauses, project_id, *, config, seed_signals, seed_coverage):
        captured["clauses"] = clauses
        captured["schedule"] = config.schedule_planned_finish
        return EnrichedCoherenceResult(
            overall_score=None, score_reason="insufficient_verified_dimensions",
            score_missing_dimensions=["BUDGET"],
        )

    async def llm_on(_tenant_id):
        return True

    async def fake_reconcile(_state):
        return SimpleNamespace(records_by_finding_key={})

    monkeypatch.setattr(project_graph, "evaluate_coherence_async", fake_evaluator)
    monkeypatch.setattr(project_graph, "is_coherence_llm_enabled", llm_on)
    monkeypatch.setattr(project_graph, "_reconcile_project_graph_alerts", fake_reconcile)

    snaps = Snapshots()
    contract_id = str(uuid4())
    schedule_id = str(uuid4())
    state = {
        "project_id": uuid4(),
        "tenant_id": uuid4(),
        "trigger_event_id": None,
        "previous_snapshot_id": None,
        "changed_artifact_ids": [],
        "artifacts": [
            DocumentArtifact(document_id=contract_id, doc_type="contract"),
            DocumentArtifact(document_id=schedule_id, doc_type="schedule"),
        ],
        "input_source_clauses": [
            Clause(
                id=str(uuid4()), text="Contractor shall deliver before 2027-06-01.",
                data={"document_id": contract_id, "document_type": "contract"},
            ),
            Clause(
                id=str(uuid4()), text="Project completion scheduled for 2027-06-20.",
                data={"document_id": schedule_id, "document_type": "schedule"},
            ),
        ],
        "schedule_planned_finish": {
            "document_id": schedule_id,
            "planned_finish": "2027-06-20",
        },
        "coherence_result": None,
        "impact_result": None,
        "health_result": None,
        "snapshot_id": None,
        "node_results": [],
        "db_session": object(),
        "snapshot_repository": snaps,
    }
    result = await project_graph.build_project_graph().ainvoke(state)

    assert len(captured["clauses"]) == 2
    assert captured["schedule"]["document_id"] == schedule_id
    by_node = {item.node: item for item in result["node_results"]}
    assert by_node["cross_doc_coherence"].status is NodeStatus.OK
    assert by_node["write_snapshot"].status is NodeStatus.OK
    assert by_node["alert_correlation"].status is NodeStatus.OK
    assert by_node["hitl_routing"].status is NodeStatus.OK
    assert len(snaps.snapshots) == 1
    assert snaps.snapshots[0].coherence_subscore is None
    assert result["snapshot_id"] == snaps.snapshots[0].snapshot_id
