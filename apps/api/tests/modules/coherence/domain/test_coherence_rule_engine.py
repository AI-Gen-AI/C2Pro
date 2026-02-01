
import pytest
from uuid import uuid4
from typing import List, NamedTuple, Dict, Optional
from enum import Enum, auto
from datetime import date, timedelta

# This import will fail as the modules do not exist yet.
from apps.api.src.coherence.domain.coherence_rule_engine import (
    CoherenceRuleEngine,
    ProjectData,
    CoherenceResult,
    CoherenceSeverity,
    CoherenceStatus,
    WBSItem,
    Activity,
    BudgetLine,
    ScopeClause,
    BOMItem, 
    BudgetVsActual,
    BudgetTrend,
    # New models for RUL-003
    Contract,
    Schedule,
    Milestone,
    ProcurementOrder,
)


# --- Test-specific Data Models (matching what the engine expects) ---
# These are re-declared here to avoid import errors until the actual models exist
class WBSItem(NamedTuple):
    id: UUID
    name: str
    level: int

class Activity(NamedTuple):
    id: UUID
    wbs_id: UUID
    date: date # Add date for R2

class BudgetLine(NamedTuple):
    id: UUID
    wbs_id: UUID
    amount: float

class ScopeClause(NamedTuple):
    id: UUID
    content: str
    wbs_ids: List[UUID] = []

class BOMItem(NamedTuple):
    id: UUID
    wbs_id: UUID
    budget_id: Optional[UUID] = None
    client_provided: bool = False

class BudgetVsActual(NamedTuple):
    wbs_id: UUID
    budgeted_amount: float
    actual_amount: float

class BudgetTrend(NamedTuple):
    wbs_id: UUID
    current_deviation_percent: float
    previous_deviation_percent: float

# New data models for RUL-003
class Contract(NamedTuple):
    id: UUID
    start_date: date
    end_date: date

class Schedule(NamedTuple):
    id: UUID
    contract_id: UUID
    date: date

class Milestone(NamedTuple):
    id: UUID
    name: str
    date: date
    activity_ids: List[UUID]

class ProcurementOrder(NamedTuple):
    id: UUID
    expected_delivery_date: date


class ProjectData(NamedTuple):
    wbs_items: List[WBSItem] = []
    activities: List[Activity] = []
    budget_lines: List[BudgetLine] = []
    scope_clauses: List[ScopeClause] = []
    bom_items: List[BOMItem] = []
    budget_vs_actual: List[BudgetVsActual] = []
    budget_trends: List[BudgetTrend] = []
    # New
    contracts: List[Contract] = []
    schedules: List[Schedule] = []
    milestones: List[Milestone] = []
    procurement_orders: List[ProcurementOrder] = []
    current_date: date = date.today()


# --- Test Fixture ---
@pytest.fixture
def rule_engine() -> CoherenceRuleEngine:
    """Provides an instance of the CoherenceRuleEngine."""
    return CoherenceRuleEngine()


