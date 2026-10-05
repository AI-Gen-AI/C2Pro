"""Contracts for bounded #867 B1 production fixtures."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import openpyxl

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "apps/api/scripts/generate_b1_prod_triplet.py"


def _module():
    spec = importlib.util.spec_from_file_location("b1_fixture_generator", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_b1_fixture_facts_conflict_with_pj01_contract_a() -> None:
    module = _module()
    assert module.BUDGET_TOTAL > 2_400_000
    assert module.SCHEDULE_ROWS[-1][2] > "2025-12-31"


def test_b1_budget_xlsx_uses_canonical_parser_headers(tmp_path: Path) -> None:
    module = _module()
    path = tmp_path / "budget.xlsx"
    module.generate_budget(path)
    workbook = openpyxl.load_workbook(path, data_only=True)
    try:
        sheet = workbook.active
        headers = [cell.value for cell in sheet[1]]
        assert headers == ["Item", "Quantity", "Unit Price", "Total", "Unit"]
        assert sheet.max_row >= 3
    finally:
        workbook.close()


def test_b1_schedule_xlsx_uses_canonical_parser_headers(tmp_path: Path) -> None:
    module = _module()
    path = tmp_path / "schedule.xlsx"
    module.generate_schedule(path)
    workbook = openpyxl.load_workbook(path, data_only=True)
    try:
        sheet = workbook.active
        headers = [cell.value for cell in sheet[1]]
        assert headers == [
            "Task",
            "Start Date",
            "End Date",
            "Duration",
            "WBS",
            "Predecessors",
        ]
        assert sheet.max_row >= 3
    finally:
        workbook.close()
