from src.coherence.graph.nodes import scoring_arbiter
from src.coherence.graph.state import CoherenceGraphState
from src.coherence.models import FindingSignal


def test_arbiter_threads_coverage_and_category_scores():
    state = CoherenceGraphState(project_id="p")
    state.deterministic_signals = [
        FindingSignal(rule_id="DET-TEC-SPEC", clause_id="c", impact_score=0.45,
                      confidence=1.0, severity="medium", category="TECHNICAL",
                      evidence_summary="e", quote="q", raw_data={})
    ]
    state.coverage_map = {"TECHNICAL": True, "SCOPE": True, "BUDGET": False,
                          "TIME": False, "LEGAL": False, "QUALITY": False}
    out = scoring_arbiter(state)
    assert out["diagnostics"]["category_scores"]["BUDGET"] is None
    assert out["diagnostics"]["category_scores"]["TECHNICAL"] is not None
    assert "BUDGET" in out["diagnostics"]["missing_dimensions"]
