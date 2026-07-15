from datetime import date


def test_category_breakdown_accepts_budget_throttled_state():
    from src.coherence.models import CategoryBreakdown, SeverityCount
    cb = CategoryBreakdown(
        category="legal", score=None, alert_count=0,
        severity_breakdown=SeverityCount(critical=0, high=0, medium=0, low=0, info=0),
        impact_percentage=0.0, state="budget_throttled", baseline_estimated=False,
    )
    assert cb.state == "budget_throttled"
    assert cb.score is None


def test_category_breakdown_existing_states_still_work():
    """Make sure the widening doesn't break the existing three TASK-BCK-060 states."""
    from src.coherence.models import CategoryBreakdown, SeverityCount
    sev = SeverityCount(critical=0, high=0, medium=0, low=0, info=0)
    for s in ("unassessed", "assessed_clean", "assessed_findings"):
        cb = CategoryBreakdown(
            category="legal", score=None, alert_count=0,
            severity_breakdown=sev, impact_percentage=0.0,
            state=s, baseline_estimated=False,
        )
        assert cb.state == s


def test_scoring_diagnostics_has_budget_exhausted_reset_date():
    from src.coherence.scoring import ScoringDiagnostics
    d = ScoringDiagnostics(
        score=None, total_findings=0, deterministic_findings=0, llm_findings=0,
        severity_distribution={"critical": 0, "high": 0, "medium": 0, "low": 0},
        avg_impact=0.0, avg_confidence=0.0, scope_factor=1.0,
        penalty_density=0.0, raw_penalty_sum=0.0, category_contributions={},
        budget_exhausted_reset_date=date(2026, 6, 1),
    )
    assert d.budget_exhausted_reset_date == date(2026, 6, 1)


def test_scoring_diagnostics_reset_date_defaults_to_none():
    """Backward compat: existing constructors without reset_date still work."""
    from src.coherence.scoring import ScoringDiagnostics
    d = ScoringDiagnostics(
        score=85.0, total_findings=3, deterministic_findings=3, llm_findings=0,
        severity_distribution={"critical": 0, "high": 1, "medium": 2, "low": 0},
        avg_impact=0.4, avg_confidence=0.9, scope_factor=1.2,
        penalty_density=0.05, raw_penalty_sum=0.06,
        category_contributions={"LEGAL": 0.06},
    )
    assert d.budget_exhausted_reset_date is None


def test_build_category_breakdown_surfaces_budget_throttled():
    """When a category is unassessed AND in budget_throttled_categories,
    breakdown.state must be 'budget_throttled' (not 'unassessed').
    """
    from src.coherence.graph.nodes import _build_category_breakdown

    coverage = dict.fromkeys(("SCOPE", "BUDGET", "TIME", "TECHNICAL", "QUALITY"), True)
    coverage["LEGAL"] = False
    cat_scores = dict.fromkeys(("SCOPE", "BUDGET", "TIME", "TECHNICAL", "QUALITY"), 85.0)
    cat_scores["LEGAL"] = None

    bd = _build_category_breakdown(
        signals=[], coverage_map=coverage, category_scores=cat_scores,
        budget_throttled_categories={"LEGAL"},
    )
    by = {b.category: b for b in bd}
    assert by["legal"].state == "budget_throttled"
    assert by["legal"].score is None
    # Other categories unchanged
    assert by["scope"].state == "assessed_clean"


def test_build_category_breakdown_omitting_throttled_set_uses_unassessed():
    """Backward-compat: when budget_throttled_categories is None / omitted,
    unassessed remains 'unassessed' (no behavioral change for non-LLM paths).
    """
    from src.coherence.graph.nodes import _build_category_breakdown
    coverage = dict.fromkeys(("SCOPE", "BUDGET", "TIME", "TECHNICAL", "QUALITY"), True)
    coverage["LEGAL"] = False
    cat_scores = dict.fromkeys(("SCOPE", "BUDGET", "TIME", "TECHNICAL", "QUALITY"), 85.0)
    cat_scores["LEGAL"] = None
    bd = _build_category_breakdown(
        signals=[], coverage_map=coverage, category_scores=cat_scores,
    )  # no budget_throttled_categories kwarg
    by = {b.category: b for b in bd}
    assert by["legal"].state == "unassessed"


def test_assessed_category_in_throttled_set_does_not_get_overridden():
    """Throttling only applies when the category is ALSO unassessed.
    An assessed-clean category in the throttled set keeps assessed_clean."""
    from src.coherence.graph.nodes import _build_category_breakdown
    coverage = dict.fromkeys(("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"), True)
    cat_scores = dict.fromkeys(coverage, 85.0)
    bd = _build_category_breakdown(
        signals=[], coverage_map=coverage, category_scores=cat_scores,
        budget_throttled_categories={"LEGAL"},
    )
    by = {b.category: b for b in bd}
    # LEGAL is assessed → state stays assessed_clean despite being in throttled set
    assert by["legal"].state == "assessed_clean"
