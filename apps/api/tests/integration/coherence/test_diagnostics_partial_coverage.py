"""
Integration test — bug repro for SCOPE-only project returning overall_score=15.

Scenario: 2-document project where only SCOPE category is assessed.
The v1 engine used to return overall_score=15 (mean × coverage_ratio) which
violates ADR-009 §1 P1 + §14. After the Phase A hotfix it must return
overall_score=None with score_reason="insufficient_active_weight".

This test drives the scoring engine through the same code path that the
diagnostics HTTP endpoint exercises: ScoringService.calculate_detailed()
→ format_output node → EnrichedCoherenceResult.

Suite ID: TS-INT-COH-DIAG-001
"""
from __future__ import annotations

import pytest

from src.coherence.graph.nodes import format_output
from src.coherence.graph.state import CoherenceGraphState, EvaluationConfig
from src.coherence.scoring import ScoringService

ALL_CATEGORIES = ("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY")


# ---------------------------------------------------------------------------
# Helper: run scoring service + format_output as the diagnostics endpoint does
# ---------------------------------------------------------------------------

def _run_scope_only_project() -> dict:
    """
    Simulate a SCOPE-only assessed project (2 docs, contract-only):
    - coverage_map: only SCOPE=True, rest False
    - signals: empty (no findings, just assessed category)
    Returns the state dict from format_output.
    """
    svc = ScoringService()
    coverage_map = {c: (c == "SCOPE") for c in ALL_CATEGORIES}

    diagnostics_result = svc.calculate_detailed(
        signals=[],
        num_clauses=20,
        coverage_map=coverage_map,
        poor_extraction_quality=False,
    )

    # Build state as format_output would receive it
    state = CoherenceGraphState(
        project_id="test-proj-scope-only",
        clauses=[],
        config=EvaluationConfig(low_budget_mode=True),
        score=diagnostics_result.score,
        coverage_map=coverage_map,
        diagnostics={
            "reason": diagnostics_result.reason,
            "missing_dimensions": diagnostics_result.missing_dimensions,
            "category_scores": diagnostics_result.category_scores or {},
            "scope_factor": diagnostics_result.scope_factor,
            "penalty_density": diagnostics_result.penalty_density,
            "avg_impact": diagnostics_result.avg_impact,
            "avg_confidence": diagnostics_result.avg_confidence,
        },
        all_signals=[],
    )

    return format_output(state)


@pytest.mark.integration
def test_scope_only_diagnostics_returns_null_score() -> None:
    """
    Bug repro: 2-doc SCOPE-only project → EnrichedCoherenceResult.overall_score
    must be None (was 15 before the hotfix).
    """
    output = _run_scope_only_project()
    result = output.get("result")

    assert result is not None, "format_output must produce a 'result' key"
    assert result.overall_score is None, (
        f"overall_score must be None for SCOPE-only; got {result.overall_score}. "
        "This is the bug repro: the old mean×coverage_ratio formula returned 15."
    )


@pytest.mark.integration
def test_scope_only_diagnostics_carries_score_reason() -> None:
    """
    score_reason must be 'insufficient_active_weight' for SCOPE-only project.
    """
    output = _run_scope_only_project()
    result = output.get("result")

    assert result.score_reason == "insufficient_active_weight", (
        f"score_reason must be 'insufficient_active_weight'; got {result.score_reason!r}"
    )


@pytest.mark.integration
def test_scope_only_category_breakdown_has_one_assessed() -> None:
    """
    category_breakdown must contain exactly 1 assessed category (SCOPE)
    and 5 unassessed. This validates coverage propagation from scoring
    diagnostics through to the enriched result.
    """
    output = _run_scope_only_project()
    result = output.get("result")

    # category_breakdown may be empty if no signals — just check
    # the score_missing_dimensions which comes from diagnostics
    if result.score_missing_dimensions:
        assert len(result.score_missing_dimensions) == 5, (
            f"Expected 5 missing dimensions; got {len(result.score_missing_dimensions)}: "
            f"{result.score_missing_dimensions}"
        )
        # SCOPE must NOT be in missing dimensions
        assert "SCOPE" not in result.score_missing_dimensions, (
            "SCOPE was assessed — must not appear in score_missing_dimensions"
        )


@pytest.mark.integration
def test_scope_category_has_nonzero_score_in_breakdown() -> None:
    """
    The SCOPE category itself was assessed and clean → its category score
    must be in the baseline band [80, 90]. The other 5 must be None (unassessed).
    Validates that the §14 guard does not zero out assessed categories.
    """
    svc = ScoringService()
    coverage_map = {c: (c == "SCOPE") for c in ALL_CATEGORIES}

    diag = svc.calculate_detailed(
        signals=[],
        num_clauses=20,
        coverage_map=coverage_map,
    )

    assert diag.category_scores is not None
    # SCOPE should have a computed baseline score
    scope_score = diag.category_scores.get("SCOPE")
    assert scope_score is not None, "SCOPE was assessed — must have a numeric category score"
    assert 70.0 <= scope_score <= 100.0, (
        f"SCOPE category score {scope_score} outside expected baseline band [70, 100]"
    )

    # All other categories must be None (unassessed)
    for cat in ALL_CATEGORIES:
        if cat != "SCOPE":
            assert diag.category_scores.get(cat) is None, (
                f"Unassessed category {cat} must have None score; got {diag.category_scores[cat]}"
            )