# --- Test Cases ---
@pytest.mark.asyncio
class TestCoherenceRuleEngine:
    """Refers to Suite ID: TS-UD-COH-RUL-001, TS-UD-COH-RUL-002, TS-UD-COH-RUL-003"""

    # --- Rule R1 Tests ---
    @pytest.mark.parametrize("schedule_date, contract_date, expected_status, expected_severity, delta", [
        (date(2024, 1, 10), date(2024, 1, 1), CoherenceStatus.FAIL, CoherenceSeverity.HIGH, 9), # Schedule late -> Critical
        (date(2024, 1, 1), date(2024, 1, 10), CoherenceStatus.WARN, CoherenceSeverity.MEDIUM, -9), # Schedule early -> Warning
        (date(2024, 1, 1), date(2024, 1, 1), CoherenceStatus.PASS, None, 0), # Match -> Pass
    ])
    async def test_001_to_005_r1_schedule_vs_contract_dates(self, rule_engine, schedule_date, contract_date, expected_status, expected_severity, delta):
        contract = Contract(id=uuid4(), start_date=contract_date, end_date=date(2025, 1, 1))
        schedule = Schedule(id=uuid4(), contract_id=contract.id, date=schedule_date)
        project_data = ProjectData(contracts=[contract], schedules=[schedule])

        results = await rule_engine.evaluate(project_data)
        r1_result = next((r for r in results if r.rule_id == "R1"), None)

        if expected_status == CoherenceStatus.PASS:
            assert r1_result is None
        else:
            assert r1_result is not None
            assert r1_result.status == expected_status
            assert r1_result.severity == expected_severity
            assert r1_result.metadata["delta_days"] == delta
            assert schedule.id in r1_result.affected_entities

    # --- Rule R2 Tests ---
    async def test_006_r2_milestone_no_activity_alert(self, rule_engine):
        milestone = Milestone(id=uuid4(), name="Phase 1", date=date(2024, 5, 5), activity_ids=[])
        project_data = ProjectData(milestones=[milestone])
        results = await rule_engine.evaluate(project_data)
        r2_result = next((r for r in results if r.rule_id == "R2"), None)
        assert r2_result is not None
        assert r2_result.status == CoherenceStatus.FAIL
        assert milestone.id in r2_result.affected_entities

    async def test_008_r2_milestone_date_mismatch_alert(self, rule_engine):
        activity = Activity(id=uuid4(), wbs_id=uuid4(), date=date(2024, 5, 10))
        milestone = Milestone(id=uuid4(), name="Phase 1", date=date(2024, 5, 5), activity_ids=[activity.id])
        project_data = ProjectData(milestones=[milestone], activities=[activity])
        results = await rule_engine.evaluate(project_data)
        r2_result = next((r for r in results if r.rule_id == "R2"), None)
        assert r2_result is not None
        assert r2_result.status == CoherenceStatus.FAIL
        assert milestone.id in r2_result.affected_entities

    async def test_007_r2_milestone_with_activity_pass(self, rule_engine):
        activity = Activity(id=uuid4(), wbs_id=uuid4(), date=date(2024, 5, 5))
        milestone = Milestone(id=uuid4(), name="Phase 1", date=date(2024, 5, 5), activity_ids=[activity.id])
        project_data = ProjectData(milestones=[milestone], activities=[activity])
        results = await rule_engine.evaluate(project_data)
        r2_failures = [r for r in results if r.rule_id == "R2" and r.status == CoherenceStatus.FAIL]
        assert len(r2_failures) == 0

    # --- Rule R5 Tests ---
    async def test_011_r5_activity_exceeds_contract_alert(self, rule_engine):
        contract = Contract(id=uuid4(), start_date=date(2024, 1, 1), end_date=date(2024, 12, 31))
        activity = Activity(id=uuid4(), wbs_id=uuid4(), date=date(2025, 1, 10)) # Outside range
        project_data = ProjectData(contracts=[contract], activities=[activity])
        results = await rule_engine.evaluate(project_data)
        r5_result = next((r for r in results if r.rule_id == "R5"), None)
        assert r5_result is not None
        assert r5_result.status == CoherenceStatus.FAIL
        assert r5_result.severity == CoherenceSeverity.HIGH
        assert activity.id in r5_result.affected_entities

    async def test_012_r5_activity_within_contract_pass(self, rule_engine):
        contract = Contract(id=uuid4(), start_date=date(2024, 1, 1), end_date=date(2024, 12, 31))
        activity = Activity(id=uuid4(), wbs_id=uuid4(), date=date(2024, 6, 15)) # Within range
        project_data = ProjectData(contracts=[contract], activities=[activity])
        results = await rule_engine.evaluate(project_data)
        r5_failures = [r for r in results if r.rule_id == "R5" and r.status == CoherenceStatus.FAIL]
        assert len(r5_failures) == 0

    # --- Rule R14 Tests ---
    @pytest.mark.parametrize("delivery_date_delta, expected_status, expected_severity", [
        (-5, CoherenceStatus.FAIL, CoherenceSeverity.HIGH), # 5 days passed -> Critical
        (5, CoherenceStatus.WARN, CoherenceSeverity.MEDIUM),  # In 5 days -> Warning
        (10, CoherenceStatus.PASS, None), # In 10 days -> Pass
    ])
    async def test_015_016_r14_order_date(self, rule_engine, delivery_date_delta, expected_status, expected_severity):
        current_date = date.today()
        delivery_date = current_date + timedelta(days=delivery_date_delta)
        order = ProcurementOrder(id=uuid4(), expected_delivery_date=delivery_date)
        project_data = ProjectData(procurement_orders=[order], current_date=current_date)

        results = await rule_engine.evaluate(project_data)
        r14_result = next((r for r in results if r.rule_id == "R14"), None)

        if expected_status == CoherenceStatus.PASS:
            assert r14_result is None
        else:
            assert r14_result is not None
            assert r14_result.status == expected_status
            assert r14_result.severity == expected_severity
            assert order.id in r14_result.affected_entities

