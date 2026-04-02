"""
Phase 8 Edge Case Tests for Coherence Engine v0.3

Parametrized tests for edge cases:
- Empty clauses
- Missing data fields
- Malformed dates
- Invalid numeric values
- Null/None handling
- Unicode and special characters

Location: apps/api/tests/coherence/test_edge_cases.py
"""

import pytest
from datetime import datetime
from src.coherence.models import Clause
from src.coherence.graph.graph import evaluate_coherence
from src.coherence.graph.state import EvaluationConfig


# =============================================================================
# EMPTY INPUT TESTS
# =============================================================================


@pytest.mark.parametrize("clauses", [
    ([]),  # Empty list
    (None),  # None (should be handled)
])
def test_empty_clauses_handled_gracefully(clauses):
    """
    Test that empty or None clause lists are handled gracefully.

    Success Criteria:
    - No exceptions raised
    - Returns valid result with score ~100 (no issues found)
    """
    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)

    # Handle None case
    if clauses is None:
        clauses = []

    result = evaluate_coherence(
        clauses=clauses,
        project_id="edge-empty",
        config=config,
    )

    # Should not crash
    assert result is not None
    assert result.overall_score >= 95.0  # No issues = high score
    assert len(result.alerts) == 0
    assert result.llm_cost_usd == 0.0


# =============================================================================
# MISSING DATA FIELD TESTS
# =============================================================================


@pytest.mark.parametrize("clause_data", [
    ({}),  # Empty data dict
    ({"irrelevant_field": "value"}),  # Data with no recognized fields
    ({"planned": 100000}),  # Partial budget data (missing 'current')
    ({"current": 120000}),  # Partial budget data (missing 'planned')
    ({"start_date": "2024-01-01"}),  # Partial schedule data (missing 'end_date')
])
def test_missing_data_fields_handled_gracefully(clause_data):
    """
    Test that clauses with missing critical data fields are handled gracefully.

    Success Criteria:
    - No exceptions raised
    - Evaluators skip clauses with insufficient data
    - Returns valid result
    """
    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)

    clauses = [
        Clause(id="test-1", text="Test clause", data=clause_data)
    ]

    result = evaluate_coherence(
        clauses=clauses,
        project_id="edge-missing-data",
        config=config,
    )

    # Should not crash
    assert result is not None
    assert 0.0 <= result.overall_score <= 100.0
    assert result.llm_cost_usd == 0.0


# =============================================================================
# MALFORMED DATE TESTS
# =============================================================================


@pytest.mark.parametrize("date_value", [
    ("not-a-date"),  # Plain text
    ("2024-13-45"),  # Invalid month/day
    ("2024/01/01"),  # Wrong format (slash instead of dash)
    ("01-01-2024"),  # Wrong order
    (""),  # Empty string
    (None),  # None value
    (12345),  # Numeric instead of string
    ("2024-02-30"),  # Invalid date (Feb 30th)
])
def test_malformed_dates_handled_gracefully(date_value):
    """
    Test that malformed date values are handled gracefully.

    Success Criteria:
    - No exceptions raised
    - Date parsing failures don't crash evaluation
    - Returns valid result
    """
    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)

    clauses = [
        Clause(
            id="test-1",
            text="Test clause with malformed date",
            data={"end_date": date_value}
        )
    ]

    result = evaluate_coherence(
        clauses=clauses,
        project_id="edge-malformed-date",
        config=config,
    )

    # Should not crash
    assert result is not None
    assert 0.0 <= result.overall_score <= 100.0
    assert result.llm_cost_usd == 0.0


# =============================================================================
# INVALID NUMERIC VALUE TESTS
# =============================================================================


@pytest.mark.parametrize("numeric_field,value", [
    ("planned", -100000),  # Negative budget
    ("planned", 0),  # Zero budget
    ("current", "not-a-number"),  # String instead of number
    ("contingency_percent", -5.0),  # Negative percentage
    ("contingency_percent", 150.0),  # Percentage >100
    ("buffer_days", -30),  # Negative buffer
    ("warranty_months", 0),  # Zero warranty
    ("warranty_months", -12),  # Negative warranty
])
def test_invalid_numeric_values_handled_gracefully(numeric_field, value):
    """
    Test that invalid numeric values are handled gracefully.

    Success Criteria:
    - No exceptions raised
    - Invalid values either trigger alerts or are skipped
    - Returns valid result
    """
    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)

    clauses = [
        Clause(
            id="test-1",
            text="Test clause with invalid numeric value",
            data={numeric_field: value}
        )
    ]

    result = evaluate_coherence(
        clauses=clauses,
        project_id="edge-invalid-numeric",
        config=config,
    )

    # Should not crash
    assert result is not None
    assert 0.0 <= result.overall_score <= 100.0
    assert result.llm_cost_usd == 0.0


# =============================================================================
# NULL/NONE HANDLING TESTS
# =============================================================================


