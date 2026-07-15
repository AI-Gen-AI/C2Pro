from src.coherence.models import FindingSignal
from src.coherence.scoring import ScoringService


def _sig(cat, impact=0.5):
    return FindingSignal(rule_id="R", clause_id="c", impact_score=impact,
                         confidence=1.0, severity="medium", category=cat,
                         evidence_summary="e", quote="q", raw_data={})


def test_unassessed_categories_are_null_and_penalize_global():
    svc = ScoringService()
    cov = {"SCOPE": True, "TECHNICAL": True, "BUDGET": False,
           "TIME": False, "LEGAL": False, "QUALITY": False}
    d = svc.calculate_detailed(signals=[_sig("TECHNICAL")], num_clauses=20,
                               coverage_map=cov)
    assert d.category_scores["BUDGET"] is None
    assert d.category_scores["LEGAL"] is None
    assert set(d.missing_dimensions) == {"BUDGET", "TIME", "LEGAL", "QUALITY"}
    assert d.score is None


def test_assessed_clean_lands_in_baseline_band():
    svc = ScoringService()
    cov = dict.fromkeys(("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"), True)
    d = svc.calculate_detailed(signals=[_sig("TECHNICAL", 0.4)], num_clauses=20,
                               coverage_map=cov)
    assert 80.0 <= d.category_scores["LEGAL"] <= 90.0
    assert d.category_scores["TECHNICAL"] < d.category_scores["LEGAL"]


def test_no_coverage_returns_none():
    svc = ScoringService()
    d = svc.calculate_detailed(signals=[], num_clauses=5, coverage_map={})
    assert d.score is None
