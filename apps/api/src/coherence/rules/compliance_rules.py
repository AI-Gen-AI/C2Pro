
from typing import Any
from src.coherence.rules_engine.context_rules import CoherenceRule, CoherenceRuleResult

class PermittingRule(CoherenceRule):
    def check(self) -> CoherenceRuleResult:
        permit_clauses = [clause for clause in self.project_context.clauses if "licencia" in clause.text.lower() or "permiso" in clause.text.lower()]
        
        has_permit_milestone = any("licencia" in item.name.lower() or "permiso" in item.name.lower() for item in self.project_context.schedule_items)
        
        is_violated = len(permit_clauses) > 0 and not has_permit_milestone
        evidence = None
        
        if is_violated:
            evidence = {
                "permit_clauses": [clause.id for clause in permit_clauses],
                "severity": "HIGH"
            }
            
        return CoherenceRuleResult(rule_id="R6", is_violated=is_violated, evidence=evidence)

class CashFlowRule(CoherenceRule):
    def check(self) -> CoherenceRuleResult:
        # This is a placeholder as the prompt mentions it's optional and depends on data availability.
        # For now, it will always pass.
        return CoherenceRuleResult(rule_id="R19", is_violated=False)
