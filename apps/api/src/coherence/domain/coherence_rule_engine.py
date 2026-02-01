
import abc
from uuid import UUID
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum
from datetime import date, timedelta

# --- Enums and Data Models ---

class CoherenceStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"

class CoherenceSeverity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class CoherenceResult(BaseModel):
    rule_id: str
    status: CoherenceStatus
    severity: CoherenceSeverity
    message: str
    affected_entities: List[UUID] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

# --- Input Data Structures ---

class WBSItem(BaseModel):
    id: UUID
    name: str
    level: int

class Activity(BaseModel):
    id: UUID
    wbs_id: UUID
    date: date # Added for R2

class BudgetLine(BaseModel):
    id: UUID
    wbs_id: UUID
    amount: float

class ScopeClause(BaseModel):
    id: UUID
    content: str
    wbs_ids: List[UUID] = Field(default_factory=list)

class BOMItem(BaseModel):
    id: UUID
    wbs_id: UUID
    budget_id: Optional[UUID] = None
    client_provided: bool = False

class BudgetVsActual(BaseModel):
    wbs_id: UUID
    budgeted_amount: float
    actual_amount: float

class BudgetTrend(BaseModel):
    wbs_id: UUID
    current_deviation_percent: float
    previous_deviation_percent: float
    
# New data models for RUL-003
class Contract(BaseModel):
    id: UUID
    start_date: date
    end_date: date

class Schedule(BaseModel):
    id: UUID
    contract_id: UUID
    date: date

class Milestone(BaseModel):
    id: UUID
    name: str
    date: date
    activity_ids: List[UUID]

class ProcurementOrder(BaseModel):
    id: UUID
    expected_delivery_date: date


class ProjectData(BaseModel):
    wbs_items: List[WBSItem] = Field(default_factory=list)
    activities: List[Activity] = Field(default_factory=list)
    budget_lines: List[BudgetLine] = Field(default_factory=list)
    scope_clauses: List[ScopeClause] = Field(default_factory=list)
    bom_items: List[BOMItem] = Field(default_factory=list)
    budget_vs_actual: List[BudgetVsActual] = Field(default_factory=list)
    budget_trends: List[BudgetTrend] = Field(default_factory=list)
    # New
    contracts: List[Contract] = Field(default_factory=list)
    schedules: List[Schedule] = Field(default_factory=list)
    milestones: List[Milestone] = Field(default_factory=list)
    procurement_orders: List[ProcurementOrder] = Field(default_factory=list)
    current_date: date = Field(default_factory=date.today)


# --- Rule Definition ---

class CoherenceRule(abc.ABC):
    """Abstract base class for a coherence rule."""
    @property
    @abc.abstractmethod
    def rule_id(self) -> str:
        pass

    @abc.abstractmethod
    def evaluate(self, data: ProjectData) -> List[CoherenceResult]:
        pass

# --- Concrete Rule Implementations ---

class RuleR11_WBSEmptyLevel4(CoherenceRule):
    rule_id = "R11"
    def evaluate(self, data: ProjectData) -> List[CoherenceResult]:
        activity_map = {act.wbs_id for act in data.activities}
        violating_wbs = [wbs.id for wbs in data.wbs_items if wbs.level == 4 and wbs.id not in activity_map]
        if violating_wbs:
            return [CoherenceResult(rule_id=self.rule_id, status=CoherenceStatus.FAIL, severity=CoherenceSeverity.MEDIUM, message="WBS items at level 4 must have at least one activity.", affected_entities=violating_wbs)]
        return []

class RuleR12_WBSNoBudget(CoherenceRule):
    rule_id = "R12"
    def evaluate(self, data: ProjectData) -> List[CoherenceResult]:
        results, budget_map = [], {line.wbs_id: line for line in data.budget_lines}
        fail, warn = [wbs.id for wbs in data.wbs_items if wbs.id not in budget_map], [wbs.id for wbs in data.wbs_items if wbs.id in budget_map and budget_map[wbs.id].amount == 0]
        if fail: results.append(CoherenceResult(rule_id=self.rule_id, status=CoherenceStatus.FAIL, severity=CoherenceSeverity.HIGH, message="WBS items are missing a budget line.", affected_entities=fail))
        if warn: results.append(CoherenceResult(rule_id=self.rule_id, status=CoherenceStatus.WARN, severity=CoherenceSeverity.MEDIUM, message="WBS items have a budget of zero.", affected_entities=warn))
        return results

class RuleR13_ScopeClauseNoWBS(CoherenceRule):
    rule_id = "R13"
    def evaluate(self, data: ProjectData) -> List[CoherenceResult]:
        if not data.scope_clauses: return []
        uncovered = [c.id for c in data.scope_clauses if not c.wbs_ids]
        coverage = ((len(data.scope_clauses) - len(uncovered)) / len(data.scope_clauses)) * 100
        if uncovered: return [CoherenceResult(rule_id=self.rule_id, status=CoherenceStatus.FAIL, severity=CoherenceSeverity.HIGH, message=f"Scope clauses coverage: {coverage:.1f}%", affected_entities=uncovered, metadata={"coverage_percentage": coverage})]
        return []

