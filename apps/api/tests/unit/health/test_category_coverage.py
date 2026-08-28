"""TS-UD-HEALTH-024-L4-1 — single-document category-coverage domain (ADR-024 / ADR-018, P0b L4-1).

Honest per-category coverage for ONE document across the six canonical categories:
evidence-backed => PRESENT; otherwise INSUFFICIENT_EVIDENCE with an actionable gap.
Never a fabricated zero/green (INV-1); null/unknown is not a numeric zero. Relational
Coherence is OUT OF SCOPE for a single document (no coherence_subscore here).
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from src.coherence.domain.category_weights import CoherenceCategory
from src.health.domain.category_coverage import (
    CategoryCoverage,
    CategoryCoverageState,
    CategoryGapAlert,
    compute_category_coverage,
    gap_alerts,
)
from src.health.domain.health_vector import HealthNullReason

ALL_CATEGORIES: tuple[CoherenceCategory, ...] = tuple(CoherenceCategory)


def _for(coverage: tuple[CategoryCoverage, ...], category: CoherenceCategory) -> CategoryCoverage:
    return next(c for c in coverage if c.category == category)


def test_computes_exactly_the_six_canonical_categories() -> None:
    coverage = compute_category_coverage({})
    assert len(coverage) == 6
    assert {c.category for c in coverage} == set(ALL_CATEGORIES)


def test_covered_category_is_present_and_produces_no_gap() -> None:
    coverage = compute_category_coverage({CoherenceCategory.SCOPE: 3})
    scope = _for(coverage, CoherenceCategory.SCOPE)
    assert scope.state is CategoryCoverageState.PRESENT
    assert scope.evidence_count == 3
    assert scope.null_reason is None
    assert scope.missing_data == ()
    assert CoherenceCategory.SCOPE not in {g.category for g in gap_alerts(coverage)}


def test_absent_category_is_insufficient_evidence_with_actionable_gap() -> None:
    coverage = compute_category_coverage({CoherenceCategory.SCOPE: 1})
    technical = _for(coverage, CoherenceCategory.TECHNICAL)
    assert technical.state is CategoryCoverageState.INSUFFICIENT_EVIDENCE
    assert technical.evidence_count == 0
    assert technical.null_reason is HealthNullReason.INSUFFICIENT_EVIDENCE
    assert technical.missing_data  # states what is missing
    gaps = gap_alerts(coverage)
    technical_gap = next(g for g in gaps if g.category is CoherenceCategory.TECHNICAL)
    assert isinstance(technical_gap, CategoryGapAlert)
    assert technical_gap.action.strip()
    assert "TECHNICAL" in technical_gap.action  # actionable + names the category


def test_missing_data_is_factual_not_an_instruction() -> None:
    # ADR-024 {missing_data} facet: a factual "not detected" statement, not an action.
    coverage = compute_category_coverage({})
    time_cov = _for(coverage, CoherenceCategory.TIME)
    assert time_cov.missing_data == ("project schedule / cronograma not detected",)
    assert "Upload" not in time_cov.missing_data[0]


def test_gap_action_and_missing_data_are_distinct_semantic_fields() -> None:
    coverage = compute_category_coverage({})
    time_cov = _for(coverage, CoherenceCategory.TIME)
    time_gap = next(g for g in gap_alerts(coverage) if g.category is CoherenceCategory.TIME)
    # gap alert = actionable instruction
    assert time_gap.action == "Upload the project schedule (cronograma) to assess TIME."
    assert time_gap.action.startswith("Upload")
    # the two fields carry different semantics and must not be the same string
    assert time_cov.missing_data[0] != time_gap.action


def test_all_present_yields_zero_gaps() -> None:
    coverage = compute_category_coverage(dict.fromkeys(ALL_CATEGORIES, 1))
    assert all(c.state is CategoryCoverageState.PRESENT for c in coverage)
    assert gap_alerts(coverage) == ()


def test_empty_input_yields_six_gaps() -> None:
    coverage = compute_category_coverage({})
    assert all(c.state is CategoryCoverageState.INSUFFICIENT_EVIDENCE for c in coverage)
    gaps = gap_alerts(coverage)
    assert len(gaps) == 6
    assert {g.category for g in gaps} == set(ALL_CATEGORIES)


def test_partial_coverage_gaps_are_exactly_the_absent_categories() -> None:
    present = {CoherenceCategory.SCOPE: 2, CoherenceCategory.BUDGET: 1, CoherenceCategory.TIME: 5}
    coverage = compute_category_coverage(present)
    gaps = gap_alerts(coverage)
    assert {g.category for g in gaps} == set(ALL_CATEGORIES) - set(present)
    assert len(gaps) == 3


def test_zero_count_is_insufficient_evidence() -> None:
    coverage = compute_category_coverage({CoherenceCategory.BUDGET: 0})
    budget = _for(coverage, CoherenceCategory.BUDGET)
    assert budget.state is CategoryCoverageState.INSUFFICIENT_EVIDENCE
    assert budget.evidence_count == 0


def test_negative_count_is_rejected_not_insufficient() -> None:
    # Invalid input is a programming/domain error, NOT an honest-null product state.
    with pytest.raises(ValueError):
        compute_category_coverage({CoherenceCategory.SCOPE: -4})


def test_bool_value_is_rejected() -> None:
    bad: dict[CoherenceCategory, Any] = {CoherenceCategory.SCOPE: True}
    with pytest.raises(TypeError):
        compute_category_coverage(bad)


def test_non_integer_value_is_rejected() -> None:
    bad_values: list[Any] = [1.5, "3", None]
    for value in bad_values:
        with pytest.raises(TypeError):
            compute_category_coverage({CoherenceCategory.SCOPE: value})


def test_unknown_non_category_key_is_rejected() -> None:
    bad: dict[Any, Any] = {"SCOPE": 1}  # a bare string is not a CoherenceCategory
    with pytest.raises(TypeError):
        compute_category_coverage(bad)


def test_inv1_present_without_evidence_is_rejected() -> None:
    # A PRESENT coverage with zero evidence is a fabricated green — must be rejected.
    with pytest.raises(ValidationError):
        CategoryCoverage(
            category=CoherenceCategory.SCOPE,
            state=CategoryCoverageState.PRESENT,
            evidence_count=0,
        )


def test_inv1_insufficient_cannot_carry_evidence() -> None:
    with pytest.raises(ValidationError):
        CategoryCoverage(
            category=CoherenceCategory.SCOPE,
            state=CategoryCoverageState.INSUFFICIENT_EVIDENCE,
            evidence_count=2,
            missing_data=("x",),
            null_reason=HealthNullReason.INSUFFICIENT_EVIDENCE,
        )


def test_insufficient_requires_null_reason_and_missing_data() -> None:
    with pytest.raises(ValidationError):
        CategoryCoverage(
            category=CoherenceCategory.SCOPE,
            state=CategoryCoverageState.INSUFFICIENT_EVIDENCE,
            evidence_count=0,
        )


def test_null_is_not_a_numeric_zero() -> None:
    # INSUFFICIENT_EVIDENCE is a distinct state, never a 0 score — L4-1 emits no score at all.
    coverage = compute_category_coverage({})
    item = coverage[0]
    assert item.state is CategoryCoverageState.INSUFFICIENT_EVIDENCE
    assert not hasattr(item, "score")


def test_coverage_items_are_immutable() -> None:
    coverage = compute_category_coverage({CoherenceCategory.SCOPE: 1})
    assert isinstance(coverage, tuple)
    with pytest.raises(ValidationError):
        coverage[0].evidence_count = 99  # frozen contract
