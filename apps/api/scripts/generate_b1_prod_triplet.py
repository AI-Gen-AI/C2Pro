#!/usr/bin/env python3
"""Generate bounded non-customer XLSX fixtures for #867 B1-12 qualification.

The source facts are intentionally inconsistent with PJ-01 Contract A:
- contract price: EUR 2,400,000 fixed;
- contract completion: 2025-12-31.

Budget and schedule remain synthetic and repository-owned. They exist only to
exercise the real upload/parser/Coherence/Alert review path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from openpyxl import Workbook

FIXED_TIME = datetime(2026, 10, 6, tzinfo=UTC)

BUDGET_ROWS = (
    ("Demolition and enabling works", 1, 300_000.00, 300_000.00, "gl"),
    ("Structural steel reinforcement", 1, 825_000.00, 825_000.00, "gl"),
    ("Mechanical and electrical installation", 1, 900_000.00, 900_000.00, "gl"),
    ("Finishes and closeout", 1, 625_000.00, 625_000.00, "gl"),
)
BUDGET_TOTAL = sum(row[3] for row in BUDGET_ROWS)

SCHEDULE_ROWS = (
    ("Mobilisation and demolition", "2025-06-01", "2025-07-15", 45, "1", ""),
    ("Structural works", "2025-07-16", "2025-11-15", 123, "2", "1"),
    ("MEP installation", "2025-11-16", "2026-01-10", 56, "3", "2"),
    ("Finishes and completion", "2026-01-11", "2026-01-31", 21, "4", "3"),
)


def _prepare(workbook: Workbook, title: str) -> None:
    workbook.properties.title = title
    workbook.properties.subject = "C2Pro B1-12 production qualification synthetic fixture"
    workbook.properties.creator = "AI-Gen C2Pro"
    workbook.properties.created = FIXED_TIME.replace(tzinfo=None)
    workbook.properties.modified = FIXED_TIME.replace(tzinfo=None)


def generate_budget(path: Path) -> None:
    workbook = Workbook()
    _prepare(workbook, "B1 Synthetic Budget")
    sheet = workbook.active
    sheet.title = "Budget"
    sheet.append(["Item", "Quantity", "Unit Price", "Total", "Unit"])
    for row in BUDGET_ROWS:
        sheet.append(list(row))
    sheet.append(["TOTAL PRESUPUESTO", None, None, BUDGET_TOTAL, None])
    workbook.save(path)
    workbook.close()


def generate_schedule(path: Path) -> None:
    workbook = Workbook()
    _prepare(workbook, "B1 Synthetic Schedule")
    sheet = workbook.active
    sheet.title = "Schedule"
    sheet.append(["Task", "Start Date", "End Date", "Duration", "WBS", "Predecessors"])
    for row in SCHEDULE_ROWS:
        sheet.append(list(row))
    workbook.save(path)
    workbook.close()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--manifest")
    args = parser.parse_args()

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    budget = output / "b1-budget.xlsx"
    schedule = output / "b1-schedule.xlsx"
    generate_budget(budget)
    generate_schedule(schedule)

    manifest = {
        "schema": "c2pro-b1-prod-fixtures/v1",
        "fixture_class": "synthetic_non_customer",
        "contract_authority": {
            "fixture": "PJ01-CONTRACT-A",
            "contract_price_eur": 2_400_000,
            "completion_date": "2025-12-31",
        },
        "budget": {
            "path": str(budget),
            "declared_total_eur": BUDGET_TOTAL,
            "sha256": sha256(budget),
        },
        "schedule": {
            "path": str(schedule),
            "completion_date": "2026-01-31",
            "sha256": sha256(schedule),
        },
        "intentional_conflicts": [
            "budget_total_exceeds_fixed_contract_price",
            "schedule_completion_exceeds_contract_completion",
        ],
    }
    encoded = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if args.manifest:
        manifest_path = Path(args.manifest)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
