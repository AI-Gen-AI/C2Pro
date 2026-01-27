
from datetime import datetime, timedelta
from typing import Any
from src.coherence.rules_engine.context_rules import CoherenceRule, CoherenceRuleResult

class LeadTimeRiskRule(CoherenceRule):
    def check(self) -> CoherenceRuleResult:
        risks = []
        today = datetime.now()
        
        for item in self.project_context.bom_items:
            if item.required_on_site_date and item.lead_time_days:
                required_order_date = item.required_on_site_date - timedelta(days=item.lead_time_days)
                if required_order_date < today:
                    risks.append({
                        "material": item.item_name,
                        "needed_date": item.required_on_site_date.isoformat(),
                        "lead_time": item.lead_time_days,
                        "required_order_date": required_order_date.isoformat(),
                        "delay_days": (today - required_order_date).days
                    })
        
        is_violated = len(risks) > 0
        evidence = None
        
        if is_violated:
            evidence = {
                "risks": risks,
                "severity": "CRITICAL"
            }
            
        return CoherenceRuleResult(rule_id="R14", is_violated=is_violated, evidence=evidence)
