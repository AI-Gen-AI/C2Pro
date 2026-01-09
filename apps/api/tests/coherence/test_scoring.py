# apps/api/tests/coherence/test_scoring.py
import pytest
from apps.api.src.modules.coherence.config import (
    DECAY_FACTOR,
    RULE_WEIGHT_OVERRIDES,
    SEVERITY_WEIGHTS,
)
from apps.api.src.modules.coherence.models import Alert, Evidence
from apps.api.src.modules.coherence.scoring import ScoringService


@pytest.fixture
def scoring_service():
    """Fixture for a ScoringService instance."""
    return ScoringService()


# --- Reusable Alert Fixtures ---
@pytest.fixture
def high_alert_1():
    return Alert(
        rule_id="HIGH-001",
        severity="high",
        message="",
        evidence=Evidence(source_clause_id="c1", claim="", quote=""),
    )


@pytest.fixture
def high_alert_2():
    return Alert(
        rule_id="HIGH-002",
        severity="high",
        message="",
        evidence=Evidence(source_clause_id="c2", claim="", quote=""),
    )


@pytest.fixture
def medium_alert_1():
    return Alert(
        rule_id="MED-001",
        severity="medium",
        message="",
        evidence=Evidence(source_clause_id="c3", claim="", quote=""),
    )


@pytest.fixture
def medium_alert_2():
    return Alert(
        rule_id="MED-002",
        severity="medium",
        message="",
        evidence=Evidence(source_clause_id="c4", claim="", quote=""),
    )


@pytest.fixture
def budget_overrun_alert():
    """Alert for a rule with a specific weight override."""
    return Alert(
        rule_id="project-budget-overrun-10",
        severity="high",
        message="",
        evidence=Evidence(source_clause_id="c5", claim="", quote=""),
    )


# --- Test Cases ---


def test_compute_score_no_alerts(scoring_service):
    """Test score is 100 when no alerts are present."""
    assert scoring_service.compute_score([]) == 100.0


def test_compute_score_single_alert(scoring_service, high_alert_1, medium_alert_1):
    """Test score with single alerts of different severities (no decay)."""
    assert scoring_service.compute_score([high_alert_1]) == 100 - SEVERITY_WEIGHTS["high"]
    assert scoring_service.compute_score([medium_alert_1]) == 100 - SEVERITY_WEIGHTS["medium"]


def test_compute_score_rule_override(scoring_service, budget_overrun_alert, high_alert_1):
    """Test that rule-specific weight override is applied correctly."""
    # The 'budget_overrun_alert' has a 'high' severity (15) but the rule_id has an override (20)
    score = scoring_service.compute_score([budget_overrun_alert])
    assert score == 100 - RULE_WEIGHT_OVERRIDES["project-budget-overrun-10"]

    # Ensure the override doesn't affect other 'high' severity alerts
    score_mixed = scoring_service.compute_score([budget_overrun_alert, high_alert_1])
    expected_deduction = (
        RULE_WEIGHT_OVERRIDES["project-budget-overrun-10"] + SEVERITY_WEIGHTS["high"]
    )
    assert score_mixed == 100 - expected_deduction


def test_compute_score_diminishing_returns(scoring_service, high_alert_1, high_alert_2):
    """Test diminishing returns for multiple alerts of the same severity."""
    alerts = [high_alert_1, high_alert_2]

    penalty1 = SEVERITY_WEIGHTS["high"] * (DECAY_FACTOR**0)
    penalty2 = SEVERITY_WEIGHTS["high"] * (DECAY_FACTOR**1)
    expected_score = 100 - (penalty1 + penalty2)

    assert scoring_service.compute_score(alerts) == pytest.approx(expected_score)


def test_compute_score_mixed_with_diminishing_and_overrides(
    scoring_service, high_alert_1, high_alert_2, medium_alert_1, budget_overrun_alert
):
    """Test a complex scenario with mixed alerts, diminishing returns, and overrides."""
    alerts = [high_alert_1, budget_overrun_alert, high_alert_2, medium_alert_1]

    # Calculation:
    # 1. budget_overrun_alert: Override weight of 20.0
    override_penalty = RULE_WEIGHT_OVERRIDES["project-budget-overrun-10"]

    # 2. high_alert_1: First 'high' alert. Penalty = 15.0
    high_penalty1 = SEVERITY_WEIGHTS["high"] * (DECAY_FACTOR**0)

    # 3. high_alert_2: Second 'high' alert. Penalty = 15.0 * 0.85
    high_penalty2 = SEVERITY_WEIGHTS["high"] * (DECAY_FACTOR**1)

    # 4. medium_alert_1: First 'medium' alert. Penalty = 5.0
    medium_penalty1 = SEVERITY_WEIGHTS["medium"] * (DECAY_FACTOR**0)

    total_deduction = override_penalty + high_penalty1 + high_penalty2 + medium_penalty1
    expected_score = 100 - total_deduction

    assert scoring_service.compute_score(alerts) == pytest.approx(expected_score)


def test_compute_score_clamped_at_zero(scoring_service):
    """Test that the score is clamped at 0 if deductions exceed 100."""
    # Create enough alerts to guarantee score goes below zero
    critical_alerts = [
        Alert(
            rule_id=f"CRIT-{i}",
            severity="critical",
            message="",
            evidence=Evidence(source_clause_id=f"c{i}", claim="", quote=""),
        )
        for i in range(5)
    ]
    assert scoring_service.compute_score(critical_alerts) == 0.0


def test_compute_score_determinism(
    scoring_service, high_alert_1, medium_alert_1, budget_overrun_alert
):
    """Test that the score is deterministic regardless of alert order."""
    alerts1 = [high_alert_1, budget_overrun_alert, medium_alert_1]
    alerts2 = [medium_alert_1, high_alert_1, budget_overrun_alert]

    score1 = scoring_service.compute_score(alerts1)
    score2 = scoring_service.compute_score(alerts2)

    assert score1 == score2
