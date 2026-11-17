"""WBS 1.2: distinguish successful zero candidates from a failed N4 call.

Zero model findings with no externally verified coverage is UNASSESSED, never
proof that the complete contract is risk-free. Provider/JSON failures remain
FAILED with typed error evidence.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.analysis.adapters.ai.tools.risk_extraction_tool import (
    RiskExtractionInput,
    RiskExtractionTool,
)
from src.analysis.domain.node_result import NodeStatus
from src.core.ai.anthropic_wrapper import AIResponse
from src.core.ai.tools.metadata import ToolResult, ToolStatus


def _tool():
    return RiskExtractionTool(anthropic_wrapper=object(), prompt_manager=object())


def _response(content):
    return AIResponse(
        content=content, model_used="test-only", input_tokens=12,
        output_tokens=6, cost_usd=0, latency_ms=1,
    )


@pytest.mark.asyncio
async def test_strict_n4_rejects_missing_explicit_risks_array():
    with pytest.raises(ValueError, match="risks"):
        await _tool()._execute_impl(
            RiskExtractionInput(
                document_text="Contract with possible penalties",
                strict_completeness=True,
            ),
            tenant_id=uuid4(),
            ai_response=_response('{"message":"no risks"}'),
        )


@pytest.mark.asyncio
async def test_strict_n4_accepts_explicit_empty_risks_as_parse_not_certification():
    risks = await _tool()._execute_impl(
        RiskExtractionInput(
            document_text="Some contract clauses with sufficient source text",
            strict_completeness=True,
        ),
        tenant_id=uuid4(),
        ai_response=_response('{"risks":[]}'),
    )
    assert risks == []


def test_successful_zero_items_injected_as_unassessed_without_confidence():
    state = {"extracted_risks": [], "messages": [], "node_results": []}
    result = ToolResult(
        data=[], status=ToolStatus.SUCCESS, success=True,
        model_used="test-only", input_tokens=10, output_tokens=2,
        cost_usd=0, latency_ms=2,
    )
    updated = _tool().inject_output_into_state(state, result)
    assert updated["risk_extraction_outcome"] == "NO_FINDINGS_UNASSESSED"
    assert updated["risk_extraction_error_type"] is None
    assert updated["confidence_score"] is None


@pytest.mark.asyncio
async def test_n4_zero_findings_must_be_degraded_not_provider_failure(monkeypatch):
    import src.core.ai.tools as tools
    from src.analysis.adapters.graph import nodes

    async def successful_zero(state):
        state["extracted_risks"] = []
        state["risk_extraction_outcome"] = "NO_FINDINGS_UNASSESSED"
        state["risk_extraction_error_type"] = None
        return state

    monkeypatch.setattr(tools, "get_tool", lambda *a, **kw: successful_zero)
    async def unexpected_persistence(*a, **kw):
        raise AssertionError("No processing_error event for valid zero output")
    monkeypatch.setattr(nodes, "_persist_node_error", unexpected_persistence)
    state = {
        "document_text": "The parties agree that they shall provide goods.",
        "anonymized_text": "The parties agree that they shall provide goods.",
        "extracted_risks": [], "node_results": [], "messages": [],
        "confidence_score": None, "retry_count": 0,
        "human_approval_required": False, "critique_notes": "",
        "tenant_id": None,
    }
    out = await nodes.risk_extractor_node(state)
    assert out["node_results"][-1].status is NodeStatus.DEGRADED
    assert out["node_results"][-1].degradation_reason == "zero_findings_unassessed"
    assert out["human_approval_required"] is True
    assert out["confidence_score"] is None


@pytest.mark.asyncio
async def test_n12_cannot_clear_review_for_unassessed_zero_candidates(monkeypatch):
    from src.analysis.adapters.graph import nodes

    class FakeCritique:
        def __init__(self, **kwargs): pass
        async def execute(self, command):
            return SimpleNamespace(
                confidence=0.99, retry_count=0, critique_notes="",
                human_approval_required=False, status="OK"
            )

    monkeypatch.setattr(nodes, "CritiqueExtractionUseCase", FakeCritique)
    monkeypatch.setattr(nodes, "get_ai_service", lambda t: object())
    async def skip_temporal(*args, **kwargs):
        return None
    monkeypatch.setattr(nodes, "_apply_temporal_review_gate", skip_temporal)
    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    state = {
        "document_text": "A sufficiently long and otherwise valid contract.",
        "anonymized_text": "A sufficiently long and otherwise valid contract.",
        "extracted_risks": [], "extracted_wbs": [],
        "doc_type": "contract", "retry_count": 0,
        "risk_extraction_outcome": "NO_FINDINGS_UNASSESSED",
        "human_approval_required": True, "messages": [],
        "node_results": [], "tenant_id": None,
    }
    out = await nodes.critique_node(state)
    assert out["human_approval_required"] is True
    assert out["confidence_score"] is None
    assert out["retry_count"] == 0
    assert "unassessed" in out["critique_notes"].lower()
