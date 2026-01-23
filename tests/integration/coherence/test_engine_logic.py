from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter

from src.modules.coherence.rules.cost_rules import CostVarianceRule
from src.modules.coherence.rules.schedule_rules import DependencyViolationRule
from src.modules.coherence.rules.supply_chain_rules import LeadTimeRiskRule


FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "scenarios"


@dataclass
class Contract:
    total_amount: float


@dataclass
class BudgetItem:
    amount: float


@dataclass
class ScheduleItem:
    id: str
    name: str
    start_date: datetime
    end_date: datetime
    predecessor_id: str | None


@dataclass
class BomItem:
    item_name: str
    required_on_site_date: datetime | None
    lead_time_days: int | None
    budget_item_id: str | None


@dataclass
class ProjectContext:
    contract: Contract
    budget_items: list[BudgetItem]
    schedule_items: list[ScheduleItem]
    bom_items: list[BomItem]
    wbs_items: list[object]
    clauses: list[object]


def _load_scenario(name: str) -> ProjectContext:
    payload = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    contract = Contract(total_amount=float(payload["contract"]["total_amount"]))
    budget_items = [BudgetItem(amount=float(item["amount"])) for item in payload["budget_items"]]
    schedule_items = [
        ScheduleItem(
            id=item["id"],
            name=item["name"],
            start_date=datetime.fromisoformat(item["start_date"]),
            end_date=datetime.fromisoformat(item["end_date"]),
            predecessor_id=item.get("predecessor_id"),
        )
        for item in payload["schedule_items"]
    ]
    bom_items = [
        BomItem(
            item_name=item["item_name"],
            required_on_site_date=datetime.fromisoformat(item["required_on_site_date"])
            if item.get("required_on_site_date")
            else None,
            lead_time_days=item.get("lead_time_days"),
            budget_item_id=item.get("budget_item_id"),
        )
        for item in payload["bom_items"]
    ]
    return ProjectContext(
        contract=contract,
        budget_items=budget_items,
        schedule_items=schedule_items,
        bom_items=bom_items,
        wbs_items=[],
        clauses=[],
    )


def _run_rules(project: ProjectContext):
    results = []
    for rule_class in (DependencyViolationRule, CostVarianceRule, LeadTimeRiskRule):
        result = rule_class(project).check()
        if result.is_violated:
            results.append(result)
    return results


def _calculate_score(results) -> float:
    severity_weights = {
        "critical": 30,
        "high": 20,
        "medium": 10,
        "low": 5,
    }
    score = 100.0
    for result in results:
        severity = "low"
        if result.evidence and isinstance(result.evidence, dict):
            severity = str(result.evidence.get("severity", "low"))
        score -= severity_weights.get(severity.lower(), 0)
    return max(0.0, score)


def test_r12_dependency_violation_triggers_alert() -> None:
    project = _load_scenario("scenario_disaster.json")
    results = _run_rules(project)

    match = next((result for result in results if result.rule_id == "R12"), None)
    assert match is not None
    assert match.evidence is not None
    assert match.evidence.get("severity") == "CRITICAL"


def test_r02_budget_overrun_triggers_alert() -> None:
    project = _load_scenario("scenario_disaster.json")
    results = _run_rules(project)

    match = next((result for result in results if result.rule_id == "R2"), None)
    assert match is not None


def test_r14_lead_time_risk_triggers_alert() -> None:
    project = _load_scenario("scenario_disaster.json")
    results = _run_rules(project)

    match = next((result for result in results if result.rule_id == "R14"), None)
    assert match is not None
    assert match.evidence is not None
    assert match.evidence.get("severity") == "CRITICAL"


def test_score_perfect_scenario_high_and_no_alerts() -> None:
    project = _load_scenario("scenario_perfect.json")
    results = _run_rules(project)
    score = _calculate_score(results)

    assert score >= 90.0
    assert results == []


def test_calculate_score_performance() -> None:
    project = _load_scenario("scenario_disaster.json")
    results = _run_rules(project)

    start = perf_counter()
    _ = _calculate_score(results)
    elapsed_ms = (perf_counter() - start) * 1000

    assert elapsed_ms < 200
