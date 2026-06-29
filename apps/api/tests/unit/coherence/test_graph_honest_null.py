"""TS-ADR-013-GRAPH-001 - INV-1 honest-null coherence graph fallbacks."""

from __future__ import annotations

import pytest

from src.coherence.models import Clause


class _SyncGraph:
    def invoke(self, _state: object) -> dict[str, object]:
        return {
            "result": None,
            "score": 100,
            "alerts": ["fabricated-alert"],
            "all_signals": ["fabricated-signal"],
            "diagnostics": {"reason": "inner_graph_failed"},
        }

    async def ainvoke(self, _state: object) -> dict[str, object]:
        return self.invoke(_state)


class _AsyncGraph:
    async def ainvoke(self, _state: object) -> dict[str, object]:
        return {
            "result": None,
            "score": 100,
            "alerts": ["fabricated-alert"],
            "all_signals": ["fabricated-signal"],
            "diagnostics": {"reason": "inner_graph_failed"},
        }


def test_evaluate_coherence_result_none_returns_honest_null(monkeypatch) -> None:
    """TS-ADR-013-GRAPH-001 - Sync graph must not synthesize evidence-free critical output."""
    from src.coherence.graph import graph

    monkeypatch.setattr(graph, "get_coherence_subgraph", lambda: _SyncGraph())

    result = graph.evaluate_coherence([Clause(id="c1", text="x")])

    assert result.overall_score is None
    assert result.score_reason == "inner_graph_failed"
    assert result.alerts == []
    assert result.finding_signals == []


@pytest.mark.asyncio
async def test_evaluate_coherence_async_result_none_returns_honest_null(
    monkeypatch,
) -> None:
    """TS-ADR-013-GRAPH-001 - Async graph must not synthesize evidence-free critical output."""
    from src.coherence.graph import graph

    monkeypatch.setattr(graph, "get_coherence_subgraph", lambda: _AsyncGraph())

    result = await graph.evaluate_coherence_async([Clause(id="c1", text="x")])

    assert result.overall_score is None
    assert result.score_reason == "inner_graph_failed"
    assert result.alerts == []
    assert result.finding_signals == []
