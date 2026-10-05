#!/usr/bin/env python3
"""Generate deterministic non-customer XLSX fixtures for #867 production qualification."""

from __future__ import annotations

from pathlib import Path

import openpyxl

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = REPO_ROOT / "apps" / "web" / "playwright" / ".prod-b1" / "fixtures"


def _budget(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Budget"
    ws.append(["Item", "Quantity", "Unit", "Unit Price", "Total"])
    ws.append(["Structural works", 1, "lot", 1_200_000, 1_200_000])
    ws.append(["MEP works", 1, "lot", 800_000, 800_000])
    ws.append(["Finishes", 1, "lot", 400_000, 400_000])
    ws.append(["Total presupuesto", None, None, None, 2_400_000])
    wb.save(path)


def _schedule(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Schedule"
    ws.append(["WBS", "Task", "Start Date", "End Date", "Duration", "Predecessors"])
    ws.append(["1", "Construction works", "2025-06-01", "2025-10-31", 153, None])
    ws.append(["2", "Commissioning and handover", "2025-11-01", "2025-12-31", 61, "1"])
    wb.save(path)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    budget = OUTPUT_DIR / "b1-budget.xlsx"
    schedule = OUTPUT_DIR / "b1-schedule.xlsx"
    _budget(budget)
    _schedule(schedule)
    print(f"B1_BUDGET_FIXTURE={budget}")
    print(f"B1_SCHEDULE_FIXTURE={schedule}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
