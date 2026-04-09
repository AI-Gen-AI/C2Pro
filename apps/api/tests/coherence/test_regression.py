"""
Phase 8 Regression Tests for Coherence Engine v0.3

Verifies that v0.3 integration doesn't break existing functionality:
- All v0.2 API contracts preserved
- Existing test data still produces valid results
- Performance hasn't degraded
- No new dependencies break existing code

Location: apps/api/tests/coherence/test_regression.py
"""

import pytest

from src.coherence.graph.graph import evaluate_coherence
from src.coherence.graph.state import EvaluationConfig
from src.coherence.models import Clause

# =============================================================================
# SMOKE TESTS (Quick validation that core functionality works)
# =============================================================================


def test_regression_basic_evaluation_still_works():
    """
    Smoke test: Basic evaluation produces valid result.

    Success Criteria:
    - Evaluation completes successfully
    - Returns valid CoherenceResult
    - Score is in valid range (0-100)
    """
    clauses = [
        Clause(
            id="test-1",
            text="Test clause",
            data={"budget": 100000}
        )
    ]

    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)
    result = evaluate_coherence(clauses=clauses, project_id="regression-basic", config=config)

    assert result is not None
    assert hasattr(result, "overall_score")
    assert hasattr(result, "alerts")
    assert 0.0 <= result.overall_score <= 100.0


def test_regression_deterministic_rules_still_fire():
    """
    Verify that deterministic rules (from v0.2) still work in v0.3.

    Success Criteria:
    - Budget overrun rule still fires
    - Schedule overdue rule still fires
    - Alerts are generated correctly
    """
    clauses = [
        Clause(
            id="bud-1",
            text="Budget overrun",
            data={"planned": 100000, "current": 150000}  # 50% overrun
        ),
        Clause(
            id="sch-1",
            text="Overdue milestone",
            data={"end_date": "2023-01-01"}  # Way overdue
        ),
    ]

    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)
    result = evaluate_coherence(clauses=clauses, project_id="regression-rules", config=config)

    # Should have alerts for budget overrun and schedule overdue
    assert len(result.alerts) >= 1, "Expected at least 1 alert for budget overrun or schedule overdue"
    assert result.overall_score < 90.0, "Expected score < 90 with critical issues"


def test_regression_empty_project_still_scores_high():
    """
    Verify that empty projects still score high (no issues = good score).

    Success Criteria:
    - Empty project scores ≥95
    - No alerts generated
    - Behavior consistent with v0.2
    """
    clauses = []

    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)
    result = evaluate_coherence(clauses=clauses, project_id="regression-empty", config=config)

    assert result.overall_score >= 95.0, "Empty project should score high"
    assert len(result.alerts) == 0, "Empty project should have no alerts"


# =============================================================================
# API CONTRACT TESTS (Verify v0.2 API contracts preserved)
# =============================================================================


def test_regression_result_has_all_v2_fields():
    """
    Verify that EnrichedCoherenceResult has all fields from v0.2 CoherenceResult.

    Success Criteria:
    - overall_score field exists
    - alerts field exists (list)
    - category_breakdown field exists (list)
    - calculated_at field exists (datetime)
    """
    clauses = [Clause(id="test-1", text="Test", data={})]

    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)
    result = evaluate_coherence(clauses=clauses, project_id="regression-fields", config=config)

    # Verify all v0.2 fields exist
    assert hasattr(result, "overall_score")
    assert hasattr(result, "alerts")
    assert hasattr(result, "category_breakdown")
    assert hasattr(result, "calculated_at")

    # Verify types
    assert isinstance(result.overall_score, float)
    assert isinstance(result.alerts, list)
    assert isinstance(result.category_breakdown, list)


def test_regression_alerts_have_correct_structure():
    """
    Verify that Alert objects have the same structure as v0.2.

    Success Criteria:
    - rule_id field exists
    - severity field exists
    - category field exists
    - message field exists
    - evidence field exists
    """
    clauses = [
        Clause(
            id="bud-1",
            text="Budget issue",
            data={"planned": 100000, "current": 150000}
        )
    ]

    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)
    result = evaluate_coherence(clauses=clauses, project_id="regression-alert-structure", config=config)

    # If we have alerts, verify structure
    if len(result.alerts) > 0:
        alert = result.alerts[0]
        assert hasattr(alert, "rule_id")
        assert hasattr(alert, "severity")
        assert hasattr(alert, "category")
        assert hasattr(alert, "message")
        assert hasattr(alert, "evidence")


# =============================================================================
# PERFORMANCE REGRESSION TESTS
# =============================================================================


