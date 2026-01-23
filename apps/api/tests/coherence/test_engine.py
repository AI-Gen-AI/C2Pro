# apps/api/tests/coherence/test_engine.py

import pytest
from apps.api.src.modules.coherence.engine import CoherenceEngine
from apps.api.src.modules.coherence.models import (
    Alert,
    Clause,
    CoherenceResult,
    Evidence,
    ProjectContext,
)
from apps.api.src.modules.coherence.rules import Rule


@pytest.fixture
def mock_rules():
    """
    Fixture providing a list of Rule objects for the implemented deterministic rules.
    Using the actual rule IDs allows the engine to pick up the correct evaluators from the registry.
    """
    return [
        Rule(
            id="project-budget-overrun-10",  # Real Rule ID for R1
            description="Budget overrun rule",
            inputs=["budget.current", "budget.planned"],
            detection_logic="project.budget.current > project.budget.planned * 1.1",
            severity="high",
            evidence_fields=["budget.current", "budget.planned"],
        ),
        Rule(
            id="project-schedule-delayed",  # Real Rule ID for R5
            description="Schedule delayed rule",
            inputs=["schedule.status"],
            detection_logic="project.schedule.status == 'delayed'",
            severity="medium",
            evidence_fields=["schedule.status"],
        ),
        # Removed other mock rules to focus tests on R1 and R5
    ]


@pytest.fixture
def coherence_engine(mock_rules):
    """Fixture for a CoherenceEngine instance with mock rules."""
    return CoherenceEngine(rules=mock_rules)


# --- Helper functions to create Clause objects for tests ---
def create_budget_clause(id_suffix, current, planned):
    return Clause(
        id=f"clause-b-{id_suffix}",
        text=f"Budget: current {current}, planned {planned}.",
        data={"current": current, "planned": planned, "type": "budget_summary"},
    )


def create_schedule_clause(id_suffix, status):
    return Clause(
        id=f"clause-s-{id_suffix}",
        text=f"Schedule status: {status}.",
        data={"status": status, "type": "schedule_summary"},
    )


def test_evaluate_returns_coherence_result(coherence_engine):
    """Test that evaluate returns a CoherenceResult object."""
    project_context = ProjectContext(id="test-project", clauses=[])
    result = coherence_engine.evaluate(project_context)
    assert isinstance(result, CoherenceResult)
    assert isinstance(result.alerts, list)
    assert isinstance(result.score, float)


def test_evaluate_with_no_alerts(coherence_engine):
    """Test evaluate with a project that triggers no alerts."""
    project_context = ProjectContext(
        id="project-clean-001",
        clauses=[
            create_budget_clause("001", 95000, 100000),  # Not overrun
            create_schedule_clause("001", "on-track"),  # Not delayed
        ],
    )
    result = coherence_engine.evaluate(project_context)
    assert len(result.alerts) == 0
    assert result.score == 100.0


def test_evaluate_with_schedule_delay_alert(coherence_engine):
    """Test the ScheduleDelayEvaluator (R5) is triggered correctly."""
    project_context = ProjectContext(
        id="project-delayed-002",
        clauses=[
            create_schedule_clause("002", "delayed"),  # Triggers this
        ],
    )
    result = coherence_engine.evaluate(project_context)
    assert len(result.alerts) == 1
    assert result.alerts[0].rule_id == "project-schedule-delayed"
    assert result.alerts[0].severity == "medium"
    assert isinstance(result.alerts[0].evidence, Evidence)
    assert result.alerts[0].evidence.source_clause_id == "clause-s-002"
    assert "delayed" in result.alerts[0].evidence.claim.lower()


def test_evaluate_with_budget_overrun_alert(coherence_engine):
    """Test the BudgetOverrunEvaluator (R1) is triggered correctly."""
    project_context = ProjectContext(
        id="project-overrun-003",
        clauses=[
            create_budget_clause("003", 250000, 200000),  # Triggers this
        ],
    )
    result = coherence_engine.evaluate(project_context)
    assert len(result.alerts) == 1
    assert result.alerts[0].rule_id == "project-budget-overrun-10"
    assert result.alerts[0].severity == "high"
    assert isinstance(result.alerts[0].evidence, Evidence)
    assert result.alerts[0].evidence.source_clause_id == "clause-b-003"
    assert "overrun" in result.alerts[0].evidence.claim.lower()


def test_evaluate_with_multiple_alerts(coherence_engine):
    """Test evaluate with a project that triggers both R1 and R5."""
    project_context = ProjectContext(
        id="project-multi-alert-005",
        clauses=[
            create_budget_clause("005", 250000, 200000),  # Triggers budget overrun (high)
            create_schedule_clause("005", "delayed"),  # Triggers schedule delayed (medium)
        ],
    )
    result = coherence_engine.evaluate(project_context)
    assert len(result.alerts) == 2
    assert any(alert.rule_id == "project-budget-overrun-10" for alert in result.alerts)
    assert any(alert.rule_id == "project-schedule-delayed" for alert in result.alerts)

    # Note: Score calculation will be tested more thoroughly in test_scoring.py
    # This just checks that multiple alerts affect the score.
    assert result.score < 100.0


def test_evaluate_alert_structure(coherence_engine):
    """Test that the alerts returned have the correct structure, including Evidence."""
    project_context = ProjectContext(
        id="project-overrun-structure", clauses=[create_budget_clause("structure", 250000, 200000)]
    )
    result = coherence_engine.evaluate(project_context)
    alert = result.alerts[0]
    assert isinstance(alert, Alert)
    assert isinstance(alert.evidence, Evidence)
    assert alert.evidence.source_clause_id == "clause-b-structure"
    assert "budget" in alert.evidence.claim.lower()
    assert "budget: current 250000, planned 200000." in alert.evidence.quote.lower()
