"""
Tests for ECOA v2 domain constants (ADR-009 §2.2, §13, §14).

Refers to Suite ID: TS-UD-COH-V2-CONST-001.
"""
from __future__ import annotations

import pytest

from src.coherence.domain.v2_constants import (
    DEFAULT_CATEGORY_WEIGHTS,
    MIN_ACTIVE_WEIGHT,
    MIN_EVIDENCE_BY_CATEGORY,
    SEVERITY_MULTIPLIERS,
)


@pytest.mark.unit
def test_thresholds_match_adr_009() -> None:
    assert {
        "SCOPE": 2,
        "BUDGET": 3,
        "QUALITY": 2,
        "TECHNICAL": 2,
        "LEGAL": 1,
        "TIME": 2,
    } == MIN_EVIDENCE_BY_CATEGORY


@pytest.mark.unit
def test_weights_sum_to_one() -> None:
    total = sum(DEFAULT_CATEGORY_WEIGHTS.values())
    assert pytest.approx(total, abs=1e-9) == 1.0
    assert set(DEFAULT_CATEGORY_WEIGHTS) == set(MIN_EVIDENCE_BY_CATEGORY)


@pytest.mark.unit
def test_min_active_weight_is_zero_point_three_five() -> None:
    assert MIN_ACTIVE_WEIGHT == 0.35


@pytest.mark.unit
def test_severity_multipliers_strictly_decreasing() -> None:
    assert SEVERITY_MULTIPLIERS["low"] == 0.9
    assert SEVERITY_MULTIPLIERS["medium"] == 0.7
    assert SEVERITY_MULTIPLIERS["high"] == 0.4
    assert SEVERITY_MULTIPLIERS["critical"] == 0.1
    ordered = [
        SEVERITY_MULTIPLIERS["low"],
        SEVERITY_MULTIPLIERS["medium"],
        SEVERITY_MULTIPLIERS["high"],
        SEVERITY_MULTIPLIERS["critical"],
    ]
    assert ordered == sorted(ordered, reverse=True)
