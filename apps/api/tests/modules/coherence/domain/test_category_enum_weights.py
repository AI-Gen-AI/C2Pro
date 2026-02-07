"""
Category Enum & Weights (TDD - RED Phase)

Refers to Suite ID: TS-UD-COH-CAT-001.
"""

from __future__ import annotations

import pytest

from src.coherence.domain.category_weights import (
    CoherenceCategory,
    DEFAULT_CATEGORY_WEIGHTS,
    get_default_category_weights,
    validate_category_weights,
)


class TestCategoryEnumWeights:
    """Refers to Suite ID: TS-UD-COH-CAT-001."""

    def test_category_enum_has_six_categories(self):
        assert len(CoherenceCategory) == 6

    def test_category_enum_contains_required_codes(self):
        assert {category.value for category in CoherenceCategory} == {
            "SCOPE",
            "BUDGET",
            "QUALITY",
            "TECHNICAL",
            "LEGAL",
            "TIME",
        }

    def test_default_weights_include_all_categories(self):
        assert set(DEFAULT_CATEGORY_WEIGHTS.keys()) == set(CoherenceCategory)

    def test_default_weights_sum_to_one(self):
        total = sum(DEFAULT_CATEGORY_WEIGHTS.values())
        assert total == pytest.approx(1.0)

    def test_default_scope_weight_is_twenty_percent(self):
        assert DEFAULT_CATEGORY_WEIGHTS[CoherenceCategory.SCOPE] == pytest.approx(0.20)

    def test_default_budget_weight_is_twenty_percent(self):
        assert DEFAULT_CATEGORY_WEIGHTS[CoherenceCategory.BUDGET] == pytest.approx(0.20)

    def test_default_quality_weight_is_fifteen_percent(self):
        assert DEFAULT_CATEGORY_WEIGHTS[CoherenceCategory.QUALITY] == pytest.approx(0.15)

    def test_default_technical_weight_is_fifteen_percent(self):
        assert DEFAULT_CATEGORY_WEIGHTS[CoherenceCategory.TECHNICAL] == pytest.approx(0.15)

    def test_default_legal_weight_is_fifteen_percent(self):
        assert DEFAULT_CATEGORY_WEIGHTS[CoherenceCategory.LEGAL] == pytest.approx(0.15)

    def test_default_time_weight_is_fifteen_percent(self):
        assert DEFAULT_CATEGORY_WEIGHTS[CoherenceCategory.TIME] == pytest.approx(0.15)

    def test_get_default_category_weights_returns_copy(self):
        first = get_default_category_weights()
        second = get_default_category_weights()
        first[CoherenceCategory.SCOPE] = 0.99
        assert second[CoherenceCategory.SCOPE] == pytest.approx(0.20)

    def test_validate_category_weights_rejects_invalid_sum(self):
        with pytest.raises(ValueError, match="sum to 1.0"):
            validate_category_weights(
                {
                    CoherenceCategory.SCOPE: 0.30,
                    CoherenceCategory.BUDGET: 0.30,
                    CoherenceCategory.QUALITY: 0.15,
                    CoherenceCategory.TECHNICAL: 0.15,
                    CoherenceCategory.LEGAL: 0.15,
                    CoherenceCategory.TIME: 0.15,
                }
            )

    def test_validate_category_weights_rejects_missing_categories(self):
        with pytest.raises(ValueError, match="Missing category weights"):
            validate_category_weights(
                {
                    CoherenceCategory.SCOPE: 0.50,
                    CoherenceCategory.BUDGET: 0.50,
                    # Missing: QUALITY, TECHNICAL, LEGAL, TIME
                }
            )

    def test_validate_category_weights_accepts_valid_weights(self):
        # Should not raise any exception
        validate_category_weights(
            {
                CoherenceCategory.SCOPE: 0.20,
                CoherenceCategory.BUDGET: 0.20,
                CoherenceCategory.QUALITY: 0.15,
                CoherenceCategory.TECHNICAL: 0.15,
                CoherenceCategory.LEGAL: 0.15,
                CoherenceCategory.TIME: 0.15,
            }
        )
