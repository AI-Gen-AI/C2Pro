"""Reuse the canonical Alerts reconciliation without inventing review decisions."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.analysis.domain.node_result import NodeStatus
from src.coherence.models import EnrichedCoherenceResult


@pytest.mark.asyncio
async def test_projectgraph_alerts_reuse_review_route(monkeypatch):
    from src.analysis.adapters.graph import project_graph

    async def fake_reconcile(state):
        assert state["coherence_evaluation"] is not None
        return SimpleNamespace(
            records_by_finding_key={
                "known-finding": SimpleNamespace(
                    alert_metadata={"requires_human_review": True},
                ),
            },
        )

    monkeypatch.setattr(project_graph, "_reconcile_project_graph_alerts", fake_reconcile)
    state = {
        "project_id": uuid4(),
        "tenant_id": uuid4(),
        "db_session": object(),
        "coherence_evaluation": EnrichedCoherenceResult(
            overall_score=None, score_reason="unassessed",
        ),
    }
    correlation = await project_graph.alert_correlation(state)
    assert correlation["node_results"][0].status is NodeStatus.OK
    assert correlation["correlated_alert_count"] == 1
    assert correlation["alert_review_required_count"] == 1

    routed = project_graph.hitl_routing({**state, **correlation})
    assert routed["node_results"][0].status is NodeStatus.OK
    assert routed["node_results"][0].data["route"] == "existing_alert_review"
    assert routed["node_results"][0].data["auto_approval"] is False


@pytest.mark.asyncio
async def test_projectgraph_failed_alert_reconciliation_is_not_silent(monkeypatch):
    from src.analysis.adapters.graph import project_graph

    async def fail(_state):
        raise RuntimeError("alerts unavailable")

    monkeypatch.setattr(project_graph, "_reconcile_project_graph_alerts", fail)
    state = {
        "project_id": uuid4(),
        "tenant_id": uuid4(),
        "db_session": object(),
        "coherence_evaluation": EnrichedCoherenceResult(overall_score=None),
    }
    result = await project_graph.alert_correlation(state)
    assert result["node_results"][0].status is NodeStatus.FAILED
    assert "alerts unavailable" in result["node_results"][0].error.message
    assert project_graph.hitl_routing({**state, **result})["node_results"][0].status is NodeStatus.SKIPPED