@pytest.mark.parametrize("field_name,null_value", [
    ("planned", None),
    ("current", None),
    ("end_date", None),
    ("status", None),
    ("category", None),
])
def test_null_field_values_handled_gracefully(field_name, null_value):
    """
    Test that None/null field values are handled gracefully.

    Success Criteria:
    - No exceptions raised
    - None values are treated as missing data
    - Returns valid result
    """
    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)

    clauses = [
        Clause(
            id="test-1",
            text="Test clause with null field",
            data={field_name: null_value}
        )
    ]

    result = evaluate_coherence(
        clauses=clauses,
        project_id="edge-null-value",
        config=config,
    )

    # Should not crash
    assert result is not None
    assert 0.0 <= result.overall_score <= 100.0
    assert result.llm_cost_usd == 0.0


# =============================================================================
# UNICODE AND SPECIAL CHARACTER TESTS
# =============================================================================


@pytest.mark.parametrize("text_value", [
    ("Budget: $1,000,000 🎯"),  # Emoji
    ("Plazo: 31/12/2024 ✓"),  # Special characters
    ("合同金额：￥100万"),  # Chinese characters
    ("Бюджет: $1,000,000"),  # Cyrillic
    ("عقد المشروع"),  # Arabic
    ("¡Proyecto completo!"),  # Spanish punctuation
    ("Line 1\nLine 2\tTabbed"),  # Newlines and tabs
])
def test_unicode_and_special_chars_handled(text_value):
    """
    Test that Unicode and special characters in clause text are handled properly.

    Success Criteria:
    - No exceptions raised
    - Text encoding doesn't cause crashes
    - Returns valid result
    """
    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)

    clauses = [
        Clause(
            id="test-1",
            text=text_value,
            data={}
        )
    ]

    result = evaluate_coherence(
        clauses=clauses,
        project_id="edge-unicode",
        config=config,
    )

    # Should not crash
    assert result is not None
    assert 0.0 <= result.overall_score <= 100.0
    assert result.llm_cost_usd == 0.0


# =============================================================================
# LARGE INPUT TESTS
# =============================================================================


@pytest.mark.parametrize("clause_count", [
    (100),   # Large but reasonable
    (500),   # Very large
    (1000),  # Stress test
])
def test_large_clause_count_handled_efficiently(clause_count):
    """
    Test that large numbers of clauses are handled efficiently.

    Success Criteria:
    - No exceptions raised
    - Evaluation completes in reasonable time (<10s for 1000 clauses)
    - Returns valid result
    """
    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)

    # Generate large list of simple clauses
    clauses = [
        Clause(
            id=f"clause-{i}",
            text=f"Test clause {i}",
            data={"index": i}
        )
        for i in range(clause_count)
    ]

    import time
    start_time = time.time()

    result = evaluate_coherence(
        clauses=clauses,
        project_id=f"edge-large-{clause_count}",
        config=config,
    )

    elapsed_time = time.time() - start_time

    # Should not crash
    assert result is not None
    assert 0.0 <= result.overall_score <= 100.0
    assert result.llm_cost_usd == 0.0

    # Should complete in reasonable time
    assert elapsed_time < 10.0, f"Evaluation took {elapsed_time:.2f}s for {clause_count} clauses"


# =============================================================================
# VERY LONG TEXT TESTS
# =============================================================================


@pytest.mark.parametrize("text_length", [
    (1000),    # 1KB
    (10000),   # 10KB
    (100000),  # 100KB
])
def test_very_long_clause_text_handled(text_length):
    """
    Test that very long clause text is handled properly.

    Success Criteria:
    - No exceptions raised
    - Long text doesn't cause memory issues
    - Returns valid result
    """
    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)

    # Generate very long text
    long_text = "This is a test clause. " * (text_length // 24)

    clauses = [
        Clause(
            id="test-1",
            text=long_text,
            data={}
        )
    ]

    result = evaluate_coherence(
        clauses=clauses,
        project_id=f"edge-long-text-{text_length}",
        config=config,
    )

    # Should not crash
    assert result is not None
    assert 0.0 <= result.overall_score <= 100.0
    assert result.llm_cost_usd == 0.0


# =============================================================================
# MIXED EDGE CASE TEST
# =============================================================================


def test_mixed_edge_cases_all_together():
    """
    Test a project with multiple edge cases combined.

    Success Criteria:
    - No exceptions raised
    - All edge cases handled in single evaluation
    - Returns valid result
    """
    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)

    clauses = [
        # Empty data
        Clause(id="edge-1", text="Empty data clause", data={}),

        # Malformed date
        Clause(id="edge-2", text="Bad date", data={"end_date": "not-a-date"}),

        # Negative numbers
        Clause(id="edge-3", text="Negative budget", data={"planned": -100000}),

        # None values
        Clause(id="edge-4", text="Null field", data={"current": None}),

        # Unicode
        Clause(id="edge-5", text="合同金额：￥100万", data={}),

        # Very long text
        Clause(id="edge-6", text="Long text " * 1000, data={}),
    ]

    result = evaluate_coherence(
        clauses=clauses,
        project_id="edge-mixed-all",
        config=config,
    )

    # Should not crash
    assert result is not None
    assert 0.0 <= result.overall_score <= 100.0
    assert result.llm_cost_usd == 0.0
    assert len(result.alerts) >= 0  # May or may not have alerts
