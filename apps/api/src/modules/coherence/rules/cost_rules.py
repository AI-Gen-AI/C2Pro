
from typing import Any
from src.modules.coherence.rules_engine.context_rules import CoherenceRule, CoherenceRuleResult

class CostVarianceRule(CoherenceRule):
    def check(self) -> CoherenceRuleResult:
        total_budget = sum(item.amount for item in self.project_context.budget_items)
        contract_amount = self.project_context.contract.total_amount
        
        if contract_amount == 0:
            return CoherenceRuleResult(rule_id="R2", is_violated=False)

        variance = (total_budget - contract_amount) / contract_amount
        is_violated = False
        evidence = None
        severity = None

        if variance > 0.10:
            is_violated = True
            severity = "CRITICAL"
        elif variance > 0.05:
            is_violated = True
            severity = "HIGH"
        
        if is_violated:
            evidence = {
                "total_budget": total_budget,
                "contract_amount": contract_amount,
                "variance_percentage": variance * 100,
                "severity": severity
            }

        return CoherenceRuleResult(rule_id="R2", is_violated=is_violated, evidence=evidence)

class UnbudgetedItemsRule(CoherenceRule):
    def check(self) -> CoherenceRuleResult:
        unbudgeted_items = [item for item in self.project_context.bom_items if not item.budget_item_id]
        
        is_violated = len(unbudgeted_items) > 0
        evidence = None
        
        if is_violated:
            evidence = {
                "unbudgeted_items": [item.item_name for item in unbudgeted_items],
                "severity": "HIGH"
            }

        return CoherenceRuleResult(rule_id="R15", is_violated=is_violated, evidence=evidence)
