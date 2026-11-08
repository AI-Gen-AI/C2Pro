"""Adversarial regression probes for Codex P0 assessment on N12."""
from __future__ import annotations
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from src.analysis.domain.critique_evaluation import CritiqueEvaluationService
from src.analysis.application.critique_extraction_use_case import (
    CritiqueExtractionCommand, CritiqueExtractionUseCase,
)


class _AI:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    async def run_extraction(self, system_prompt: str, user_content: str):
        return self.payload


@pytest.mark.parametrize("skip_hitl", [False, True])
def test_unassessed_never_inherits_confidence_or_bypasses_hitl(skip_hitl):
    result = CritiqueEvaluationService().evaluate_critique(
        critique_status="UNASSESSED",
        critique_notes="N12_UNASSESSED: no source evidence",
        confidence=0.98,
        retry_count=0,
        skip_hitl=skip_hitl,
    )
    assert result.confidence is None
    assert result.human_approval_required is True
    assert result.retry_count == 0


@pytest.mark.asyncio
async def test_legacy_node_routes_unassessed_to_hitl_with_mock_enabled(monkeypatch):
    from src.ai.graph import nodes as legacy_nodes
    from src.ai.graph.workflow import _next_after_critique

    async def _unassessed(*, items, doc_type, tenant_id):
        return {"status": "UNASSESSED", "notes": "N12_UNASSESSED: no source"}
    monkeypatch.setattr(legacy_nodes, "_critique_extraction", _unassessed)
    monkeypatch.setenv("C2PRO_AI_MOCK", "1")
    state = {
        "extracted_risks": [{"title": "Risk A", "confidence": 0.98}],
        "extracted_wbs": [],
        "doc_type": "contract", "tenant_id": None, "retry_count": 0,
        "messages": [AIMessage(content="Start")],
        "confidence_score": 0.98,
    }
    result = await legacy_nodes.critique_node(state)
    assert result["confidence_score"] is None
    assert result["human_approval_required"] is True
    assert result["retry_count"] == 0
    assert _next_after_critique(result) == "human_interrupt"


@pytest.mark.asyncio
async def test_partial_upstream_text_below_16k_cannot_certify_source_coverage():
    source = "EPC-01: The contractor shall supply the mounting structures."
    # The extracted document can be incomplete even when len(source) < 16000.
    # Until a trusted coverage authority is propagated, allow no OK-as-reviewed.
    result = await CritiqueExtractionUseCase(ai=_AI({"status": "OK", "notes": "", "findings": []})).execute(
        CritiqueExtractionCommand(
            extracted_risks=[{"title": "Scope", "confidence": 0.99}],
            extracted_wbs=[], doc_type="contract", retry_count=0,
            source_text=source,
        )
    )
    assert result.status == "UNASSESSED"
    assert result.confidence is None
    assert result.human_approval_required is True
