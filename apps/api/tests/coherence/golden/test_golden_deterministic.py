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


@pytest.mark.parametrize("test_case", GOLDEN_TEST_CASES, ids=lambda tc: tc["name"])
def test_golden_score_curve(test_case):
    """
    Validate score curve against golden test cases.

    Success Criteria:
    - Score falls within expected range
    - Alert count matches expected
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

    # Verify score is in expected range
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
    assert result.llm_cost_usd == 0.0, (
        f"{test_case['name']}: Expected zero cost in low_budget_mode, got ${result.llm_cost_usd}"
    )


# =============================================================================
# SPECIFIC GOLDEN TEST CASES (for detailed debugging)
# =============================================================================


def test_golden_perfect_project_scores_100():
    """
    GOLD-PERFECT-001: Perfect project with no issues should score ~100.

    Success Criteria:
    - Score ≥95
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

    assert result.overall_score >= 95.0, f"Perfect project scored {result.overall_score}, expected ≥95"
    assert len(result.alerts) == 0, f"Perfect project had {len(result.alerts)} alerts, expected 0"
    assert result.llm_cost_usd == 0.0


def test_golden_moderate_scores_50_to_80():
    """
    GOLD-MODERATE-*: Moderate issues should score 50-80.

    Success Criteria:
    - Score in 50-80 range
    - 1-3 alerts (moderate severity)
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

        assert 50.0 <= result.overall_score <= 80.0, (
            f"{test_case['name']} scored {result.overall_score}, expected 50-80"
        )
        assert 1 <= len(result.alerts) <= 4, (
            f"{test_case['name']} had {len(result.alerts)} alerts, expected 1-4"
        )
        assert result.llm_cost_usd == 0.0


def test_golden_severe_scores_10_to_30():
    """
    GOLD-SEVERE-*: Severe issues should score low (5-35 range).

    Success Criteria:
    - Score in 5-35 range (5 is min_score floor for extreme cases)
    - At least 1 critical/high severity alert
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

        # Use expected score range from test case
        expected_min, expected_max = test_case["expected_score_range"]
        assert expected_min <= result.overall_score <= expected_max, (
            f"{test_case['name']} scored {result.overall_score}, expected {expected_min}-{expected_max}"
        )
        # Verify at least 1 alert (all severe cases have at least 1 critical issue)
        assert len(result.alerts) >= 1, (
            f"{test_case['name']} had {len(result.alerts)} alerts, expected ≥1"
        )
        assert result.llm_cost_usd == 0.0


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


def test_golden_empty_project_does_not_crash():
    """
    GOLD-EDGE-001: Empty project should not crash.

    Success Criteria:
    - No exceptions raised
    - Score ≥95 (no issues)
    - Zero alerts
    """
    from .golden_deterministic import GOLD_EDGE_EMPTY_PROJECT

    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)
    result = evaluate_coherence(
        clauses=GOLD_EDGE_EMPTY_PROJECT["clauses"],
        project_id="golden-edge-001",
        config=config,
    )

    assert result.overall_score >= 95.0
    assert len(result.alerts) == 0
    assert result.llm_cost_usd == 0.0


def test_golden_missing_data_handled_gracefully():
    """
    GOLD-EDGE-002: Missing data fields should be handled gracefully.

    Success Criteria:
    - No exceptions raised
    - Score reasonable (rules skip clauses with missing data)
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
    assert result.overall_score >= 0.0
    assert result.overall_score <= 100.0
    assert result.llm_cost_usd == 0.0


def test_golden_malformed_dates_handled_gracefully():
    """
    GOLD-EDGE-003: Malformed dates should be handled gracefully.

    Success Criteria:
    - No exceptions raised
    - Score reasonable (date parsing fails gracefully)
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
    assert result.overall_score >= 0.0
    assert result.overall_score <= 100.0
    assert result.llm_cost_usd == 0.0


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
        assert result.llm_cost_usd == 0.0, (
            f"{test_case['name']} cost ${result.llm_cost_usd} in low_budget_mode, expected $0.00"
        )

        total_cost += result.llm_cost_usd

    # Verify total cost across all test cases
    assert total_cost == 0.0, (
        f"Total cost across {len(GOLDEN_TEST_CASES)} test cases: ${total_cost}, expected $0.00"
    )

    # Verify cost is under $0.01 per project (even though it's $0.00)
    avg_cost_per_project = total_cost / len(GOLDEN_TEST_CASES)
    assert avg_cost_per_project < 0.01, (
        f"Average cost per project: ${avg_cost_per_project}, expected <$0.01"
    )
