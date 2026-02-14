"""
I6 Coherence Domain Rules
Test Suite ID: TS-I6-COH-RULES-001
"""

from datetime import date, timedelta
from typing import Optional, Protocol

from src.modules.coherence.domain.entities import CoherenceAlert, RuleInput


class CoherenceRuleProtocol(Protocol):
    """Protocol for coherence rule implementations."""

    name: str

    def evaluate(self, rule_input: RuleInput) -> Optional[CoherenceAlert]:
        ...


class ScheduleMismatchRule:
    """Triggers when actual schedule end meaningfully exceeds planned end."""

    name = "ScheduleMismatchRule"

    def evaluate(self, rule_input: RuleInput) -> Optional[CoherenceAlert]:
        if not rule_input.schedule_data or not rule_input.actual_dates:
            return None

        project_end = rule_input.schedule_data.get("project_end")
        actual_end = rule_input.actual_dates.get("project_end")
        if not isinstance(project_end, date) or not isinstance(actual_end, date):
            return None

        if actual_end > project_end + timedelta(days=7):
            delay_days = (actual_end - project_end).days
            return CoherenceAlert(
                type="Schedule Mismatch",
                severity="Critical",
                message=f"Project delayed by {delay_days} days against contract schedule.",
                evidence={
                    "scheduled_end": project_end.isoformat(),
                    "actual_end": actual_end.isoformat(),
                    "delay_days": delay_days,
                },
                triggered_by_rule=self.name,
                doc_id=rule_input.doc_id,
            )
        return None


class BudgetMismatchRule:
    """Triggers when actual spend exceeds allocated budget by >10%."""

    name = "BudgetMismatchRule"

    def evaluate(self, rule_input: RuleInput) -> Optional[CoherenceAlert]:
        if not rule_input.budget_data or not rule_input.actual_costs:
            return None

        allocated = rule_input.budget_data.get("allocated")
        actual_spend = rule_input.actual_costs.get("actual_spend")
        if not isinstance(allocated, (int, float)) or not isinstance(actual_spend, (int, float)):
            return None

        if allocated > 0 and actual_spend > allocated * 1.1:
            overage = actual_spend - allocated
            return CoherenceAlert(
                type="Budget Mismatch",
                severity="High",
                message=f"Budget exceeded by {overage}.",
                evidence={"allocated": allocated, "actual_spend": actual_spend, "overage": overage},
                triggered_by_rule=self.name,
                doc_id=rule_input.doc_id,
            )
        return None


class ScopeProcurementMismatchRule:
    """Triggers when required scoped items are missing from procurement."""

    name = "ScopeProcurementMismatchRule"

    def evaluate(self, rule_input: RuleInput) -> Optional[CoherenceAlert]:
        if not rule_input.scope_data or not rule_input.procurement_items:
            return None

        required_items = set(rule_input.scope_data.get("required_items", []))
        procured_items = set(rule_input.procurement_items.get("items_procured", []))

        if not required_items:
            return None

        missing = sorted(required_items - procured_items)
        if missing:
            return CoherenceAlert(
                type="Scope-Procurement Mismatch",
                severity="Medium",
                message=f"Missing procurement for scope items: {', '.join(missing)}.",
                evidence={
                    "required_items": sorted(required_items),
                    "procured_items": sorted(procured_items),
                    "missing_items": missing,
                },
                triggered_by_rule=self.name,
                doc_id=rule_input.doc_id,
            )
        return None

