from src.coherence.graph.nodes import deterministic_evaluate, llm_semantic_evaluate
from src.coherence.graph.state import CoherenceGraphState
from src.coherence.models import Clause


def test_deterministic_node_marks_assessed_and_unassessed():
    state = CoherenceGraphState(
        project_id="p",
        clauses=[Clause(id="c1", text="BOM material standard", data={"material": "steel"})],
    )
    out = deterministic_evaluate(state)
    cov = out["coverage_map"]
    assert cov.get("TECHNICAL") is True
    assert cov.get("BUDGET", False) is False


def test_llm_node_low_budget_marks_categories_not_llm_assessed():
    state = CoherenceGraphState(
        project_id="p",
        clauses=[Clause(id="c1", text="The contractor shall be liable.", data={})],
    )
    # default config.low_budget_mode is True
    out = llm_semantic_evaluate(state)
    cov = out["coverage_map"]
    assert cov.get("LEGAL") is False
    assert out["llm_signals"] == []
