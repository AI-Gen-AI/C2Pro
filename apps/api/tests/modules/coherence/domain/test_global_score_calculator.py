"""
Global score calculator tests.

Refers to Suite ID: TS-UD-COH-SCR-002.
"""

from __future__ import annotations

import pytest

from src.coherence.domain.global_score_calculator import (
    GlobalScoreCalculator,
    WeightConfig,
)
from src.coherence.domain.subscore_calculator import ScoreScope


class TestGlobalScoreCalculator:
    """Refers to Suite ID: TS-UD-COH-SCR-002"""

    def test_001_global_score_formula_verification(self) -> None:
        subscores = {
            ScoreScope.BUDGET: 80.0,
            ScoreScope.TIME: 90.0,
            ScoreScope.SCOPE: 70.0,
        }
        weights = WeightConfig.model_validate(
            {
                "weights": {
                    ScoreScope.BUDGET: 0.30,
                    ScoreScope.TIME: 0.30,
                    ScoreScope.SCOPE: 0.40,
                }
            }
        )

        score = GlobalScoreCalculator().calculate_global(subscores=subscores, weights=weights)

        assert score == pytest.approx(79.0)

    def test_002_global_score_default_weights(self) -> None:
        subscores = {
            ScoreScope.BUDGET: 80.0,
            ScoreScope.TIME: 90.0,
            ScoreScope.SCOPE: 70.0,
            ScoreScope.QUALITY: 100.0,
            ScoreScope.TECHNICAL: 100.0,
            ScoreScope.LEGAL: 100.0,
        }

        score = GlobalScoreCalculator().calculate_global(subscores=subscores)

        assert score == pytest.approx(90.0)

    def test_003_global_score_all_100_equals_100(self) -> None:
        subscores = {scope: 100.0 for scope in ScoreScope}

        score = GlobalScoreCalculator().calculate_global(subscores=subscores)

        assert score == 100.0

    def test_004_global_score_all_0_equals_0(self) -> None:
        subscores = {scope: 0.0 for scope in ScoreScope}

        score = GlobalScoreCalculator().calculate_global(subscores=subscores)

        assert score == 0.0

    def test_005_global_score_mixed_subscores(self) -> None:
        subscores = {
            ScoreScope.BUDGET: 85.0,
            ScoreScope.TIME: 70.0,
            ScoreScope.SCOPE: 95.0,
            ScoreScope.QUALITY: 65.0,
            ScoreScope.TECHNICAL: 80.0,
            ScoreScope.LEGAL: 90.0,
        }

        score = GlobalScoreCalculator().calculate_global(subscores=subscores)

        assert score == pytest.approx((85 + 70 + 95 + 65 + 80 + 90) / 6)

    def test_006_global_score_range_0_to_100(self) -> None:
        high = GlobalScoreCalculator().calculate_global(
            subscores={ScoreScope.BUDGET: 150.0},
            weights=WeightConfig.model_validate({"weights": {ScoreScope.BUDGET: 1.0}}),
        )
        low = GlobalScoreCalculator().calculate_global(
            subscores={ScoreScope.BUDGET: -10.0},
            weights=WeightConfig.model_validate({"weights": {ScoreScope.BUDGET: 1.0}}),
        )

        assert high == 100.0
        assert low == 0.0

    def test_007_weights_sum_validation(self) -> None:
        subscores = {ScoreScope.BUDGET: 80.0, ScoreScope.TIME: 90.0}
        invalid_weights = WeightConfig.model_validate(
            {"weights": {ScoreScope.BUDGET: 0.8, ScoreScope.TIME: 0.8}}
        )

        with pytest.raises(ValueError, match="Weights do not sum to 1.0"):
            GlobalScoreCalculator().calculate_global(
                subscores=subscores,
                weights=invalid_weights,
                normalize_weights=False,
            )

    def test_008_weights_normalization_auto(self) -> None:
        subscores = {ScoreScope.BUDGET: 80.0, ScoreScope.TIME: 100.0}
        weights = WeightConfig.model_validate(
            {"weights": {ScoreScope.BUDGET: 50.0, ScoreScope.TIME: 50.0}}
        )

        score = GlobalScoreCalculator().calculate_global(
            subscores=subscores,
            weights=weights,
            normalize_weights=True,
        )

        assert score == pytest.approx(90.0)

    def test_009_weights_custom_budget_30(self) -> None:
        subscores = {
            ScoreScope.BUDGET: 80.0,
            ScoreScope.TIME: 90.0,
            ScoreScope.SCOPE: 70.0,
            ScoreScope.QUALITY: 100.0,
            ScoreScope.TECHNICAL: 100.0,
            ScoreScope.LEGAL: 100.0,
        }
        weights = WeightConfig.model_validate({"weights": {ScoreScope.BUDGET: 0.30}})

        score = GlobalScoreCalculator().calculate_global(subscores=subscores, weights=weights)

        other = (1.0 - 0.30) / 5
        expected = (80.0 * 0.30) + (90.0 * other) + (70.0 * other) + (100.0 * other) + (100.0 * other) + (100.0 * other)
        assert score == pytest.approx(expected)

    def test_010_weights_custom_time_25(self) -> None:
        subscores = {
            ScoreScope.BUDGET: 80.0,
            ScoreScope.TIME: 90.0,
            ScoreScope.SCOPE: 70.0,
            ScoreScope.QUALITY: 100.0,
            ScoreScope.TECHNICAL: 100.0,
            ScoreScope.LEGAL: 100.0,
        }
        weights = WeightConfig.model_validate({"weights": {ScoreScope.TIME: 0.25}})

        score = GlobalScoreCalculator().calculate_global(subscores=subscores, weights=weights)

        other = (1.0 - 0.25) / 5
        expected = (90.0 * 0.25) + (80.0 * other) + (70.0 * other) + (100.0 * other) + (100.0 * other) + (100.0 * other)
        assert score == pytest.approx(expected)

    def test_011_weights_per_project_type(self) -> None:
        subscores = {
            ScoreScope.BUDGET: 80.0,
            ScoreScope.TIME: 90.0,
            ScoreScope.SCOPE: 70.0,
        }
        residential = WeightConfig.model_validate(
            {"weights": {ScoreScope.BUDGET: 0.50, ScoreScope.TIME: 0.20, ScoreScope.SCOPE: 0.30}}
        )
        commercial = WeightConfig.model_validate(
            {"weights": {ScoreScope.BUDGET: 0.20, ScoreScope.TIME: 0.50, ScoreScope.SCOPE: 0.30}}
        )

        calculator = GlobalScoreCalculator()
        residential_score = calculator.calculate_global(subscores=subscores, weights=residential)
        commercial_score = calculator.calculate_global(subscores=subscores, weights=commercial)

        assert residential_score == pytest.approx(79.0)
        assert commercial_score == pytest.approx(82.0)

    def test_012_weights_history_tracking(self) -> None:
        subscores = {ScoreScope.BUDGET: 80.0, ScoreScope.TIME: 90.0}
        weights_a = WeightConfig.model_validate(
            {"weights": {ScoreScope.BUDGET: 0.50, ScoreScope.TIME: 0.50}}
        )
        weights_b = WeightConfig.model_validate(
            {"weights": {ScoreScope.BUDGET: 0.25, ScoreScope.TIME: 0.75}}
        )

        calculator = GlobalScoreCalculator()
        calculator.calculate_global(subscores=subscores, weights=weights_a, track_history=True)
        calculator.calculate_global(subscores=subscores, weights=weights_b, track_history=True)

        history = calculator.get_weight_history()
        assert len(history) == 2
        assert history[0].weights[ScoreScope.BUDGET] == pytest.approx(0.50)
        assert history[1].weights[ScoreScope.TIME] == pytest.approx(0.75)

    def test_013_empty_subscores_returns_100(self) -> None:
        """Empty subscores dictionary returns perfect score."""
        subscores = {}
        score = GlobalScoreCalculator().calculate_global(subscores=subscores)
        assert score == 100.0

    def test_014_weights_config_with_no_matching_scopes_uses_equal(self) -> None:
        """When weights don't match any subscores, use equal weighting."""
        subscores = {ScoreScope.BUDGET: 80.0, ScoreScope.TIME: 90.0}
        weights = WeightConfig.model_validate(
            {"weights": {ScoreScope.SCOPE: 0.50, ScoreScope.LEGAL: 0.50}}
        )

        score = GlobalScoreCalculator().calculate_global(subscores=subscores, weights=weights)
        # Should use equal weights (0.5 each) since no relevant weights
        assert score == pytest.approx(85.0)

    def test_015_weights_exact_sum_to_1_with_all_scopes(self) -> None:
        """When weights exactly sum to 1.0 and cover all scopes, use as-is."""
        subscores = {ScoreScope.BUDGET: 80.0, ScoreScope.TIME: 90.0}
        weights = WeightConfig.model_validate(
            {"weights": {ScoreScope.BUDGET: 0.40, ScoreScope.TIME: 0.60}}
        )

        score = GlobalScoreCalculator().calculate_global(subscores=subscores, weights=weights)
        expected = (80.0 * 0.40) + (90.0 * 0.60)
        assert score == pytest.approx(expected)

    def test_016_weights_zero_sum_uses_equal(self) -> None:
        """When all weights sum to zero, use equal weighting."""
        subscores = {ScoreScope.BUDGET: 80.0, ScoreScope.TIME: 90.0}
        weights = WeightConfig.model_validate(
            {"weights": {ScoreScope.BUDGET: 0.0, ScoreScope.TIME: 0.0}}
        )

        score = GlobalScoreCalculator().calculate_global(subscores=subscores, weights=weights)
        # Should use equal weights (0.5 each)
        assert score == pytest.approx(85.0)

    @pytest.mark.asyncio
    async def test_017_async_calculate_wrapper(self) -> None:
        """Async calculate() wrapper returns same result as calculate_global()."""
        subscores = {ScoreScope.BUDGET: 80.0, ScoreScope.TIME: 90.0}
        weights = WeightConfig.model_validate(
            {"weights": {ScoreScope.BUDGET: 0.50, ScoreScope.TIME: 0.50}}
        )

        calculator = GlobalScoreCalculator()
        sync_score = calculator.calculate_global(subscores=subscores, weights=weights)
        async_score = await calculator.calculate(subscores=subscores, weights=weights)

        assert async_score == sync_score
        assert async_score == pytest.approx(85.0)

    def test_018_weights_partial_sum_less_than_1_with_all_scopes_covered(self) -> None:
        """When weights sum < 1.0 but cover all scopes in subscores, use as-is."""
        subscores = {ScoreScope.BUDGET: 80.0, ScoreScope.TIME: 90.0}
        weights = WeightConfig.model_validate(
            {"weights": {ScoreScope.BUDGET: 0.30, ScoreScope.TIME: 0.40}}  # Sum = 0.70
        )

        score = GlobalScoreCalculator().calculate_global(
            subscores=subscores, weights=weights, normalize_weights=True
        )
        # Should return as-is since all subscores are covered
        expected = (80.0 * 0.30) + (90.0 * 0.40)
        assert score == pytest.approx(expected)

    def test_019_normalization_disabled_with_exact_1_0_sum(self) -> None:
        """When normalize_weights=False and weights sum exactly to 1.0, use as-is."""
        subscores = {ScoreScope.BUDGET: 80.0, ScoreScope.TIME: 90.0}
        weights = WeightConfig.model_validate(
            {"weights": {ScoreScope.BUDGET: 0.40, ScoreScope.TIME: 0.60}}
        )

        score = GlobalScoreCalculator().calculate_global(
            subscores=subscores, weights=weights, normalize_weights=False
        )
        expected = (80.0 * 0.40) + (90.0 * 0.60)
        assert score == pytest.approx(expected)
