
import pytest
from typing import Dict
from enum import Enum, auto

# This import will fail as the modules do not exist yet.
from apps.api.src.coherence.domain.global_score_calculator import (
    GlobalScoreCalculator,
    ScoreScope,
    WeightConfig,
    Subscores,
)

# --- Test Fixture ---
@pytest.fixture
def calculator() -> GlobalScoreCalculator:
    """Provides an instance of the GlobalScoreCalculator."""
    # This is a pure domain service with no dependencies.
    return GlobalScoreCalculator()

# --- Test Data ---
@pytest.fixture
def all_100_subscores(calculator) -> Subscores:
    return {scope: 100.0 for scope in calculator.ScoreScope}

@pytest.fixture
def all_0_subscores(calculator) -> Subscores:
    return {scope: 0.0 for scope in calculator.ScoreScope}

@pytest.fixture
def mixed_subscores(calculator) -> Subscores:
    return {
        calculator.ScoreScope.BUDGET: 80.0,
        calculator.ScoreScope.TIME: 90.0,
        calculator.ScoreScope.SCOPE: 70.0,
        calculator.ScoreScope.QUALITY: 100.0,
        calculator.ScoreScope.TECHNICAL: 100.0,
        calculator.ScoreScope.LEGAL: 100.0,
    }