class RuleR6_BudgetActualDeviation(CoherenceRule):
    rule_id = "R6"
    DEVIATION_THRESHOLD = 0.10
    def evaluate(self, data: ProjectData) -> List[CoherenceResult]:
        results = []
        for ba in data.budget_vs_actual:
            if ba.budgeted_amount == 0: continue
            deviation = abs(ba.actual_amount - ba.budgeted_amount) / ba.budgeted_amount
            if deviation > self.DEVIATION_THRESHOLD:
                severity, message = (CoherenceSeverity.HIGH, f"Budget exceeded by {deviation:.1%}.") if ba.actual_amount > ba.budgeted_amount else (CoherenceSeverity.MEDIUM, f"Budget under-spent by {deviation:.1%}.")
                results.append(CoherenceResult(rule_id=self.rule_id, status=CoherenceStatus.FAIL, severity=severity, message=message, affected_entities=[ba.wbs_id]))
        return results

class RuleR15_BOMBudget(CoherenceRule):
    rule_id = "R15"
    def evaluate(self, data: ProjectData) -> List[CoherenceResult]:
        violating = [bom.id for bom in data.bom_items if not bom.client_provided and bom.budget_id is None]
        if violating: return [CoherenceResult(rule_id=self.rule_id, status=CoherenceStatus.FAIL, severity=CoherenceSeverity.HIGH, message="BOM items must have an associated budget.", affected_entities=violating)]
        return []

class RuleR16_BudgetVarianceTrend(CoherenceRule):
    rule_id = "R16"
    DEVIATION_ALERT_THRESHOLD = 0.11
    def evaluate(self, data: ProjectData) -> List[CoherenceResult]:
        violating = [t.wbs_id for t in data.budget_trends if t.current_deviation_percent >= self.DEVIATION_ALERT_THRESHOLD and t.current_deviation_percent > t.previous_deviation_percent]
        if violating: return [CoherenceResult(rule_id=self.rule_id, status=CoherenceStatus.FAIL, severity=CoherenceSeverity.HIGH, message="Budget variance shows a worsening trend.", affected_entities=violating)]
        return []

# New Rules for RUL-003
class RuleR1_ScheduleContractDateMismatch(CoherenceRule):
    rule_id = "R1"
    def evaluate(self, data: ProjectData) -> List[CoherenceResult]:
        results, contract_map = [], {c.id: c for c in data.contracts}
        for s in data.schedules:
            if s.contract_id in contract_map:
                contract_date = contract_map[s.contract_id].start_date
                if s.date != contract_date:
                    delta = (s.date - contract_date).days
                    status, severity = (CoherenceStatus.FAIL, CoherenceSeverity.HIGH) if delta > 0 else (CoherenceStatus.WARN, CoherenceSeverity.MEDIUM)
                    results.append(CoherenceResult(rule_id=self.rule_id, status=status, severity=severity, message=f"Schedule date deviates from contract by {delta} days.", affected_entities=[s.id], metadata={"delta_days": delta}))
        return results

class RuleR2_MilestoneConsistency(CoherenceRule):
    rule_id = "R2"
    def evaluate(self, data: ProjectData) -> List[CoherenceResult]:
        violations = {}
        activity_map = {a.id: a for a in data.activities}
        for m in data.milestones:
            if not m.activity_ids: violations[m.id] = "Milestone has no linked activities."
            else:
                for act_id in m.activity_ids:
                    if act_id in activity_map and activity_map[act_id].date != m.date: violations[m.id] = "Milestone date does not match activity date."; break
        if violations: return [CoherenceResult(rule_id=self.rule_id, status=CoherenceStatus.FAIL, severity=CoherenceSeverity.MEDIUM, message="Milestone consistency failed.", affected_entities=list(violations.keys()))]
        return []

class RuleR5_ActivityExceedsContract(CoherenceRule):
    rule_id = "R5"
    def evaluate(self, data: ProjectData) -> List[CoherenceResult]:
        if not data.contracts: return []
        contract = data.contracts[0] # Assuming one main contract for simplicity
        violating = [a.id for a in data.activities if not (contract.start_date <= a.date <= contract.end_date)]
        if violating: return [CoherenceResult(rule_id=self.rule_id, status=CoherenceStatus.FAIL, severity=CoherenceSeverity.HIGH, message="Activities fall outside contract dates.", affected_entities=violating)]
        return []

class RuleR14_OrderDatePassed(CoherenceRule):
    rule_id = "R14"
    TIGHT_DEADLINE_DAYS = 7
    def evaluate(self, data: ProjectData) -> List[CoherenceResult]:
        results = []
        for order in data.procurement_orders:
            delta = (order.expected_delivery_date - data.current_date).days
            if delta < 0: results.append(CoherenceResult(rule_id=self.rule_id, status=CoherenceStatus.FAIL, severity=CoherenceSeverity.HIGH, message="Expected delivery date has passed.", affected_entities=[order.id]))
            elif delta <= self.TIGHT_DEADLINE_DAYS: results.append(CoherenceResult(rule_id=self.rule_id, status=CoherenceStatus.WARN, severity=CoherenceSeverity.MEDIUM, message="Expected delivery date is approaching.", affected_entities=[order.id]))
        return results


# --- Rule Engine ---

class CoherenceRuleEngine:
    def __init__(self):
        self.rules: List[CoherenceRule] = [
            RuleR11_WBSEmptyLevel4(), RuleR12_WBSNoBudget(), RuleR13_ScopeClauseNoWBS(),
            RuleR6_BudgetActualDeviation(), RuleR15_BOMBudget(), RuleR16_BudgetVarianceTrend(),
            RuleR1_ScheduleContractDateMismatch(), RuleR2_MilestoneConsistency(),
            RuleR5_ActivityExceedsContract(), RuleR14_OrderDatePassed(),
        ]

    async def evaluate(self, data: ProjectData) -> List[CoherenceResult]:
        all_results = []
        for rule in self.rules: all_results.extend(rule.evaluate(data))
        return all_results
