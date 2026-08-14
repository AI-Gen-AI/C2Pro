"""TS-COH-BUD-RECON-001: structured BOM clauses for deterministic coherence."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.coherence.budget_clause_builder import build_budget_clauses
from src.coherence.rules_engine.base import ApplicabilityState
from src.coherence.rules_engine.deterministic import BudgetLineItemEvaluator


class _Result:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def fetchall(self) -> list[object]:
        return self._rows

    def scalar_one_or_none(self) -> object | None:
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, results: list[_Result]) -> None:
        self._results = results
        self.params: list[dict[str, object]] = []

    async def execute(self, _stmt: object, params: dict[str, object]) -> _Result:
        self.params.append(params)
        return self._results.pop(0)


def _row(
    *,
    item_name: str = "Concrete",
    quantity: Decimal | None = Decimal("2.5000"),
    unit_price: Decimal | None = Decimal("100.00"),
    total_price: Decimal | None = Decimal("250.00"),
    unit: str | None = None,
) -> object:
    return SimpleNamespace(
        id=uuid4(),
        item_name=item_name,
        quantity=quantity,
        unit_price=unit_price,
        total_price=total_price,
        unit=unit,
    )


@pytest.mark.asyncio
async def test_build_budget_clauses_returns_line_items_and_reconciliation() -> None:
    """TS-COH-BUD-RECON-001: BOM rows become line and reconciliation clauses."""
    project_id = uuid4()
    tenant_id = uuid4()
    rows = [
        _row(item_name="Concrete", total_price=Decimal("250.00")),
        _row(item_name="Steel", quantity=Decimal("1.0000"), unit_price=Decimal("50.00"), total_price=Decimal("50.00")),
    ]
    session = _Session([_Result(rows), _Result([Decimal("280.00")]), _Result([Decimal("310.00")])])

    clauses = await build_budget_clauses(session, project_id, tenant_id)  # type: ignore[arg-type]

    assert len(clauses) == 3
    line_clauses = [clause for clause in clauses if clause.id.startswith("bom-")]
    assert len(line_clauses) == 2
    assert all(clause.data["source"] == "procurement_bom" for clause in line_clauses)
    assert all(
        BudgetLineItemEvaluator().applicability(clause) == ApplicabilityState.EVALUATED
        for clause in line_clauses
    )
    reconciliation = clauses[-1]
    assert reconciliation.id == f"budget-reconciliation-{project_id}"
    assert reconciliation.data["contract_total"] == 280.0
    assert reconciliation.data["stated_total"] == 310.0
    assert reconciliation.data["budget_items"] == [
        {"amount": 250.0, "name": "Concrete"},
        {"amount": 50.0, "name": "Steel"},
    ]
    assert all(params["tenant_id"] == str(tenant_id) for params in session.params)


@pytest.mark.asyncio
async def test_build_budget_clauses_returns_empty_without_bom_rows() -> None:
    """TS-COH-BUD-RECON-001: no structured BOM rows means no fabricated budget clauses."""
    session = _Session([_Result([])])

    clauses = await build_budget_clauses(session, uuid4(), uuid4())  # type: ignore[arg-type]

    assert clauses == []


@pytest.mark.asyncio
async def test_build_budget_clauses_skips_reconciliation_without_contract_total() -> None:
    """TS-COH-BUD-RECON-004: missing totals keep only honest line items."""
    rows = [_row(item_name="Concrete")]
    session = _Session([_Result(rows), _Result([]), _Result([])])

    clauses = await build_budget_clauses(session, uuid4(), uuid4())  # type: ignore[arg-type]

    assert len(clauses) == 1
    assert clauses[0].id.startswith("bom-")
    assert "budget_items" not in clauses[0].data


@pytest.mark.asyncio
async def test_build_budget_clauses_reconciles_with_stated_total_only() -> None:
    """TS-COH-BUD-RECON-004: stated total can drive internal reconciliation alone."""
    project_id = uuid4()
    rows = [_row(item_name="Concrete", total_price=Decimal("250.00"))]
    session = _Session([_Result(rows), _Result([]), _Result([Decimal("310.00")])])

    clauses = await build_budget_clauses(session, project_id, uuid4())  # type: ignore[arg-type]

    assert len(clauses) == 2
    reconciliation = clauses[-1]
    assert reconciliation.id == f"budget-reconciliation-{project_id}"
    assert reconciliation.data["budget_items"] == [{"amount": 250.0, "name": "Concrete"}]
    assert reconciliation.data["stated_total"] == 310.0
    assert "contract_total" not in reconciliation.data


@pytest.mark.asyncio
async def test_build_budget_clauses_reconciles_with_contract_total_only() -> None:
    """TS-COH-BUD-RECON-004: contract total remains sufficient for DET-BUD-SUM."""
    project_id = uuid4()
    rows = [_row(item_name="Concrete", total_price=Decimal("250.00"))]
    session = _Session([_Result(rows), _Result([Decimal("280.00")]), _Result([])])

    clauses = await build_budget_clauses(session, project_id, uuid4())  # type: ignore[arg-type]

    assert len(clauses) == 2
    reconciliation = clauses[-1]
    assert reconciliation.data["contract_total"] == 280.0
    assert "stated_total" not in reconciliation.data
