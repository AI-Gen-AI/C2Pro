"""WBS 1.1: an unreadable document must fail closed without invoking any LLM."""
from __future__ import annotations

import pytest

from src.analysis.adapters.graph import workflow as workflow_module
from src.analysis.domain.node_result import NodeStatus


@pytest.mark.asyncio
@pytest.mark.parametrize("unreadable_text", ["", " \n\t "])
async def test_insufficient_extractable_text_terminates_without_extraction(monkeypatch, unreadable_text):
    async def n1(state):
        return {"document_parsed": False, "document_category": "insufficient_extractable_text"}

    async def n2(state):
        return {"anonymized_text": ""}

    async def forbidden_extraction(state):
        raise AssertionError("unextractable document was routed to an extractor")

    monkeypatch.setattr(workflow_module, "document_ingestion_node", n1)
    monkeypatch.setattr(workflow_module, "pii_anonymizer_node", n2)
    monkeypatch.setattr(workflow_module, "risk_extractor_node", forbidden_extraction)
    monkeypatch.setattr(workflow_module, "wbs_extractor_node", forbidden_extraction)
    monkeypatch.setattr(workflow_module, "budget_parser_node", forbidden_extraction)

    graph = workflow_module.build_workflow().compile()
    result = await graph.ainvoke({
        "document_text": unreadable_text,
        "doc_type": "",
        "messages": [],
        "node_results": [],
        "extracted_risks": [],
        "extracted_wbs": [],
        "confidence_score": None,
    })

    assert result["doc_type"] == "insufficient_extractable_text"
    assert result["workflow_terminated"] is True
    assert result["termination_reason"] == "insufficient_extractable_text"
    assert result["confidence_score"] is None
    assert result["human_approval_required"] is False
    assert not result["extracted_risks"]
    assert not result["extracted_wbs"]
    assert any(
        n.node == "router" and n.status is NodeStatus.SKIPPED
        for n in result["node_results"]
    )
