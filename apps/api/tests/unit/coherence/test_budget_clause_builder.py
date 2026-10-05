"""TS-COH-BUD-RECON-001 / #860: budget-document facts for deterministic coherence.

Supersedes the BOM-row clause contract: the procurement BOM is a mixed legacy
object, not budget truth, so no BOM row becomes a budget line clause and the rules
that need structured budget lines are not evaluated. The budget document's own
declared total (plus the contract total) still reaches the total-level rules.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from src.coherence.budget_clause_builder import build_budget_clauses
from src.coherence.domain.budget_line_availability import STRUCTURED_BUDGET_SOURCE_UNAVAILABLE
from src.coherence.rules_engine.base import ApplicabilityState
from src.coherence.rules_engine.deterministic import (
    BudgetInternalConsistencyEvaluator,
    BudgetLineItemEvaluator,
    BudgetSumMismatchEvaluator,
)


class _Result:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def scalar_one_or_none(self) -> object | None:
        return self._rows[0] if self._rows else None


class _Session:
    """Answers the stated-total query first, then the contract-total query."""

    def __init__(self, results: list[_Result]) -> None:
        self._results = results
        self.params: list[dict[str, object]] = []

    async def execute(self, _stmt: object, params: dict[str, object]) -> _Result:
        self.params.append(params)
        return self._results.pop(0)


@pytest.mark.asyncio
async def test_stated_and_contract_totals_reach_one_declared_total_clause() -> None:
    project_id = uuid4()
    tenant_id = uuid4()
    session = _Session([_Result([Decimal("310.00")]), _Result([Decimal("280.00")])])

    clauses = await build_budget_clauses(session, project_id, tenant_id)  # type: ignore[arg-type]

    [clause] = clauses
    assert clause.id == f"budget-reconciliation-{project_id}"
    assert clause.data["source"] == "budget_document_metadata"
    assert clause.data["stated_total"] == 310.0
    assert clause.data["contract_total"] == 280.0
    assert clause.data["budget_line_items"] == "unavailable"
    assert clause.data["budget_line_items_reason"] == STRUCTURED_BUDGET_SOURCE_UNAVAILABLE
    assert "budget_items" not in clause.data
    assert all(params["tenant_id"] == str(tenant_id) for params in session.params)


@pytest.mark.asyncio
async def test_budget_line_rules_are_not_evaluated_from_the_declared_total() -> None:
    """No line set is derived from ``stated_total``: the line rules stay unassessed."""
    session = _Session([_Result([Decimal("310.00")]), _Result([Decimal("280.00")])])

    [clause] = await build_budget_clauses(session, uuid4(), uuid4())  # type: ignore[arg-type]

    for evaluator in (
        BudgetLineItemEvaluator(),
        BudgetSumMismatchEvaluator(),
        BudgetInternalConsistencyEvaluator(),
    ):
        assert evaluator.applicability(clause) is not ApplicabilityState.EVALUATED
        assert evaluator.evaluate_v3(clause) is None


@pytest.mark.asyncio
async def test_no_stated_total_means_no_fabricated_budget_clause() -> None:
    session = _Session([_Result([])])

    clauses = await build_budget_clauses(session, uuid4(), uuid4())  # type: ignore[arg-type]

    assert clauses == []
    assert len(session.params) == 1


@pytest.mark.asyncio
async def test_stated_total_alone_is_kept_without_a_contract_total() -> None:
    project_id = uuid4()
    session = _Session([_Result([Decimal("310.00")]), _Result([])])

    [clause] = await build_budget_clauses(session, project_id, uuid4())  # type: ignore[arg-type]

    assert clause.data["stated_total"] == 310.0
    assert "contract_total" not in clause.data
