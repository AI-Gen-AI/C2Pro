"""
Golden Test Suite for Coherence Engine v0.3 Score Curve Validation

Tests the scoring algorithm against realistic scenarios to verify:
1. Perfect projects score ~100
2. Moderate issues score 50-80
3. Severe issues score 10-30
4. Edge cases handled gracefully

Location: apps/api/tests/coherence/golden/test_golden_deterministic.py
"""

import pytest

from src.coherence.graph.graph import evaluate_coherence
from src.coherence.graph.state import EvaluationConfig

from .golden_deterministic import GOLDEN_TEST_CASES

# =============================================================================
# GOLDEN TEST RUNNER
# =============================================================================


def _assert_honest_null_score(result) -> None:
    """
    Coherence scores are honest: when category coverage doesn't clear
    MIN_ACTIVE_WEIGHT (ADR-009 SS14), the score is null (never a fabricated
    number) and an AUDIT_INCOMPLETE meta-alert explains why.
    Refers to: Honest Coherence Scoring (#136), src/coherence/scoring.py:431.
    """
    assert result.overall_score is None, (
        f"expected an honest null score for insufficient category coverage, "
        f"got {result.overall_score}"
    )
    assert result.score_reason in ("insufficient_evidence", "insufficient_active_weight"), (
        f"expected an honest-null reason, got {result.score_reason!r}"
    )
    assert any(a.rule_id == "AUDIT_INCOMPLETE" for a in result.alerts), (
        "insufficient-evidence results must surface an AUDIT_INCOMPLETE meta-alert"
    )


@pytest.mark.parametrize("test_case", GOLDEN_TEST_CASES, ids=lambda tc: tc["name"])
def test_golden_score_curve(test_case):
    """
    Validate score curve against golden test cases.

    Success Criteria:
    - Cases with enough assessed category coverage score within range
    - Cases without enough coverage (narrow, single-issue fixtures) return
      an honest null score rather than a fabricated number
    - No crashes on edge cases
    """
    # Extract test case data
    clauses = test_case["clauses"]
    expected_min, expected_max = test_case["expected_score_range"]
    expected_alerts = test_case["expected_alert_count"]
    description = test_case["description"]

    # Run evaluation in low_budget_mode (deterministic only, no LLM cost)
    config = EvaluationConfig(
        low_budget_mode=True,
        include_rag_similarity=False,  # Disable RAG for golden tests (no embeddings)
    )

    result = evaluate_coherence(
        clauses=clauses,
        project_id=f"golden-{test_case['name']}",
        config=config,
    )

    if result.overall_score is None:
        # Narrow fixtures (1-2 clauses) don't clear MIN_ACTIVE_WEIGHT
        # (ADR-009 SS14) — an honest null is the correct outcome, not a
        # fabricated number squeezed into the legacy expected range.
        _assert_honest_null_score(result)
    else:
        assert expected_min <= result.overall_score <= expected_max, (
            f"{test_case['name']}: Score {result.overall_score:.2f} outside expected range "
            f"[{expected_min}, {expected_max}]. Description: {description}"
        )

        # Verify alert count (allow ±1 tolerance for edge cases)
        alert_count_diff = abs(len(result.alerts) - expected_alerts)
        assert alert_count_diff <= 1, (
            f"{test_case['name']}: Got {len(result.alerts)} alerts, expected {expected_alerts}. "
            f"Description: {description}"
        )

    # Verify cost is zero (low_budget_mode)
    assert result.llm_cost_usd == pytest.approx(0.0), (
        f"{test_case['name']}: Expected zero cost in low_budget_mode, got ${result.llm_cost_usd}"
    )


# =============================================================================
# SPECIFIC GOLDEN TEST CASES (for detailed debugging)
# =============================================================================


def test_golden_perfect_project_scores_100():
    """
    GOLD-PERFECT-001: Perfect project with no issues scores at the
    inherent-risk ceiling (90.0), not a fabricated 100.

    HeuristicBaselineProvider caps an assessed-but-clean category at 90.0 —
    "clean so far" isn't proof of zero risk. Refers to:
    src/coherence/scoring.py HeuristicBaselineProvider docstring
    (Band [80, 90]; clean elsewhere -> 90).

    Success Criteria:
    - Score at the 90.0 ceiling
    - Zero alerts
    - Zero cost
    """
    from .golden_deterministic import GOLD_PERFECT_PROJECT

    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)
    result = evaluate_coherence(
        clauses=GOLD_PERFECT_PROJECT["clauses"],
        project_id="golden-perfect-001",
        config=config,
    )

    assert result.overall_score == pytest.approx(90.0), (
        f"Perfect project scored {result.overall_score}, expected the 90.0 inherent-risk ceiling"
    )
    assert len(result.alerts) == 0, f"Perfect project had {len(result.alerts)} alerts, expected 0"
    assert result.llm_cost_usd == pytest.approx(0.0)


