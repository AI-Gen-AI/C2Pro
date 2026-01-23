import unittest
from datetime import datetime, timedelta
from uuid import uuid4
from abc import ABC, abstractmethod

# Mocking the necessary Pydantic models and the CoherenceRule class
# In a real scenario, these would be imported from the application's source code
from pydantic import BaseModel
from typing import List, Any

class CoherenceRuleResult(BaseModel):
    rule_id: str
    is_violated: bool
    evidence: dict[str, Any] | None = None

class CoherenceRule(ABC):
    def __init__(self, project_context: Any):
        self.project_context = project_context

    @abstractmethod
    def check(self) -> CoherenceRuleResult:
        raise NotImplementedError

# Mocking the project context and its components
class MockBudgetItem(BaseModel):
    amount: float

class MockContract(BaseModel):
    total_amount: float

class MockBOMItem(BaseModel):
    item_name: str
    budget_item_id: Any | None
    required_on_site_date: datetime | None
    lead_time_days: int | None

class MockScheduleItem(BaseModel):
    id: Any
    name: str
    start_date: datetime
    end_date: datetime
    predecessor_id: Any | None

class MockStakeholder(BaseModel):
    role: str

class MockWBSItem(BaseModel):
    code: str
    name: str
    parent_code: str | None
    stakeholders: List[MockStakeholder] = []

class MockClause(BaseModel):
    id: Any
    text: str

class MockProjectContext(BaseModel):
    budget_items: List[MockBudgetItem] = []
    contract: MockContract | None = None
    bom_items: List[MockBOMItem] = []
    schedule_items: List[MockScheduleItem] = []
    wbs_items: List[MockWBSItem] = []
    clauses: List[MockClause] = []

# Importing the rules to be tested
from apps.api.src.modules.coherence.rules.cost_rules import CostVarianceRule, UnbudgetedItemsRule
from apps.api.src.modules.coherence.rules.schedule_rules import DependencyViolationRule, OrphanTasksRule
from apps.api.src.modules.coherence.rules.supply_chain_rules import LeadTimeRiskRule
from apps.api.src.modules.coherence.rules.compliance_rules import PermittingRule, CashFlowRule


