import os
import sys

# Temporarily add the parent directory to sys.path to allow relative imports when run directly
# This is a common pattern for testing modules within a package structure
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(
    os.path.join(script_dir, "../../../../../")
)  # Go up from coherence to modules, src, api, apps, then c2pro
sys.path.insert(0, project_root)

from apps.api.src.modules.coherence.config import (
    DECAY_FACTOR,
    RULE_WEIGHT_OVERRIDES,
    SEVERITY_WEIGHTS,
)
from apps.api.src.modules.coherence.models import Alert, Evidence


class ScoringService:
    """
    Service responsible for computing a coherence score based on a list of alerts.
    Implements an advanced model with rule-specific weights and diminishing returns.
    """

    def compute_score(self, alerts: list[Alert]) -> float:
        """
        Calculates the coherence score based on a more nuanced model.

        1.  Checks for rule-specific weight overrides.
        2.  Applies a decay factor for multiple alerts of the same severity (for non-overridden rules).
        3.  Clamps the final score between 0 and 100.
        """
        base_score = 100.0
        total_deduction = 0.0

        severity_counts: Dict[str, int] = {}

        for alert in alerts:
            # 1. Check for a rule-specific override first
            if alert.rule_id in RULE_WEIGHT_OVERRIDES:
                total_deduction += RULE_WEIGHT_OVERRIDES[alert.rule_id]
                continue  # Overridden rules do not contribute to diminishing returns count

            # 2. If no override, use severity weight with diminishing returns
            base_penalty = SEVERITY_WEIGHTS.get(alert.severity, 0.0)

            if base_penalty == 0.0:
                continue

            severity = alert.severity
            count = severity_counts.get(severity, 0)

            decayed_penalty = base_penalty * (DECAY_FACTOR**count)

            total_deduction += decayed_penalty

            # Increment the count for this severity
            severity_counts[severity] = count + 1

        final_score = base_score - total_deduction

        # Clamp the score between 0 and 100 and round to 2 decimal places
        return max(0.0, min(100.0, round(final_score, 2)))


if __name__ == "__main__":
    # Example usage and testing for the new ScoringService

    # Create dummy alerts for testing
    high_alert_1 = Alert(
        rule_id="HIGH-001",
        severity="high",
        message="",
        evidence=Evidence(source_clause_id="c1", claim="", quote=""),
    )
    high_alert_2 = Alert(
        rule_id="HIGH-002",
        severity="high",
        message="",
        evidence=Evidence(source_clause_id="c2", claim="", quote=""),
    )

    # This rule has a weight override in config.py (20.0)
    budget_overrun_alert = Alert(
        rule_id="project-budget-overrun-10",
        severity="high",
        message="",
        evidence=Evidence(source_clause_id="c3", claim="", quote=""),
    )

    medium_alert = Alert(
        rule_id="MED-001",
        severity="medium",
        message="",
        evidence=Evidence(source_clause_id="c4", claim="", quote=""),
    )

    service = ScoringService()

    print("--- Testing Advanced Scoring ---")

    # Test case 1: Single high alert (no decay)
    score1 = service.compute_score([high_alert_1])
    print(f"Score with one 'high' alert: {score1}")
    # Expected: 100 - 15 = 85.0

    # Test case 2: Two high alerts (diminishing returns)
    score2 = service.compute_score([high_alert_1, high_alert_2])
    deduction2 = 15.0 * (DECAY_FACTOR**0) + 15.0 * (DECAY_FACTOR**1)
    print(f"Score with two 'high' alerts: {score2} (Expected: {100 - deduction2})")

    # Test case 3: Rule-specific weight override
    score3 = service.compute_score([budget_overrun_alert])
    print(f"Score with overridden rule 'project-budget-overrun-10': {score3}")
    # Expected: 100 - 20.0 = 80.0

    # Test case 4: Mixed alerts with override and diminishing returns
    alerts = [high_alert_1, high_alert_2, budget_overrun_alert, medium_alert]
    # 'high_alert_1' is a 'high' alert (count 1)
    # 'high_alert_2' is a 'high' alert (count 2)
    # 'budget_overrun_alert' is also 'high', but uses its override (20.0), so it doesn't affect the 'high' count for decay
    # Let's refine the logic to count based on the *final* weight source for fairness.
    # For now, let's assume the count is by severity string.
    # high_alert_1 penalty = 15 * (0.85**0) = 15
    # high_alert_2 penalty = 15 * (0.85**1) = 12.75
    # budget_overrun_alert penalty = 20.0 (override)
    # medium_alert penalty = 5 * (0.85**0) = 5
    # Total deduction = 15 + 12.75 + 20 + 5 = 52.75
    score4 = service.compute_score(alerts)
    print(f"Score with mixed alerts: {score4} (Expected: {100 - 52.75})")
