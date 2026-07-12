"""TS-ADR-013-GRAPH-001 - Graph node contract guards for ADR-013 Runtime Trust."""

from __future__ import annotations

import inspect
from pathlib import Path


def test_n8_coherence_call_surface_accepts_seeded_evidence() -> None:
    """TS-ADR-013-GRAPH-001 - N8 and the coherence subgraph keep an explicit seeded-evidence API."""
    from src.coherence.graph.graph import evaluate_coherence_async

    signature = inspect.signature(evaluate_coherence_async)

    assert list(signature.parameters)[:3] == ["clauses", "project_id", "config"]
    assert "seed_signals" in signature.parameters
    assert "seed_coverage" in signature.parameters


def test_n8_node_does_not_hardcode_low_budget_mode_true() -> None:
    """TS-ADR-013-GRAPH-001 - N8 must gate LLM usage through feature_v3_coherence_llm."""
    from src.analysis.adapters.graph import nodes_extended

    source = inspect.getsource(nodes_extended.coherence_scorer_node)

    assert "low_budget_mode=True" not in source
    assert "feature_v3_coherence_llm" in source


def test_ci_workflow_runs_graph_node_contract_gate() -> None:
    """TS-ADR-013-GRAPH-001 - CI executes the ADR-013 graph contract gate."""
    workflow = Path(__file__).parents[4] / ".github" / "workflows" / "ci.yml"

    contents = workflow.read_text(encoding="utf-8")

    assert "tests/contract/test_graph_node_contracts.py" in contents
