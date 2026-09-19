from src.coherence.graph.nodes import format_output, scoring_arbiter
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


def test_format_output_surfaces_audit_coverage_and_category_scores():
    state = CoherenceGraphState(project_id="p")
    state.deterministic_signals = [
        FindingSignal(rule_id="DET-TEC-SPEC", clause_id="c", impact_score=0.45,
                      confidence=1.0, severity="medium", category="TECHNICAL",
                      evidence_summary="e", quote="q", raw_data={})
    ]
    state.llm_signals = []
    state.cross_signals = []
    state.coverage_map = {"TECHNICAL": True, "SCOPE": True, "BUDGET": False,
                          "TIME": False, "LEGAL": False, "QUALITY": False}

    arb = scoring_arbiter(state)
    assert arb["diagnostics"]["audit_coverage"] is not None

    state.diagnostics = arb["diagnostics"]
    state.score = arb["score"]
    state.all_signals = arb["all_signals"]

    result = format_output(state)["result"]

    # The diagnostics API response must expose the audit coverage rather than
    # omitting it when the scorer computed it (Issue #140).
    assert result.audit_coverage is not None
    assert result.audit_coverage["assessed"] == 2
    assert result.audit_coverage["total"] == 6

    # Per-category scores computed by the scorer are also surfaced.
    assert result.category_scores is not None
    assert result.category_scores["BUDGET"] is None
    assert result.category_scores["TECHNICAL"] is not None
