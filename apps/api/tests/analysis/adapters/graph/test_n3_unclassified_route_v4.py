"""V4 regression: a provider classification failure must not invoke any extractor.

Runs the REAL compiled LangGraph and N3 adapter, with only external/model
ports isolated. This is a routing and trust contract test, not semantic gold.
"""
from __future__ import annotations

import pytest

from src.analysis.adapters.graph import nodes
from src.analysis.adapters.graph import workflow as workflow_module
from src.analysis.domain.node_result import NodeStatus


class FailedClassifier:
    def __init__(self):
        self.calls = 0

    async def run_extraction(self, prompt, content):
        self.calls += 1
        raise ConnectionError("Classification provider unavailable")


@pytest.mark.asyncio
async def test_unclassified_document_does_not_route_to_n4_n5_n9_or_human(monkeypatch):
    async def n1(_state):
        return {"document_parsed": True, "document_category": "UNKNOWN"}

    async def n2(state):
        return {"anonymized_text": state["document_text"], "pii_anonymization_complete": True}

    async def forbidden(_state):
        raise AssertionError("Unknown document type MUST NOT start an extractor")

    ai = FailedClassifier()
    monkeypatch.setattr(workflow_module, "document_ingestion_node", n1)
    monkeypatch.setattr(workflow_module, "pii_anonymizer_node", n2)
    monkeypatch.setattr(workflow_module, "risk_extractor_node", forbidden)
    monkeypatch.setattr(workflow_module, "wbs_extractor_node", forbidden)
    monkeypatch.setattr(workflow_module, "budget_parser_node", forbidden)
    monkeypatch.setattr(workflow_module, "critique_node", forbidden)
    monkeypatch.setattr(workflow_module, "human_interrupt_node", forbidden)
    monkeypatch.setattr(workflow_module, "save_to_db_node", forbidden)
    monkeypatch.setattr(nodes, "get_ai_service", lambda tenant_id: ai)

    graph = workflow_module.build_workflow().compile()
    source = (
        "Project supply agreement: software, equipment and installation "
        "activities are described along with scope, schedule and budget."
    )
    state = await graph.ainvoke({
        "document_text": source,
        "doc_type": "",
        "messages": [],
        "node_results": [],
        "extracted_risks": [],
        "extracted_wbs": [],
        "confidence_score": None,
    })

    assert ai.calls == 1
    assert state["doc_type"] == "classification_unassessed"
    assert state["workflow_terminated"] is True
    assert state["termination_reason"] == "classification_unassessed"
    assert state["human_approval_required"] is False
    assert state["confidence_score"] is None
    assert state["extracted_risks"] == state["extracted_wbs"] == []
    assert any(
        row.node == "router"
        and row.status == NodeStatus.DEGRADED
        and row.degradation_reason == "classification_unassessed"
        for row in state["node_results"]
    )
    assert any(
        row.node == "unclassified_document"
        and row.degradation_reason == "classification_unassessed"
        for row in state["node_results"]
    )
