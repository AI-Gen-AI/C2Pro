"""
I6 - Coherence Engine Service (Application)
Test Suite ID: TS-I6-COH-SVC-001
"""

from datetime import date
from typing import Any, Optional
from uuid import uuid4

import pytest
from pydantic import BaseModel, Field

try:
    from src.modules.coherence.domain.entities import CoherenceAlert, RuleInput
    from src.modules.coherence.application.ports import CoherenceEngineService
except ImportError:
    class CoherenceAlert(BaseModel):
        alert_id: str = Field(default_factory=lambda: str(uuid4()))
        type: str
        severity: str
        message: str
        evidence: dict[str, Any] = Field(default_factory=dict)
        triggered_by_rule: str
        doc_id: Optional[str] = None
        metadata: dict[str, Any] = Field(default_factory=dict)

    class RuleInput(BaseModel):
        doc_id: str = Field(default_factory=lambda: str(uuid4()))
        schedule_data: Optional[dict[str, Any]] = None
        actual_dates: Optional[dict[str, Any]] = None
        budget_data: Optional[dict[str, Any]] = None
        actual_costs: Optional[dict[str, Any]] = None
        scope_data: Optional[dict[str, Any]] = None
        procurement_items: Optional[dict[str, Any]] = None

    class CoherenceEngineService:
        def __init__(self, rules: list[Any], langsmith_client: Any = None):
            self.rules = rules
            self.langsmith_client = langsmith_client

        async def run_coherence_checks(self, rule_input: RuleInput) -> list[CoherenceAlert]:
            alerts: list[CoherenceAlert] = []
            for rule in self.rules:
                alert = rule.evaluate(rule_input)
                if alert:
                    alerts.append(alert)
            return alerts


class MockCoherenceRule:
    def __init__(self, name: str, will_trigger: bool = False, severity: str = "Medium"):
        self.name = name
        self.will_trigger = will_trigger
        self.severity = severity

    def evaluate(self, rule_input: RuleInput) -> Optional[CoherenceAlert]:
        if self.will_trigger:
            return CoherenceAlert(
                alert_id=str(uuid4()),
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
        doc_id=str(uuid4()),
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
        doc_id=str(uuid4()),
        schedule_data={"project_end": date(2024, 12, 31)},
        actual_dates={"project_end": date(2025, 1, 15)},
    )

    alerts = await engine.run_coherence_checks(rule_input)

    assert len(alerts) == 1
    assert alerts[0].metadata.get("requires_human_review") is True
    assert alerts[0].metadata.get("review_reason") == "Critical Coherence Conflict"
