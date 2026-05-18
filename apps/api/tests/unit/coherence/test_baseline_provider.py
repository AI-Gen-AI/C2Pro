from src.coherence.scoring import BaselineContext, HeuristicBaselineProvider


def test_single_assessed_category_gets_high():
    p = HeuristicBaselineProvider()
    ctx = BaselineContext(total_findings_other_categories=0,
                           total_assessed_categories=1,
                           avg_impact_other_categories=0.0, num_clauses=10)
    assert p.baseline_for("LEGAL", ctx) == 90.0


def test_clean_elsewhere_pushes_toward_high():
    p = HeuristicBaselineProvider()
    ctx = BaselineContext(total_findings_other_categories=0,
                           total_assessed_categories=3,
                           avg_impact_other_categories=0.0, num_clauses=10)
    assert p.baseline_for("LEGAL", ctx) == 90.0


def test_high_risk_elsewhere_drops_toward_low():
    p = HeuristicBaselineProvider()
    ctx = BaselineContext(total_findings_other_categories=8,
                           total_assessed_categories=3,
                           avg_impact_other_categories=0.8, num_clauses=10)
    assert p.baseline_for("LEGAL", ctx) == 80.0


def test_baseline_stays_in_band():
    p = HeuristicBaselineProvider()
    for impact in (0.0, 0.1, 0.3, 0.5, 0.9, 5.0):
        ctx = BaselineContext(1, 4, impact, 10)
        assert 80.0 <= p.baseline_for("BUDGET", ctx) <= 90.0
