from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "calibration_dataset.json"

sys.path.insert(0, str(PROJECT_ROOT))

from scripts.weights_config import RULE_SEVERITY, SEVERITY_WEIGHTS, SENSITIVITY
from apps.api.src.modules.coherence.rules.cost_rules import CostVarianceRule
from apps.api.src.modules.coherence.rules.schedule_rules import DependencyViolationRule
from apps.api.src.modules.coherence.rules.supply_chain_rules import LeadTimeRiskRule
from apps.api.src.modules.coherence.rules.compliance_rules import PermittingRule
from apps.api.src.modules.coherence.rules_engine.context_rules import CoherenceRuleResult


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
class Clause:
    text: str


@dataclass
class ProjectContext:
    contract: Contract
    budget_items: list[BudgetItem]
    schedule_items: list[ScheduleItem]
    bom_items: list[BomItem]
    wbs_items: list[object]
    clauses: list[Clause]


def _load_dataset() -> list[dict]:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATASET_PATH}")
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def _parse_project(payload: dict) -> ProjectContext:
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
    clauses = [Clause(text=item["text"]) for item in payload.get("clauses", [])]
    return ProjectContext(
        contract=contract,
        budget_items=budget_items,
        schedule_items=schedule_items,
        bom_items=bom_items,
        wbs_items=[],
        clauses=clauses,
    )


def _run_rules(project: ProjectContext) -> list[CoherenceRuleResult]:
    rule_classes = [
        DependencyViolationRule,
        CostVarianceRule,
        LeadTimeRiskRule,
        PermittingRule,
    ]
    results: list[CoherenceRuleResult] = []
    for rule_class in rule_classes:
        result = rule_class(project).check()
        if result.is_violated:
            results.append(result)
    return results


def _severity_for(result: CoherenceRuleResult) -> str:
    if result.evidence and isinstance(result.evidence, dict):
        severity = str(result.evidence.get("severity", "")).lower()
        if severity:
            return severity
    return RULE_SEVERITY.get(result.rule_id, "low")


def _score_from_results(results: Iterable[CoherenceRuleResult]) -> tuple[int, dict[str, int], list[str], float]:
    severity_breakdown = {key: 0 for key in SEVERITY_WEIGHTS}
    penalties: dict[str, float] = {}
    raw_penalty = 0.0

    for result in results:
        severity = _severity_for(result)
        weight = SEVERITY_WEIGHTS.get(severity, 0)
        raw_penalty += weight
        severity_breakdown[severity] += 1
        penalties[result.rule_id] = penalties.get(result.rule_id, 0) + weight

    normalized = 100 / (1 + (raw_penalty / SENSITIVITY))
    score = int(max(0, min(100, normalized)))
    top_drivers = [rule_id for rule_id, _ in sorted(penalties.items(), key=lambda item: item[1], reverse=True)[:5]]
    return score, severity_breakdown, top_drivers, raw_penalty


def _pearson(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or not x:
        return 0.0
    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    den_x = math.sqrt(sum((a - mean_x) ** 2 for a in x))
    den_y = math.sqrt(sum((b - mean_y) ** 2 for b in y))
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


def _mse(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or not x:
        return 0.0
    return sum((a - b) ** 2 for a, b in zip(x, y)) / len(x)


def _render_ascii_table(rows: list[dict]) -> None:
    header = f"{'project_id':<24} {'human':>6} {'ai':>6} {'diff':>6} {'penalty':>8}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['project_id']:<24} {row['human_score']:>6.1f} {row['ai_score']:>6.1f} "
            f"{row['diff']:>6.1f} {row['raw_penalty']:>8.1f}"
        )


def _maybe_plot(rows: list[dict]) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return

    human = [row["human_score"] for row in rows]
    ai = [row["ai_score"] for row in rows]

    plt.figure(figsize=(6, 5))
    plt.scatter(human, ai, alpha=0.75)
    plt.plot([0, 100], [0, 100], linestyle="--", color="gray")
    plt.xlabel("Human score")
    plt.ylabel("AI score")
    plt.title("Calibration scatter plot")
    output_path = PROJECT_ROOT / "calibration_scatter.png"
    plt.tight_layout()
    plt.savefig(output_path)
    print(f"Saved scatter plot to {output_path}")


def main() -> int:
    dataset = _load_dataset()
    rows: list[dict] = []
    ai_scores: list[float] = []
    human_scores: list[float] = []

    for entry in dataset:
        project_id = entry.get("project_id") or entry.get("id") or "unknown"
        human_score = float(entry["human_score"])
        project_context = _parse_project(entry["project"])
        results = _run_rules(project_context)
        ai_score, breakdown, top_drivers, raw_penalty = _score_from_results(results)

        rows.append(
            {
                "project_id": project_id,
                "human_score": human_score,
                "ai_score": ai_score,
                "diff": ai_score - human_score,
                "raw_penalty": raw_penalty,
                "top_drivers": top_drivers,
                "breakdown": breakdown,
            }
        )
        ai_scores.append(ai_score)
        human_scores.append(human_score)

    mse = _mse(ai_scores, human_scores)
    corr = _pearson(ai_scores, human_scores)

    _render_ascii_table(rows)
    _maybe_plot(rows)

    print(f"\nMSE: {mse:.2f}")
    print(f"Pearson correlation: {corr:.3f}")

    if corr < 0.85:
        print("Calibration below target correlation. Consider adjusting weights.")
        top_penalties: dict[str, float] = {}
        for row in rows:
            for rule_id in row["top_drivers"]:
                top_penalties[rule_id] = top_penalties.get(rule_id, 0) + 1
        if top_penalties:
            print("Rules most frequently driving penalties:")
            for rule_id, count in sorted(top_penalties.items(), key=lambda item: item[1], reverse=True):
                print(f"  {rule_id}: {count} projects")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
