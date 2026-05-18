from src.coherence.graph.nodes import _build_category_breakdown
from src.coherence.models import FindingSignal


def _sig(cat):
    return FindingSignal(rule_id="R", clause_id="c", impact_score=0.45,
                         confidence=1.0, severity="medium", category=cat,
                         evidence_summary="e", quote="q", raw_data={})


def test_three_states_present():
    signals = [_sig("TECHNICAL")]
    coverage = {"TECHNICAL": True, "SCOPE": True, "BUDGET": False,
                "TIME": False, "LEGAL": False, "QUALITY": False}
    cat_scores = {"TECHNICAL": 71.0, "SCOPE": 88.0, "BUDGET": None,
                  "TIME": None, "LEGAL": None, "QUALITY": None}
    bd = _build_category_breakdown(signals, coverage, cat_scores)
    by = {b.category: b for b in bd}
    assert by["technical"].state == "assessed_findings" and by["technical"].score == 71.0
    assert by["scope"].state == "assessed_clean" and by["scope"].baseline_estimated is True
    # BUDGET maps to the canonical legacy label "financial" (see _CAT_LEGACY /
    # AlertCategory). The plan snippet's by["budget"] contradicted the mandated
    # _CAT_LEGACY block and the codebase-wide vocabulary; "financial" is correct.
    assert by["financial"].state == "unassessed" and by["financial"].score is None
