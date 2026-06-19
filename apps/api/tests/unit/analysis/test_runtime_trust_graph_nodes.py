"""TS-ADR-013-GRAPH-001 - Runtime Trust behavior for material graph nodes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.analysis.domain.node_result import NodeResult, NodeStatus
from src.coherence.models import EnrichedCoherenceResult


def _state(**overrides: object) -> dict[str, object]:
    """TS-ADR-013-GRAPH-001 - Build a minimal analysis graph state."""
    defaults: dict[str, object] = {
        "project_id": str(uuid4()),
        "document_id": str(uuid4()),
        "document_text": "Contract text with liquidated damages and schedule obligations.",
        "anonymized_text": "",
        "doc_type": "contract",
        "tenant_id": str(uuid4()),
        "messages": [],
        "extracted_risks": [{"title": "Delay", "severity": "HIGH", "category": "TIME"}],
        "extracted_wbs": [],
        "bom_items": [],
        "confidence_score": 0.9,
    }
    defaults.update(overrides)
    return defaults


@pytest.mark.asyncio
async def test_coherence_scorer_returns_failed_node_result_when_subgraph_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS-ADR-013-GRAPH-001 - N8 failures are explicit NodeResult envelopes, never silent empty fallbacks."""
    from src.analysis.adapters.graph import nodes_extended

    async def failing_evaluate_coherence_async(**_kwargs: object) -> EnrichedCoherenceResult:
        raise RuntimeError("coherence signature drift")

    persisted: list[NodeResult] = []

    monkeypatch.setattr(
        "src.coherence.graph.graph.evaluate_coherence_async",
        failing_evaluate_coherence_async,
    )
    monkeypatch.setattr(
        nodes_extended,
        "_persist_node_error",
        lambda state, result: persisted.append(result),
    )

    result = await nodes_extended.coherence_scorer_node(_state())

    node_result = result["node_results"][0]
    assert node_result.status is NodeStatus.FAILED
    assert node_result.error is not None
    assert node_result.error.node == "coherence_scorer"
    assert node_result.error.message == "coherence signature drift"
    assert persisted == [node_result]
    assert result["coherence_score"] is None
    assert result["coherence_reason"] == "node_failed"


@pytest.mark.asyncio
async def test_stakeholder_extractor_returns_failed_node_result_when_extraction_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS-ADR-013-GRAPH-001 - N6 failures are observable instead of indistinguishable from no stakeholders."""
    from src.analysis.adapters.graph import nodes_extended

    class FailingExtractor:
        def __init__(self, ai_provider: object) -> None:
            self.ai_provider = ai_provider

        async def execute(self, **_kwargs: object) -> list[object]:
            raise RuntimeError("stakeholder model unavailable")

    monkeypatch.setattr("src.core.ai.anthropic_wrapper.get_anthropic_wrapper", lambda: object())
    monkeypatch.setattr(
        "src.stakeholders.application.extract_stakeholders.ExtractStakeholdersUseCase",
        FailingExtractor,
    )
    monkeypatch.setattr(nodes_extended, "_persist_node_error", lambda _state, _result: None)

    result = await nodes_extended.stakeholder_extractor_node(_state())

    node_result = result["node_results"][0]
    assert node_result.status is NodeStatus.FAILED
    assert node_result.error is not None
    assert node_result.error.node == "stakeholder_extractor"
    assert result["extracted_stakeholders"] == []


@pytest.mark.asyncio
async def test_stakeholder_extractor_no_tenant_returns_skipped_node_result() -> None:
    """TS-ADR-013-GRAPH-001 - N6 no-tenant skip paths are visible NodeResult skips."""
    from src.analysis.adapters.graph import nodes_extended

    result = await nodes_extended.stakeholder_extractor_node(_state(tenant_id=None))

    node_result = result["node_results"][0]
    assert node_result.node == "stakeholder_extractor"
    assert node_result.status is NodeStatus.SKIPPED
    assert node_result.degradation_reason == "missing_tenant_id"
    assert result["extracted_stakeholders"] == []


@pytest.mark.asyncio
async def test_coherence_scorer_no_project_returns_skipped_node_result() -> None:
    """TS-ADR-013-GRAPH-001 - N8 no-project skip paths are visible NodeResult skips."""
    from src.analysis.adapters.graph import nodes_extended

    result = await nodes_extended.coherence_scorer_node(_state(project_id=None))

    node_result = result["node_results"][0]
    assert node_result.node == "coherence_scorer"
    assert node_result.status is NodeStatus.SKIPPED
    assert node_result.degradation_reason == "missing_project_id"
    assert result["coherence_score"] is None


@pytest.mark.asyncio
async def test_coherence_llm_flag_controls_low_budget_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS-ADR-013-GRAPH-001 - feature_v3_coherence_llm is the LLM-on gate for N8."""
    from src.analysis.adapters.graph import nodes_extended

    configs: list[object] = []

    async def fake_evaluate_coherence_async(**kwargs: object) -> EnrichedCoherenceResult:
        configs.append(kwargs["config"])
        return EnrichedCoherenceResult(
            overall_score=None,
            score_reason="insufficient_evidence",
            score_missing_dimensions=["schedule", "budget"],
            calculated_at=datetime.now(UTC),
            finding_signals=[],
        )

    monkeypatch.setattr(
        "src.coherence.graph.graph.evaluate_coherence_async",
        fake_evaluate_coherence_async,
    )

    async def enabled(_state: dict[str, object]) -> bool:
        return True

    monkeypatch.setattr(nodes_extended, "_is_feature_v3_coherence_llm_enabled", enabled)

    await nodes_extended.coherence_scorer_node(_state())

    assert configs
    assert configs[0].low_budget_mode is False