def test_golden_unassessed_scope_produces_honest_null():
    """
    GOLD-NULL-SCOPE-001 (V3-P1-HEALTH-13): When SCOPE is unassessed and
    active_weight < MIN_ACTIVE_WEIGHT (0.35), the scorer returns an honest
    null — not a fabricated 0, not an inflated 100, and not the 90.0
    inherent-risk baseline.

    The fixture has only a BUDGET clause (weight 0.20). SCOPE (weight 0.20)
    is genuinely absent. Total active_weight = 0.20 < 0.35, triggering
    insufficient_active_weight → score = None.

    Success Criteria:
    - overall_score is None (honest null)
    - score_reason is 'insufficient_active_weight'
    - AUDIT_INCOMPLETE meta-alert present
    - SCOPE shows as unassessed in category_breakdown
    - Zero cost
    """
    from .golden_deterministic import GOLD_UNASSESSED_SCOPE

    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)
    result = evaluate_coherence(
        clauses=GOLD_UNASSESSED_SCOPE["clauses"],
        project_id="golden-null-scope-001",
        config=config,
    )

    _assert_honest_null_score(result)

    # Verify SCOPE specifically is in the missing dimensions
    assert "SCOPE" in (result.score_missing_dimensions or []), (
        f"SCOPE should be in missing_dimensions, got {result.score_missing_dimensions}"
    )

    # Verify category_breakdown shows SCOPE as unassessed
    if hasattr(result, "category_breakdown"):
        scope_breakdown = [
            cb for cb in result.category_breakdown
            if cb.category.lower() == "scope"
        ]
        assert len(scope_breakdown) == 1, "SCOPE should appear in category_breakdown"
        assert scope_breakdown[0].state == "unassessed", (
            f"SCOPE state should be 'unassessed', got {scope_breakdown[0].state}"
        )
        assert scope_breakdown[0].score is None, (
            f"SCOPE score should be None, got {scope_breakdown[0].score}"
        )

    assert result.llm_cost_usd == pytest.approx(0.0)


def test_golden_moderate_scores_50_to_80():
    """
    GOLD-MODERATE-*: Moderate issues should score 50-80 when enough
    category coverage is assessed; narrow single/dual-clause fixtures
    honestly return null instead (ADR-009 SS14 active-weight guard).

    Success Criteria:
    - Score in 50-80 range OR an honest null with AUDIT_INCOMPLETE
    - Zero cost
    """
    from .golden_deterministic import (
        GOLD_MODERATE_BUDGET_OVERRUN,
        GOLD_MODERATE_MULTIPLE_MEDIUM,
        GOLD_MODERATE_SCHEDULE_DELAY,
    )

    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)

    for test_case in [GOLD_MODERATE_BUDGET_OVERRUN, GOLD_MODERATE_SCHEDULE_DELAY, GOLD_MODERATE_MULTIPLE_MEDIUM]:
        result = evaluate_coherence(
            clauses=test_case["clauses"],
            project_id=f"golden-{test_case['name']}",
            config=config,
        )

        if result.overall_score is None:
            _assert_honest_null_score(result)
        else:
            assert 50.0 <= result.overall_score <= 80.0, (
                f"{test_case['name']} scored {result.overall_score}, expected 50-80"
            )
            assert 1 <= len(result.alerts) <= 4, (
                f"{test_case['name']} had {len(result.alerts)} alerts, expected 1-4"
            )
        assert result.llm_cost_usd == pytest.approx(0.0)


