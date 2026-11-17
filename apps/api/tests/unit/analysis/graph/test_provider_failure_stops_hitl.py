"""P0 regression: a failed N4 provider must not create a sham HITL candidate.

The independent multiprovider router is implemented in a separate gate;
this test covers failure semantics while all direct providers are unavailable.
"""
from __future__ import annotations

from src.analysis.adapters.graph.nodes import _mark_risk_extraction_honest_failure
from src.analysis.adapters.graph.workflow import build_workflow, route_after_risk_extraction


def test_n4_provider_failure_terminates_before_n12_and_hitl() -> None:
    state = {
        "confidence_score": 0.93,
        "extracted_risks": [{"title": "old risk"}],
        "human_approval_required": True,
        "messages": [],
    }

    _mark_risk_extraction_honest_failure(
        state,
        reason="AI risk extraction failed/empty — no risks extracted",
        exc=RuntimeError("provider_balance_unavailable"),
    )

    assert state["workflow_terminated"] is True
    assert state["termination_reason"] == "risk_extraction_unassessed"
    assert state["human_approval_required"] is False
    assert state["confidence_score"] is None
    assert state["extracted_risks"] == []
    assert route_after_risk_extraction(state) == "terminated"


def test_successful_or_unassessed_zero_findings_can_reach_critique() -> None:
    assert route_after_risk_extraction({"workflow_terminated": False}) == "critique"
    assert route_after_risk_extraction({}) == "critique"


def test_graph_compiles_with_early_failure_end() -> None:
    # Static graph topology only: no database, providers or human decisions.
    build_workflow().compile()
