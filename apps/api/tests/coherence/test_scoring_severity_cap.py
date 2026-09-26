"""Severity-cap tests for the coherence scorer (ADR-009 follow-up).

The evidence-aware model let a dimension with a critical finding out-score clean
dimensions (its context-inflated baseline barely decayed). These tests pin the
fix: a dimension with an open finding is the WORST, not the best, and the overall
score cannot read "healthy" while a critical is open.
"""

from __future__ import annotations

import pytest

from src.coherence.models import FindingSignal
from src.coherence.scoring import ScoringService

_ALL = ("SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME")


def _signal(category: str, severity: str, impact: float = 0.7) -> FindingSignal:
    return FindingSignal(
        rule_id="DET-BUD-SUM",
        clause_id="C1",
        source="deterministic",
        impact_score=impact,
        confidence=1.0,
        severity=severity,
        category=category,
        evidence_summary="budget sum below contract total",
        quote="1,196,941.54 vs 1,609,282.94",
    )


@pytest.fixture
def scorer() -> ScoringService:
    return ScoringService()


def _coverage_all() -> dict[str, bool]:
    return dict.fromkeys(_ALL, True)


def test_flagged_category_scores_worst_not_best(scorer: ScoringService) -> None:
    """The exact pilot inversion: BUDGET has the only critical finding, so it must
    be the LOWEST category — never higher than the clean ones (was 82.4 > 80)."""
    diag = scorer.calculate_detailed(
        [_signal("BUDGET", "critical")], num_clauses=67, coverage_map=_coverage_all()
    )
    budget = diag.category_scores["BUDGET"]
    others = [v for c, v in diag.category_scores.items() if c != "BUDGET" and v is not None]
    assert budget is not None
    assert budget <= 45.0, f"critical budget must cap <=45, got {budget}"
    assert others, "clean categories should still be scored"
    assert all(budget < o for o in others), "flagged category must score below clean ones"


def test_overall_capped_when_critical_open(scorer: ScoringService) -> None:
    diag = scorer.calculate_detailed(
        [_signal("BUDGET", "critical")], num_clauses=67, coverage_map=_coverage_all()
    )
    assert diag.score is not None
    assert diag.score <= 60.0, f"overall must cap <=60 with an open critical, got {diag.score}"


def test_high_finding_caps_below_clean(scorer: ScoringService) -> None:
    diag = scorer.calculate_detailed(
        [_signal("LEGAL", "high")], num_clauses=40, coverage_map=_coverage_all()
    )
    legal = diag.category_scores["LEGAL"]
    assert legal is not None and legal <= 65.0


def test_clean_project_not_capped(scorer: ScoringService) -> None:
    """No findings -> no cap; every assessed category keeps its baseline."""
    diag = scorer.calculate_detailed([], num_clauses=40, coverage_map=_coverage_all())
    assert diag.score is not None
    assert diag.score > 60.0, "a clean project must not be capped"
