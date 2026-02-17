"""
I6 - Coherence Engine Service (Application)
Test Suite ID: TS-I6-COH-SVC-001
"""

from datetime import date
from typing import Optional
from uuid import uuid4

import pytest

from src.modules.coherence.domain.entities import CoherenceAlert, RuleInput
from src.modules.coherence.application.ports import CoherenceEngineService


class MockCoherenceRule:
    def __init__(self, name: str, will_trigger: bool = False, severity: str = "Medium"):
        self.name = name
        self.will_trigger = will_trigger
        self.severity = severity

    def evaluate(self, rule_input: RuleInput) -> Optional[CoherenceAlert]:
        if self.will_trigger:
            return CoherenceAlert(
                alert_id=uuid4(),
                type=f"{self.name} Alert",
                severity=self.severity,
                message=f"Alert from {self.name}",
                evidence={"rule_triggered": True},
                triggered_by_rule=self.name,
                doc_id=rule_input.doc_id,
            )
        return None


@pytest.mark.asyncio
async def test_i6_coherence_engine_returns_neutral_when_data_missing() -> None:
    """Refers to I6.2: engine should return neutral output when required data is missing."""
    rules = [
        MockCoherenceRule(name="ScheduleRule", will_trigger=True, severity="Critical"),
        MockCoherenceRule(name="BudgetRule", will_trigger=False),
    ]

    engine = CoherenceEngineService(rules=rules)
    rule_input = RuleInput(
        doc_id=uuid4(),
        schedule_data=None,
        actual_dates=None,
        budget_data={"allocated": 100000},
        actual_costs={"actual_spend": 90000},
        scope_data=None,
        procurement_items=None,
    )

    alerts = await engine.run_coherence_checks(rule_input)

    assert isinstance(alerts, list)
    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_i6_critical_coherence_conflicts_flagged_for_review() -> None:
    """Refers to I6.6: critical alerts must include explicit human-review metadata."""
    rules = [MockCoherenceRule(name="CriticalRule", will_trigger=True, severity="Critical")]

    engine = CoherenceEngineService(rules=rules)
    rule_input = RuleInput(
        doc_id=uuid4(),
        schedule_data={"project_end": date(2024, 12, 31)},
        actual_dates={"project_end": date(2025, 1, 15)},
    )

    alerts = await engine.run_coherence_checks(rule_input)

    assert len(alerts) == 1
    assert alerts[0].metadata.get("requires_human_review") is True
    assert alerts[0].metadata.get("review_reason") == "Critical Coherence Conflict"


@pytest.mark.asyncio
async def test_i6_high_coherence_conflicts_flagged_for_review() -> None:
    """Refers to I6.6: high severity alerts must include explicit human-review metadata."""
    rules = [MockCoherenceRule(name="BudgetRule", will_trigger=True, severity="High")]

    engine = CoherenceEngineService(rules=rules)
    rule_input = RuleInput(
        doc_id=uuid4(),
        budget_data={"allocated": 100000},
        actual_costs={"actual_spend": 120000},
    )

    alerts = await engine.run_coherence_checks(rule_input)

    assert len(alerts) == 1
    assert alerts[0].metadata.get("requires_human_review") is True
    assert alerts[0].metadata.get("review_reason") == "High Coherence Conflict"


@pytest.mark.asyncio
async def test_i6_medium_coherence_conflicts_not_flagged_for_review() -> None:
    """Refers to I6.6: medium severity alerts should not be forced into mandatory human review."""
    rules = [MockCoherenceRule(name="ScopeRule", will_trigger=True, severity="Medium")]

    engine = CoherenceEngineService(rules=rules)
    rule_input = RuleInput(
        doc_id=uuid4(),
        scope_data={"required_items": ["Material A"]},
        procurement_items={"items_procured": []},
    )

    alerts = await engine.run_coherence_checks(rule_input)

    assert len(alerts) == 1
    assert alerts[0].metadata.get("requires_human_review") is None
    assert alerts[0].metadata.get("review_reason") is None