class TestCoherenceRules(unittest.TestCase):
    def test_cost_variance_rule(self):
        # Test case 1: No violation
        context = MockProjectContext(
            budget_items=[MockBudgetItem(amount=100), MockBudgetItem(amount=50)],
            contract=MockContract(total_amount=150)
        )
        rule = CostVarianceRule(context)
        result = rule.check()
        self.assertFalse(result.is_violated)

        # Test case 2: HIGH violation
        context = MockProjectContext(
            budget_items=[MockBudgetItem(amount=100), MockBudgetItem(amount=60)],
            contract=MockContract(total_amount=150)
        )
        rule = CostVarianceRule(context)
        result = rule.check()
        self.assertTrue(result.is_violated)
        self.assertEqual(result.evidence["severity"], "HIGH")

        # Test case 3: CRITICAL violation
        context = MockProjectContext(
            budget_items=[MockBudgetItem(amount=100), MockBudgetItem(amount=70)],
            contract=MockContract(total_amount=150)
        )
        rule = CostVarianceRule(context)
        result = rule.check()
        self.assertTrue(result.is_violated)
        self.assertEqual(result.evidence["severity"], "CRITICAL")


    def test_unbudgeted_items_rule(self):
        # Test case 1: No violation
        context = MockProjectContext(
            bom_items=[MockBOMItem(item_name="item1", budget_item_id=uuid4())]
        )
        rule = UnbudgetedItemsRule(context)
        result = rule.check()
        self.assertFalse(result.is_violated)

        # Test case 2: Violation
        context = MockProjectContext(
            bom_items=[
                MockBOMItem(item_name="item1", budget_item_id=uuid4()),
                MockBOMItem(item_name="item2", budget_item_id=None)
            ]
        )
        rule = UnbudgetedItemsRule(context)
        result = rule.check()
        self.assertTrue(result.is_violated)
        self.assertIn("item2", result.evidence["unbudgeted_items"])


    def test_dependency_violation_rule(self):
        # Test case 1: No violation
        item1_id = uuid4()
        item2_id = uuid4()
        context = MockProjectContext(
            schedule_items=[
                MockScheduleItem(id=item1_id, name="task1", start_date=datetime(2024, 1, 1), end_date=datetime(2024, 1, 5), predecessor_id=None),
                MockScheduleItem(id=item2_id, name="task2", start_date=datetime(2024, 1, 6), end_date=datetime(2024, 1, 10), predecessor_id=item1_id)
            ]
        )
        rule = DependencyViolationRule(context)
        result = rule.check()
        self.assertFalse(result.is_violated)

        # Test case 2: Violation
        context = MockProjectContext(
            schedule_items=[
                MockScheduleItem(id=item1_id, name="task1", start_date=datetime(2024, 1, 1), end_date=datetime(2024, 1, 5), predecessor_id=None),
                MockScheduleItem(id=item2_id, name="task2", start_date=datetime(2024, 1, 4), end_date=datetime(2024, 1, 10), predecessor_id=item1_id)
            ]
        )
        rule = DependencyViolationRule(context)
        result = rule.check()
        self.assertTrue(result.is_violated)
        self.assertEqual(len(result.evidence["violations"]), 1)
        self.assertEqual(result.evidence["violations"][0]["successor_id"], item2_id)


    def test_orphan_tasks_rule(self):
        # Test case 1: No violation
        context = MockProjectContext(
            wbs_items=[
                MockWBSItem(code="1", name="root", parent_code=None),
                MockWBSItem(code="1.1", name="leaf1", parent_code="1", stakeholders=[MockStakeholder(role="Responsible")])
            ]
        )
        rule = OrphanTasksRule(context)
        result = rule.check()
        self.assertFalse(result.is_violated)

        # Test case 2: Violation
        context = MockProjectContext(
            wbs_items=[
                MockWBSItem(code="1", name="root", parent_code=None),
                MockWBSItem(code="1.1", name="leaf1", parent_code="1", stakeholders=[]),
                MockWBSItem(code="1.2", name="leaf2", parent_code="1", stakeholders=[MockStakeholder(role="Approver")])
            ]
        )
        rule = OrphanTasksRule(context)
        result = rule.check()
        self.assertTrue(result.is_violated)
        self.assertIn("leaf1", result.evidence["orphan_tasks"])
        self.assertIn("leaf2", result.evidence["orphan_tasks"])

    def test_lead_time_risk_rule(self):
        # Test case 1: No violation
        context = MockProjectContext(
            bom_items=[
                MockBOMItem(item_name="item1", required_on_site_date=datetime.now() + timedelta(days=60), lead_time_days=30)
            ]
        )
        rule = LeadTimeRiskRule(context)
        result = rule.check()
        self.assertFalse(result.is_violated)

        # Test case 2: Violation
        context = MockProjectContext(
            bom_items=[
                MockBOMItem(item_name="item1", required_on_site_date=datetime.now() + timedelta(days=20), lead_time_days=30)
            ]
        )
        rule = LeadTimeRiskRule(context)
        result = rule.check()
        self.assertTrue(result.is_violated)
        self.assertEqual(len(result.evidence["risks"]), 1)
        self.assertEqual(result.evidence["risks"][0]["material"], "item1")


    def test_permitting_rule(self):
        # Test case 1: No violation (no permit clause)
        context = MockProjectContext(
            clauses=[],
            schedule_items=[]
        )
        rule = PermittingRule(context)
        result = rule.check()
        self.assertFalse(result.is_violated)

        # Test case 2: No violation (permit clause and milestone exist)
        context = MockProjectContext(
            clauses=[MockClause(id=uuid4(), text="Se necesita una licencia de construcción.")],
            schedule_items=[MockScheduleItem(id=uuid4(), name="Obtener licencia de construcción", start_date=datetime(2024,1,1), end_date=datetime(2024,1,31), predecessor_id=None)]
        )
        rule = PermittingRule(context)
        result = rule.check()
        self.assertFalse(result.is_violated)

        # Test case 3: Violation
        context = MockProjectContext(
            clauses=[MockClause(id=uuid4(), text="Se necesita un permiso de obra.")],
            schedule_items=[]
        )
        rule = PermittingRule(context)
        result = rule.check()
        self.assertTrue(result.is_violated)
        self.assertEqual(len(result.evidence["permit_clauses"]), 1)


    def test_cash_flow_rule(self):
        context = MockProjectContext()
        rule = CashFlowRule(context)
        result = rule.check()
        self.assertFalse(result.is_violated)


if __name__ == '__main__':
    unittest.main()