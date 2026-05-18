from src.coherence.models import CategoryBreakdown, SeverityCount


def test_category_breakdown_accepts_null_score_and_state():
    cb = CategoryBreakdown(
        category="legal", score=None, alert_count=0,
        severity_breakdown=SeverityCount(critical=0, high=0, medium=0, low=0, info=0),
        impact_percentage=0.0, state="unassessed", baseline_estimated=False,
    )
    assert cb.score is None
    assert cb.state == "unassessed"
    assert cb.baseline_estimated is False