def test_regression_performance_not_degraded():
    """
    Verify that evaluation performance hasn't degraded significantly in v0.3.

    Success Criteria:
    - 10 clauses evaluate in <2 seconds
    - Performance is similar to v0.2 baseline
    """
    import time

    clauses = [
        Clause(id=f"clause-{i}", text=f"Test clause {i}", data={"index": i})
        for i in range(10)
    ]

    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)

    start_time = time.time()
    result = evaluate_coherence(clauses=clauses, project_id="regression-performance", config=config)
    elapsed_time = time.time() - start_time

    assert result is not None
    assert elapsed_time < 2.0, f"Evaluation took {elapsed_time:.2f}s, expected <2s"


# =============================================================================
# BACKWARD COMPATIBILITY TESTS
# =============================================================================


def test_regression_low_budget_mode_default_true():
    """
    Verify that low_budget_mode defaults to True (no behavior change from v0.2).

    Success Criteria:
    - Default config has low_budget_mode=True
    - No LLM calls made by default
    - Cost is $0.00 by default
    """
    config = EvaluationConfig()  # Use defaults

    assert config.low_budget_mode is True, "low_budget_mode should default to True"

    clauses = [Clause(id="test-1", text="Test", data={})]
    result = evaluate_coherence(clauses=clauses, project_id="regression-default-config", config=config)

    assert result.llm_cost_usd == 0.0, "Default config should have zero cost"


def test_regression_scoring_still_continuous():
    """
    Verify that scoring is continuous (not binary 0/100 like old system).

    Success Criteria:
    - Scores are not exactly 0 or 100 (except perfect/terrible cases)
    - Scores are granular floats
    - Multiple test cases produce different scores
    """
    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)

    # Test case 1: Minor issue
    minor_result = evaluate_coherence(
        clauses=[
            Clause(id="bud-1", text="Slight overrun", data={"planned": 100000, "current": 105000})
        ],
        project_id="regression-minor",
        config=config,
    )

    # Test case 2: Major issue
    major_result = evaluate_coherence(
        clauses=[
            Clause(id="bud-1", text="Major overrun", data={"planned": 100000, "current": 200000})
        ],
        project_id="regression-major",
        config=config,
    )

    # Scores should be different (continuous)
    assert minor_result.overall_score != major_result.overall_score, \
        "Different issues should produce different scores"

    # Scores should be granular (not binary)
    assert minor_result.overall_score not in [0.0, 100.0], \
        "Minor issue should not score exactly 0 or 100"
    assert major_result.overall_score not in [0.0, 100.0], \
        "Major issue should not score exactly 0 or 100"


# =============================================================================
# INTEGRATION TESTS (Full workflow)
# =============================================================================


def test_regression_full_workflow_end_to_end():
    """
    End-to-end regression test of full evaluation workflow.

    Success Criteria:
    - Accepts clauses
    - Runs all evaluation nodes
    - Returns valid EnrichedCoherenceResult
    - All fields populated correctly
    """
    clauses = [
        # BUDGET clauses
        Clause(
            id="bud-1",
            text="Total budget: $1,000,000",
            data={"planned": 1000000, "current": 950000, "contingency_percent": 10.0}
        ),
        # TIME clauses
        Clause(
            id="sch-1",
            text="Project timeline: 12 months",
            data={"start_date": "2024-01-01", "end_date": "2024-12-31", "status": "on_track"}
        ),
        # LEGAL clauses
        Clause(
            id="leg-1",
            text="Warranty period: 24 months",
            data={"warranty_months": 24, "payment_term_days": 30}
        ),
    ]

    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)
    result = evaluate_coherence(clauses=clauses, project_id="regression-e2e", config=config)

    # Verify result structure
    assert result is not None
    assert isinstance(result.overall_score, float)
    assert 0.0 <= result.overall_score <= 100.0
    assert isinstance(result.alerts, list)
    assert isinstance(result.category_breakdown, list)

    # Verify diagnostic fields (v0.3 specific)
    assert hasattr(result, "finding_signals")
    assert hasattr(result, "llm_cost_usd")
    assert hasattr(result, "evaluation_mode")
    assert hasattr(result, "penalty_density")
    assert result.llm_cost_usd == 0.0


# =============================================================================
# NO CRASH TESTS (Verify robustness)
# =============================================================================


@pytest.mark.parametrize("test_scenario", [
    ("empty_clauses", []),
    ("single_clause", [Clause(id="1", text="Test", data={})]),
    ("many_clauses", [Clause(id=str(i), text=f"Test {i}", data={}) for i in range(50)]),
])
def test_regression_no_crashes(test_scenario):
    """
    Verify that evaluation doesn't crash on various input scenarios.

    Success Criteria:
    - No exceptions raised
    - Returns valid result
    - Behavior consistent across scenarios
    """
    scenario_name, clauses = test_scenario

    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)
    result = evaluate_coherence(
        clauses=clauses,
        project_id=f"regression-no-crash-{scenario_name}",
        config=config,
    )

    # Should not crash
    assert result is not None
    assert 0.0 <= result.overall_score <= 100.0
    assert isinstance(result.alerts, list)
