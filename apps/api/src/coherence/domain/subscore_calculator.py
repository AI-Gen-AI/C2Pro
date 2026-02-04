"""
Subscore calculator domain service.

Refers to Suite ID: TS-UD-COH-SCR-001.
"""

from typing import List, NamedTuple
from enum import Enum, auto

# --- Data Models and Enums ---

class CoherenceSeverity(Enum):
    """Defines the severity levels of a coherence alert."""
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()

class ScoreScope(Enum):
    """Enumerates the different areas or dimensions for subscoring."""
    SCOPE = auto()
    BUDGET = auto()
    QUALITY = auto()
    TECHNICAL = auto()
    LEGAL = auto()
    TIME = auto()

class CoherenceAlert(NamedTuple):
    """
    Represents a single coherence violation alert, used as input for scoring.
    """
    rule_id: str
    severity: CoherenceSeverity
    scope: ScoreScope

# --- Domain Service ---

class SubscoreCalculator:
    """
    A domain service to calculate a subscore based on coherence alerts.
    The score starts at 100 and is penalized based on the severity of alerts
    within a specific scope.
    """

    # Exposed for tests that inject temporary classes.
    CoherenceSeverity = CoherenceSeverity
    ScoreScope = ScoreScope
    CoherenceAlert = CoherenceAlert
    
    BASE_SCORE = 100.0
    MIN_SCORE = 0.0

    async def calculate(self, alerts: List[CoherenceAlert], scope: ScoreScope) -> float:
        """
        Calculates a subscore for a given scope based on a list of coherence alerts.

        Args:
            alerts: A list of all coherence alerts for the project.
            scope: The specific scope for which to calculate the subscore.

        Returns:
            The calculated subscore, as a float between 0.0 and 100.0.
        """
        penalty_by_name = {
            "LOW": 5,
            "MEDIUM": 10,
            "HIGH": 20,
            "CRITICAL": 30,
        }
        total_penalty = 0

        # Filter alerts that match the requested scope
        relevant_alerts = [
            alert
            for alert in alerts
            if getattr(alert.scope, "name", str(alert.scope)) == getattr(scope, "name", str(scope))
        ]

        # Calculate the cumulative penalty
        for alert in relevant_alerts:
            severity_name = getattr(alert.severity, "name", str(alert.severity)).upper()
            total_penalty += penalty_by_name.get(severity_name, 0)
            
        # Calculate the final score and ensure it doesn't go below the minimum
        final_score = self.BASE_SCORE - total_penalty
        
        return max(self.MIN_SCORE, final_score)
