from __future__ import annotations

import sys
import types

import pytest
from langgraph.checkpoint.memory import MemorySaver


@pytest.mark.asyncio
async def test_graph_flow_retries_on_negative_critique(monkeypatch) -> None:
    stub_ai_service = types.ModuleType("src.ai.ai_service")

    class StubAIService:
        def __init__(self, tenant_id=None) -> None:
            self.tenant_id = tenant_id

        async def run_extraction(self, system_prompt: str, user_content: str):
            return {}

    stub_ai_service.AIService = StubAIService

    stub_risk_agent = types.ModuleType("src.ai.agents.risk_agent")
    stub_wbs_agent = types.ModuleType("src.ai.agents.wbs_agent")

    class StubRiskAgent:
        def __init__(self, tenant_id=None) -> None:
            self.tenant_id = tenant_id

        async def extract(self, document_text: str):
            return []

    class StubWBSAgent:
        def __init__(self, tenant_id=None) -> None:
            self.tenant_id = tenant_id

        async def extract(self, document_text: str):
            return []

    stub_risk_agent.RiskExtractionAgent = StubRiskAgent
    stub_wbs_agent.WBSExtractionAgent = StubWBSAgent

    sys.modules["src.ai.ai_service"] = stub_ai_service
    sys.modules["src.ai.agents.risk_agent"] = stub_risk_agent
    sys.modules["src.ai.agents.wbs_agent"] = stub_wbs_agent

    from src.ai.graph.workflow import compile_workflow
    import src.ai.graph.nodes as nodes
    import src.ai.graph.workflow as workflow

    calls = {"extract": 0, "critique": 0}

    async def fake_risk_extractor(state):
        calls["extract"] += 1
        state["extracted_risks"] = [{"title": "R1", "description": "Risk", "confidence": 0.9}]
        return state

    async def fake_save_to_db(state):
        return state

    async def fake_critique_extraction(*, items, doc_type, tenant_id):
        calls["critique"] += 1
        if calls["critique"] == 1:
            return {"status": "RETRY", "notes": "Faltan referencias a clausulas."}
        return {"status": "OK", "notes": "Correcto."}

    monkeypatch.setattr(workflow, "risk_extractor_node", fake_risk_extractor)
    monkeypatch.setattr(workflow, "save_to_db_node", fake_save_to_db)
    monkeypatch.setattr(nodes, "_critique_extraction", fake_critique_extraction)

    app = compile_workflow(checkpointer=MemorySaver(), persist_diagram=False)
    initial_state = {
        "project_id": "p-123",
        "document_id": "d-123",
        "document_text": "Contrato de obra con clausulas.",
        "doc_type": "contract",
        "messages": [],
        "extracted_risks": [],
        "extracted_wbs": [],
        "confidence_score": 0.0,
        "critique_notes": "",
        "human_feedback": "",
        "retry_count": 0,
        "tenant_id": None,
        "analysis_id": None,
        "human_approval_required": False,
    }

    result = await app.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": "p-123"}, "recursion_limit": 10},
    )

    assert calls["extract"] == 2
    assert result["retry_count"] == 1
    assert result["human_approval_required"] is False
