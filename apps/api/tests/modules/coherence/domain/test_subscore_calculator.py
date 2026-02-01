
import pytest
from typing import List, NamedTuple
from enum import Enum, auto

# This import will fail as the modules do not exist yet.
from apps.api.src.coherence.domain.subscore_calculator import (
    SubscoreCalculator,
    CoherenceAlert,
    CoherenceSeverity,
    ScoreScope,
)

# --- Temporary definitions for test development ---
class TempCoherenceSeverity(Enum):
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()

class TempScoreScope(Enum):
    SCOPE = auto()
    BUDGET = auto()
    QUALITY = auto()
    TECHNICAL = auto()
    LEGAL = auto()
    TIME = auto()

class TempCoherenceAlert(NamedTuple):
    rule_id: str
    severity: TempCoherenceSeverity
    scope: TempScoreScope


# --- Test Fixture ---
@pytest.fixture
def calculator() -> SubscoreCalculator:
    """Provides an instance of the SubscoreCalculator."""
    # This is a pure domain service with no dependencies.
    service = SubscoreCalculator()
    # Temporarily attach the temp classes for testing
    service.CoherenceSeverity = TempCoherenceSeverity
    service.ScoreScope = TempScoreScope
    service.CoherenceAlert = TempCoherenceAlert
    return service

# --- Test Cases ---
@pytest.mark.asyncio
class TestSubscoreCalculator:
    """Refers to Suite ID: TS-UD-COH-SCR-001"""

    async def test_001_subscore_no_alerts_100_percent(self, calculator):
        score = await calculator.calculate(alerts=[], scope=calculator.ScoreScope.BUDGET)
        assert score == 100.0

    async def test_002_subscore_one_alert_penalized(self, calculator):
        alerts = [
            calculator.CoherenceAlert("R1", calculator.CoherenceSeverity.MEDIUM, calculator.ScoreScope.BUDGET)
        ]
        score = await calculator.calculate(alerts=alerts, scope=calculator.ScoreScope.BUDGET)
        assert score == 90.0 # 100 - 10

    async def test_003_subscore_multiple_alerts_cumulative(self, calculator):
        alerts = [
            calculator.CoherenceAlert("R1", calculator.CoherenceSeverity.MEDIUM, calculator.ScoreScope.BUDGET),
            calculator.CoherenceAlert("R2", calculator.CoherenceSeverity.HIGH, calculator.ScoreScope.BUDGET),
        ]
        score = await calculator.calculate(alerts=alerts, scope=calculator.ScoreScope.BUDGET)
        assert score == 70.0 # 100 - 10 - 20

    @pytest.mark.parametrize("severity, expected_penalty", [
        (TempCoherenceSeverity.LOW, 5),
        (TempCoherenceSeverity.MEDIUM, 10),
        (TempCoherenceSeverity.HIGH, 20),
        (TempCoherenceSeverity.CRITICAL, 30),
    ])
    async def test_004_to_007_subscore_severity_penalties(self, calculator, severity, expected_penalty):
        alerts = [calculator.CoherenceAlert("R1", severity, calculator.ScoreScope.BUDGET)]
        score = await calculator.calculate(alerts=alerts, scope=calculator.ScoreScope.BUDGET)
        assert score == 100.0 - expected_penalty

    async def test_008_to_013_subscore_scope_calculation(self, calculator):
        """
        Tests that only alerts for the specified scope are included in the calculation.
        """
        alerts = [
            calculator.CoherenceAlert("R-BUDGET", calculator.CoherenceSeverity.HIGH, calculator.ScoreScope.BUDGET), # -20
            calculator.CoherenceAlert("R-TIME", calculator.CoherenceSeverity.MEDIUM, calculator.ScoreScope.TIME),   # -10
            calculator.CoherenceAlert("R-SCOPE", calculator.CoherenceSeverity.LOW, calculator.ScoreScope.SCOPE),    # -5
        ]
        
        # Calculate for BUDGET scope
        budget_score = await calculator.calculate(alerts=alerts, scope=calculator.ScoreScope.BUDGET)
        assert budget_score == 80.0 # 100 - 20
        
        # Calculate for TIME scope
        time_score = await calculator.calculate(alerts=alerts, scope=calculator.ScoreScope.TIME)
        assert time_score == 90.0 # 100 - 10
        
        # Calculate for SCOPE scope
        scope_score = await calculator.calculate(alerts=alerts, scope=calculator.ScoreScope.SCOPE)
        assert scope_score == 95.0 # 100 - 5
        
        # Calculate for a scope with no alerts
        quality_score = await calculator.calculate(alerts=alerts, scope=calculator.ScoreScope.QUALITY)
        assert quality_score == 100.0

    async def test_014_subscore_floor_at_zero(self, calculator):
        alerts = [
            calculator.CoherenceAlert("R1", calculator.CoherenceSeverity.CRITICAL, calculator.ScoreScope.BUDGET), # -30
            calculator.CoherenceAlert("R2", calculator.CoherenceSeverity.CRITICAL, calculator.ScoreScope.BUDGET), # -30
            calculator.CoherenceAlert("R3", calculator.CoherenceSeverity.CRITICAL, calculator.ScoreScope.BUDGET), # -30
            calculator.CoherenceAlert("R4", calculator.CoherenceSeverity.CRITICAL, calculator.ScoreScope.BUDGET), # -30
        ]
        score = await calculator.calculate(alerts=alerts, scope=calculator.ScoreScope.BUDGET)
        assert score == 0.0
