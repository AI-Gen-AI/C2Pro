"""
Tests for N8 coherence_scorer canonical subgraph delegation.

Refers to Suite ID: TS-UA-ANA-UC-001.
Refers to backlog_id: TASK-COH-V1-02.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.coherence.models import EnrichedCoherenceResult


@pytest.mark.asyncio
async def test_coherence_scorer_invokes_canonical_subgraph_for_contract_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS-UA-ANA-UC-001: N8 keeps graph signature and delegates scoring to v1 subgraph."""
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node
    from src.coherence.models import Clause

    calls: list[tuple[list[Clause], str]] = []

    async def fake_evaluate_coherence_async(
        clauses: list[Clause],
        project_id: str = "default",
        config: object | None = None,
        seed_signals: list[object] | None = None,
        seed_coverage: dict[str, bool] | None = None,
    ) -> EnrichedCoherenceResult:
        assert seed_signals == []
        assert seed_coverage == {}
        calls.append((clauses, project_id))
        return EnrichedCoherenceResult(
            overall_score=None,
            score_version="coherence-v1",
            score_reason="insufficient_evidence",
            score_missing_dimensions=["schedule", "budget"],
            calculated_at=datetime.now(UTC),
            finding_signals=[],
        )

    monkeypatch.setattr(
        "src.coherence.graph.graph.evaluate_coherence_async",
        fake_evaluate_coherence_async,
    )

    project_id = str(uuid4())
    state = {
        "project_id": project_id,
        "document_id": str(uuid4()),
        "document_text": "Contract-only upload with no schedule or budget attachment.",
        "doc_type": "contract",
        "messages": [],
        "extracted_risks": [],
        "extracted_wbs": [],
        "confidence_score": 0.95,
        "tenant_id": str(uuid4()),
        "analysis_id": str(uuid4()),
        "bom_items": [],
    }

    result = await coherence_scorer_node(state)

    assert calls
    assert calls[0][1] == project_id
    assert result["coherence_score"] is None
    assert result["coherence_score_version"] == "coherence-v1"
    assert result["coherence_reason"] == "insufficient_evidence"
    assert result["coherence_missing_dimensions"] == ["schedule", "budget"]