# --- Test Cases ---
@pytest.mark.asyncio
class TestGlobalScoreCalculator:
    """Refers to Suite ID: TS-UD-COH-SCR-002"""

    async def test_001_global_score_formula_verification(self, calculator, mixed_subscores):
        """Verify the weighted average formula."""
        # Manually define simple weights that sum to 1.0
        weights = WeightConfig(weights={
            calculator.ScoreScope.BUDGET: 0.3,
            calculator.ScoreScope.TIME: 0.3,
            calculator.ScoreScope.SCOPE: 0.4,
        })
        # Only provide subscores for the weighted scopes
        subscores = {
            calculator.ScoreScope.BUDGET: 80.0,
            calculator.ScoreScope.TIME: 90.0,
            calculator.ScoreScope.SCOPE: 70.0,
        }
        
        expected_score = (80.0 * 0.3) + (90.0 * 0.3) + (70.0 * 0.4) # 24 + 27 + 28 = 79.0
        
        score = await calculator.calculate(subscores=subscores, weights=weights)
        assert score == pytest.approx(79.0)

    async def test_002_global_score_default_weights(self, calculator, mixed_subscores):
        """Test that default weights are applied if none are provided."""
        # Assuming default weights are equal for all 6 scopes (1/6 each)
        score = await calculator.calculate(subscores=mixed_subscores)
        
        expected_score = (80 + 90 + 70 + 100 + 100 + 100) / 6  # 540 / 6 = 90.0
        assert score == pytest.approx(90.0)

    async def test_003_global_score_all_100_equals_100(self, calculator, all_100_subscores):
        score = await calculator.calculate(subscores=all_100_subscores)
        assert score == 100.0

    async def test_004_global_score_all_0_equals_0(self, calculator, all_0_subscores):
        score = await calculator.calculate(subscores=all_0_subscores)
        assert score == 0.0

    async def test_005_global_score_mixed_subscores(self, calculator, mixed_subscores):
        """Test with a standard set of mixed scores and default weights."""
        score = await calculator.calculate(subscores=mixed_subscores)
        expected_score = (80 + 90 + 70 + 100 + 100 + 100) / 6
        assert score == pytest.approx(expected_score)
        
    async def test_006_global_score_range_0_to_100(self, calculator):
        """Test that scores outside the 0-100 range are clamped."""
        # This test is implicitly covered by others, but good to be explicit
        # A subscore > 100 should not result in a global score > 100
        subscores_high = {calculator.ScoreScope.BUDGET: 150.0}
        weights_high = WeightConfig(weights={calculator.ScoreScope.BUDGET: 1.0})
        score_high = await calculator.calculate(subscores=subscores_high, weights=weights_high)
        assert score_high == 100.0

        # A subscore < 0 should not result in a global score < 0
        subscores_low = {calculator.ScoreScope.BUDGET: -50.0}
        weights_low = WeightConfig(weights={calculator.ScoreScope.BUDGET: 1.0})
        score_low = await calculator.calculate(subscores=subscores_low, weights=weights_low)
        assert score_low == 0.0

    async def test_007_weights_sum_validation(self, calculator, mixed_subscores):
        """Test that providing weights that don't sum to 1.0 raises an error if normalization is off."""
        weights = WeightConfig(weights={
            calculator.ScoreScope.BUDGET: 0.5,
            calculator.ScoreScope.TIME: 0.6, # Sums to 1.1
        })
        with pytest.raises(ValueError, match="Weights do not sum to 1.0"):
            await calculator.calculate(subscores=mixed_subscores, weights=weights, normalize_weights=False)

    async def test_008_weights_normalization_auto(self, calculator, mixed_subscores):
        """Test that weights are automatically normalized if they don't sum to 1.0."""
        # These weights (50, 50) sum to 100, not 1. They should be normalized to 0.5, 0.5.
        weights = WeightConfig(weights={
            calculator.ScoreScope.BUDGET: 50.0,
            calculator.ScoreScope.TIME: 50.0,
        })
        subscores = {
            calculator.ScoreScope.BUDGET: 80.0,
            calculator.ScoreScope.TIME: 100.0,
        }
        score = await calculator.calculate(subscores=subscores, weights=weights, normalize_weights=True)
        
        # Expected score with normalized weights (0.5, 0.5)
        expected_score = (80.0 * 0.5) + (100.0 * 0.5) # 40 + 50 = 90.0
        assert score == pytest.approx(90.0)

    async def test_009_010_weights_custom(self, calculator, mixed_subscores):
        """Test with custom weights for budget and time."""
        weights = WeightConfig(weights={
            calculator.ScoreScope.BUDGET: 0.3, # 30%
            calculator.ScoreScope.TIME: 0.25,  # 25%
            # The rest will be distributed among remaining scopes
        })
        score = await calculator.calculate(subscores=mixed_subscores, weights=weights, normalize_weights=True)
        
        # Manually calculate expected score with normalization
        total_weight = 0.3 + 0.25 + (4 * (1-0.55)/4) # 1.0
        norm_budget = 0.3
        norm_time = 0.25
        norm_other = (1.0 - 0.55) / 4 # 0.1125 each for SCOPE, QUALITY, TECHNICAL, LEGAL
        
        expected = (
            (80.0 * norm_budget) +
            (90.0 * norm_time) +
            (70.0 * norm_other) +
            (100.0 * norm_other) +
            (100.0 * norm_other) +
            (100.0 * norm_other)
        )
        assert score == pytest.approx(expected)

    async def test_011_weights_per_project_type(self, calculator, mixed_subscores):
        """Simulate passing different weight configs for different project types."""
        # The calculator is stateless; the caller is responsible for providing the correct weights.
        
        # "Residential" project weights (heavy on budget)
        weights_residential = WeightConfig(weights={
            calculator.ScoreScope.BUDGET: 0.5,
            calculator.ScoreScope.TIME: 0.2,
            calculator.ScoreScope.SCOPE: 0.3,
        })
        score_residential = await calculator.calculate(subscores=mixed_subscores, weights=weights_residential)
        expected_res = (80 * 0.5) + (90 * 0.2) + (70 * 0.3) # 40 + 18 + 21 = 79.0
        assert score_residential == pytest.approx(expected_res)

        # "Commercial" project weights (heavy on time)
        weights_commercial = WeightConfig(weights={
            calculator.ScoreScope.BUDGET: 0.2,
            calculator.ScoreScope.TIME: 0.5,
            calculator.ScoreScope.SCOPE: 0.3,
        })
        score_commercial = await calculator.calculate(subscores=mixed_subscores, weights=weights_commercial)
        expected_com = (80 * 0.2) + (90 * 0.5) + (70 * 0.3) # 16 + 45 + 21 = 82.0
        assert score_commercial == pytest.approx(expected_com)

    # test_012 (history tracking) is a persistence concern and not tested at the domain level.
