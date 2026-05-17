from src.coherence.graph.nodes import deterministic_evaluate
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
