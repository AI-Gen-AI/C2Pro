"""
I6 - Coherence Rules (Domain)
Test Suite ID: TS-I6-COH-RULES-001
"""

from datetime import date
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

try:
    from src.coherence.domain.entities import CoherenceAlert, RuleInput
    from src.coherence.domain.rules import (
        BudgetMismatchRule,
        ScheduleMismatchRule,
        ScopeProcurementMismatchRule,
    )
except ImportError:
    class CoherenceAlert(BaseModel):
        alert_id: str = Field(default_factory=lambda: str(uuid4()))
        type: str
        severity: str
        message: str
        evidence: dict[str, Any] = Field(default_factory=dict)
        triggered_by_rule: str
        doc_id: str | None = None

    class RuleInput(BaseModel):
        doc_id: str = Field(default_factory=lambda: str(uuid4()))
        schedule_data: dict[str, Any] | None = None
        actual_dates: dict[str, Any] | None = None
        budget_data: dict[str, Any] | None = None
        actual_costs: dict[str, Any] | None = None
        scope_data: dict[str, Any] | None = None
        procurement_items: dict[str, Any] | None = None

    class ScheduleMismatchRule:
        def evaluate(self, rule_input: RuleInput) -> CoherenceAlert | None:
            return None

    class BudgetMismatchRule:
        def evaluate(self, rule_input: RuleInput) -> CoherenceAlert | None:
            return None

    class ScopeProcurementMismatchRule:
        def evaluate(self, rule_input: RuleInput) -> CoherenceAlert | None:
            return None


def test_i6_schedule_mismatch_rule_triggers_on_overlap_violation() -> None:
    """Refers to I6.1: schedule mismatch rule should trigger on delayed actual end date."""
    rule_input = RuleInput(
        doc_id=str(uuid4()),
        schedule_data={"project_end": date(2024, 12, 31)},
        actual_dates={"project_end": date(2025, 1, 15)},
    )

    rule = ScheduleMismatchRule()
    alert = rule.evaluate(rule_input)

    assert alert is not None
    assert alert.type == "Schedule Mismatch"
    assert alert.severity == "Critical"


def test_i6_budget_mismatch_rule_triggers_on_exceedance() -> None:
    """Refers to I6.1: budget mismatch rule should trigger above tolerance."""
    rule_input = RuleInput(
        doc_id=str(uuid4()),
        budget_data={"allocated": 100000},
        actual_costs={"actual_spend": 115000},
    )

    rule = BudgetMismatchRule()
    alert = rule.evaluate(rule_input)

    assert alert is not None
    assert alert.type == "Budget Mismatch"
    assert alert.severity in {"High", "Critical"}


def test_i6_scope_procurement_mismatch_rule_triggers() -> None:
    """Refers to I6.1: scope-procurement mismatch should trigger when required items are missing."""
    rule_input = RuleInput(
        doc_id=str(uuid4()),
        scope_data={"required_items": ["Material A", "Service B", "Material C"]},
        procurement_items={"items_procured": ["Material A", "Service B"]},
    )

    rule = ScopeProcurementMismatchRule()
    alert = rule.evaluate(rule_input)

    assert alert is not None
    assert alert.type == "Scope-Procurement Mismatch"
    assert "Material C" in alert.message
