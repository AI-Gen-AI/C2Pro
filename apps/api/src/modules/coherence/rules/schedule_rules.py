
from typing import Any
from src.modules.coherence.rules_engine.context_rules import CoherenceRule, CoherenceRuleResult

class DependencyViolationRule(CoherenceRule):
    def check(self) -> CoherenceRuleResult:
        violations = []
        schedule_items_map = {item.id: item for item in self.project_context.schedule_items}
        
        for item in self.project_context.schedule_items:
            if item.predecessor_id and item.predecessor_id in schedule_items_map:
                predecessor = schedule_items_map[item.predecessor_id]
                if item.start_date < predecessor.end_date:
                    violations.append({
                        "successor_id": item.id,
                        "successor_name": item.name,
                        "successor_start_date": item.start_date.isoformat(),
                        "predecessor_id": predecessor.id,
                        "predecessor_name": predecessor.name,
                        "predecessor_end_date": predecessor.end_date.isoformat(),
                    })
        
        is_violated = len(violations) > 0
        evidence = None
        
        if is_violated:
            evidence = {
                "violations": violations,
                "severity": "CRITICAL"
            }
            
        return CoherenceRuleResult(rule_id="R12", is_violated=is_violated, evidence=evidence)

class OrphanTasksRule(CoherenceRule):
    def check(self) -> CoherenceRuleResult:
        orphan_tasks = []
        wbs_leaf_items = [item for item in self.project_context.wbs_items if not any(i.parent_code == item.code for i in self.project_context.wbs_items)]

        for item in wbs_leaf_items:
            # This assumes that stakeholders are linked to WBS items.
            # I will assume there is a `stakeholders` field in the WBS item.
            if not hasattr(item, 'stakeholders') or not any(s.role == 'Responsible' for s in item.stakeholders):
                orphan_tasks.append(item.name)
        
        is_violated = len(orphan_tasks) > 0
        evidence = None
        
        if is_violated:
            evidence = {
                "orphan_tasks": orphan_tasks,
                "severity": "MEDIUM"
            }
            
        return CoherenceRuleResult(rule_id="R20", is_violated=is_violated, evidence=evidence)
