"""
I6 Coherence Application Service
Test Suite ID: TS-I6-COH-SVC-001
"""

from typing import Any, Optional, Protocol

from src.modules.coherence.domain.entities import CoherenceAlert, RuleInput
from src.modules.coherence.domain.rules import CoherenceRuleProtocol


class LangSmithClientProtocol(Protocol):
    def start_span(self, name: str, input: Any = None, run_type: str = "tool", **kwargs) -> Any: ...
    def end_span(self, span: dict[str, Any], outputs: Any = None) -> None: ...


class CoherenceEngineService:
    """Runs configured coherence rules and emits normalized alerts."""

    def __init__(
        self,
        rules: list[CoherenceRuleProtocol],
        langsmith_client: Optional[LangSmithClientProtocol] = None,
    ):
        self.rules = rules
        self.langsmith_client = langsmith_client

    def _has_required_data(self, rule_name: str, rule_input: RuleInput) -> bool:
        """Neutral behavior gate: skip rule evaluation when required inputs are missing."""
        name = rule_name.lower()
        if "schedule" in name:
            return bool(rule_input.schedule_data and rule_input.actual_dates)
        if "budget" in name:
            return bool(rule_input.budget_data and rule_input.actual_costs)
        if "scope" in name or "procurement" in name:
            return bool(rule_input.scope_data and rule_input.procurement_items)
        return True

    async def run_coherence_checks(self, rule_input: RuleInput) -> list[CoherenceAlert]:
        alerts: list[CoherenceAlert] = []

        for rule in self.rules:
            rule_name = getattr(rule, "name", rule.__class__.__name__)
            if not self._has_required_data(rule_name, rule_input):
                continue

            alert = rule.evaluate(rule_input)
            if not alert:
                continue

            if alert.severity in ("Critical", "High"):
                alert.metadata["requires_human_review"] = True
                alert.metadata["review_reason"] = f"{alert.severity} Coherence Conflict"
            alerts.append(alert)

        return alerts

