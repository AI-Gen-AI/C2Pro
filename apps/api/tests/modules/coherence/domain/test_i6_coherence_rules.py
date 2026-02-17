"""
I6 - Coherence Rules (Domain)
Test Suite ID: TS-I6-COH-RULES-001
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest

from src.modules.coherence.domain.entities import RuleInput
from src.modules.coherence.domain.rules import (
    ScheduleMismatchRule,
    BudgetMismatchRule,
    ScopeProcurementMismatchRule,
)


def test_i6_schedule_mismatch_rule_triggers_on_overlap_violation() -> None:
    """Refers to I6.1: schedule mismatch rule should trigger on delayed actual end date."""
    doc_id = uuid4()
    rule_input = RuleInput(
        doc_id=doc_id,
        schedule_data={"project_end": date(2024, 12, 31)},
        actual_dates={"project_end": date(2025, 1, 15)},
    )

    rule = ScheduleMismatchRule()
    alert = rule.evaluate(rule_input)

    assert alert is not None
    assert alert.type == "Schedule Mismatch"
    assert alert.severity == "Critical"
    assert alert.triggered_by_rule == "ScheduleMismatchRule"
    assert alert.doc_id == doc_id
    assert alert.evidence.get("delay_days") == 15


def test_i6_budget_mismatch_rule_triggers_on_exceedance() -> None:
    """Refers to I6.1: budget mismatch rule should trigger above tolerance."""
    doc_id = uuid4()
    rule_input = RuleInput(
        doc_id=doc_id,
        budget_data={"allocated": 100000},
        actual_costs={"actual_spend": 115000},
    )

    rule = BudgetMismatchRule()
    alert = rule.evaluate(rule_input)

    assert alert is not None
    assert alert.type == "Budget Mismatch"
    assert alert.severity in {"High", "Critical"}
    assert alert.triggered_by_rule == "BudgetMismatchRule"
    assert alert.doc_id == doc_id
    assert alert.evidence.get("allocated") == 100000
    assert alert.evidence.get("actual_spend") == 115000
    assert alert.evidence.get("overage") == 15000


def test_i6_scope_procurement_mismatch_rule_triggers() -> None:
    """Refers to I6.1: scope-procurement mismatch should trigger when required items are missing."""
    doc_id = uuid4()
    rule_input = RuleInput(
        doc_id=doc_id,
        scope_data={"required_items": ["Material A", "Service B", "Material C"]},
        procurement_items={"items_procured": ["Material A", "Service B"]},
    )

    rule = ScopeProcurementMismatchRule()
    alert = rule.evaluate(rule_input)

    assert alert is not None
    assert alert.type == "Scope-Procurement Mismatch"
    assert "Material C" in alert.message
    assert alert.triggered_by_rule == "ScopeProcurementMismatchRule"
    assert alert.doc_id == doc_id
    assert "Material C" in (alert.evidence.get("missing_items") or [])
