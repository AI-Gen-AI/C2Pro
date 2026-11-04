"""N2 -> N3/N4/N5 safe-source regression: no LLM sees original PII."""

from __future__ import annotations

from typing import Any

import pytest

from src.analysis.domain.ai_source_text import llm_document_text
from src.analysis.adapters.ai.tools.risk_extraction_tool import RiskExtractionTool
from src.analysis.adapters.ai.tools.wbs_extraction_tool import WBSExtractionTool
from src.analysis.adapters.graph.nodes import router_node


RAW = "Contract contact: juan@example.org. EPC contractor shall deliver transformers in May."
REDACTED = "Contract contact: [REDACTED]. EPC contractor shall deliver transformers in May."


def _state() -> dict[str, Any]:
    return {
        "document_text": RAW,
        "anonymized_text": REDACTED,
        "pii_anonymization_complete": True,
        "doc_type": "",
        "tenant_id": "00000000-0000-0000-0000-000000000099",
        "messages": [],
        "node_results": [],
        "critique_notes": "",
        "human_feedback": "",
    }


def test_safe_projection_never_falls_back_to_original_after_n2_marker():
    state = _state()
    assert llm_document_text(state) == REDACTED
    state["anonymized_text"] = ""
    assert llm_document_text(state) == ""


def test_legacy_direct_tool_invocation_without_n2_still_works():
    assert llm_document_text({"document_text": RAW, "anonymized_text": ""}) == RAW


@pytest.mark.asyncio
async def test_n3_router_ai_receives_only_anonymized_projection(monkeypatch):
    from src.analysis.adapters.graph import nodes

    class FakeAI:
        def __init__(self) -> None:
            self.messages: list[str] = []

        async def run_extraction(self, system_prompt: str, user_content: str):
            self.messages.append(user_content)
            return {"doc_type": "contract"}

    ai = FakeAI()
    monkeypatch.setattr(nodes, "get_ai_service", lambda tenant_id: ai)
    result = await router_node(_state())
    assert result["doc_type"] == "contract"
    assert len(ai.messages) == 1
    assert "juan@example.org" not in ai.messages[0]
    assert "[REDACTED]" in ai.messages[0]


def test_n4_tool_reads_redacted_projection_without_losing_risk_terms():
    # No AI request is made by extract_input_from_state.
    tool = RiskExtractionTool()
    params = tool.extract_input_from_state(_state())
    assert "juan@example.org" not in params.document_text
    assert "[REDACTED]" in params.document_text
    assert "transformers" in params.document_text


def test_n5_tool_reads_redacted_projection_without_losing_activity_terms():
    tool = WBSExtractionTool()
    params = tool.extract_input_from_state(_state())
    assert "juan@example.org" not in params.document_text
    assert "[REDACTED]" in params.document_text
    assert "transformers" in params.document_text


@pytest.mark.asyncio
async def test_n2_marks_projection_complete(monkeypatch):
    from src.analysis.adapters.graph import nodes_extended

    class Detector:
        async def detect(self, text):
            from types import SimpleNamespace
            return SimpleNamespace(items=[])

    class Anonymizer:
        async def anonymize(self, text, config):
            return REDACTED

    monkeypatch.setattr(nodes_extended, "get_pii_detector_service", lambda: Detector())
    monkeypatch.setattr(nodes_extended, "get_anonymization_service", lambda detector: Anonymizer())
    result = await nodes_extended.pii_anonymizer_node(_state())
    assert result["pii_anonymization_complete"] is True
    assert result["anonymized_text"] == REDACTED