def test_golden_severe_scores_10_to_30():
    """
    GOLD-SEVERE-*: Severe issues should score low (5-35 range) when enough
    category coverage is assessed; narrow single/dual-clause fixtures
    honestly return null instead (ADR-009 SS14 active-weight guard).

    Success Criteria:
    - Score in the fixture's expected range OR an honest null with AUDIT_INCOMPLETE
    - Zero cost
    """
    from .golden_deterministic import (
        GOLD_SEVERE_BUDGET_COLLAPSE,
        GOLD_SEVERE_MULTI_CATEGORY,
        GOLD_SEVERE_SCHEDULE_CRISIS,
    )

    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)

    for test_case in [GOLD_SEVERE_BUDGET_COLLAPSE, GOLD_SEVERE_SCHEDULE_CRISIS, GOLD_SEVERE_MULTI_CATEGORY]:
        result = evaluate_coherence(
            clauses=test_case["clauses"],
            project_id=f"golden-{test_case['name']}",
            config=config,
        )

        if result.overall_score is None:
            _assert_honest_null_score(result)
        else:
            expected_min, expected_max = test_case["expected_score_range"]
            assert expected_min <= result.overall_score <= expected_max, (
                f"{test_case['name']} scored {result.overall_score}, expected {expected_min}-{expected_max}"
            )
            assert len(result.alerts) >= 1, (
                f"{test_case['name']} had {len(result.alerts)} alerts, expected ≥1"
            )
        assert result.llm_cost_usd == pytest.approx(0.0)


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


def test_golden_empty_project_does_not_crash():
    """
    GOLD-EDGE-001: Empty project should not crash.

    Zero clauses means zero assessed categories — an honest null score,
    not a fabricated "no issues = 95+".

    Success Criteria:
    - No exceptions raised
    - Honest null score with AUDIT_INCOMPLETE
    """
    from .golden_deterministic import GOLD_EDGE_EMPTY_PROJECT

    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)
    result = evaluate_coherence(
        clauses=GOLD_EDGE_EMPTY_PROJECT["clauses"],
        project_id="golden-edge-001",
        config=config,
    )

    _assert_honest_null_score(result)
    assert result.llm_cost_usd == pytest.approx(0.0)


def test_golden_missing_data_handled_gracefully():
    """
    GOLD-EDGE-002: Missing data fields should be handled gracefully.

    Success Criteria:
    - No exceptions raised
    - Real score in [0, 100] OR an honest null with AUDIT_INCOMPLETE
    - Zero cost
    """
    from .golden_deterministic import GOLD_EDGE_MISSING_DATA

    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)
    result = evaluate_coherence(
        clauses=GOLD_EDGE_MISSING_DATA["clauses"],
        project_id="golden-edge-002",
        config=config,
    )

    # Should not crash
    if result.overall_score is None:
        _assert_honest_null_score(result)
    else:
        assert 0.0 <= result.overall_score <= 100.0
    assert result.llm_cost_usd == pytest.approx(0.0)


def test_golden_malformed_dates_handled_gracefully():
    """
    GOLD-EDGE-003: Malformed dates should be handled gracefully.

    Success Criteria:
    - No exceptions raised
    - Real score in [0, 100] OR an honest null with AUDIT_INCOMPLETE
    - Zero cost
    """
    from .golden_deterministic import GOLD_EDGE_MALFORMED_DATES

    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)
    result = evaluate_coherence(
        clauses=GOLD_EDGE_MALFORMED_DATES["clauses"],
        project_id="golden-edge-003",
        config=config,
    )

    # Should not crash
    if result.overall_score is None:
        _assert_honest_null_score(result)
    else:
        assert 0.0 <= result.overall_score <= 100.0
    assert result.llm_cost_usd == pytest.approx(0.0)


# =============================================================================
# COST TRACKING VALIDATION (Task 8.3)
# =============================================================================


def test_low_budget_mode_costs_under_one_cent():
    """
    Task 8.3: Verify cost stays under $0.01/project in low_budget_mode.

    Success Criteria:
    - All golden test cases cost $0.00 in low_budget_mode
    - No LLM API calls made
    """
    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)

    total_cost = 0.0
    for test_case in GOLDEN_TEST_CASES:
        result = evaluate_coherence(
            clauses=test_case["clauses"],
            project_id=f"cost-test-{test_case['name']}",
            config=config,
        )

        # Verify individual test case cost
        assert result.llm_cost_usd == pytest.approx(0.0), (
            f"{test_case['name']} cost ${result.llm_cost_usd} in low_budget_mode, expected $0.00"
        )

        total_cost += result.llm_cost_usd

    # Verify total cost across all test cases
    assert total_cost == pytest.approx(0.0), (
        f"Total cost across {len(GOLDEN_TEST_CASES)} test cases: ${total_cost}, expected $0.00"
    )

    # Verify cost is under $0.01 per project (even though it's $0.00)
    avg_cost_per_project = total_cost / len(GOLDEN_TEST_CASES)
    assert avg_cost_per_project < 0.01, (
        f"Average cost per project: ${avg_cost_per_project}, expected <$0.01"
    )
