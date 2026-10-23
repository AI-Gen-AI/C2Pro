"""
Cross-document money comparisons need one denomination (PQ-HITL-09 S7).

A contract in EUR and a budget in USD have no FX basis in the project model, so
comparing their bare totals would assert a margin or overrun that does not exist.
Such comparisons are NOT_ASSESSED: no finding, no signal, an explicit reason.

Refers to Suite ID: TS-UD-COH-XDOC-CURRENCY-001.
"""
from __future__ import annotations

import pytest

from src.coherence.cross_document import (
    RULE_BUDGET_EXCEEDS_CONTRACT,
    RULE_CONTRACT_VS_BUDGET,
    CrossDocFinding,
    CrossDocNotAssessed,
    ProjectCrossDocInputs,
    assemble_cross_doc_inputs,
    assess_numeric_comparators,
    budget_exceeds_contract,
    contract_vs_budget_total,
    cross_document_signals,
    run_numeric_comparators,
)
from src.coherence.models import Clause


def _contract(total: float, currency: str | None) -> Clause:
    data: dict[str, object] = {"contract_total": total}
    if currency is not None:
        data["currency"] = currency
    return Clause(id="contract", text="contract price", data=data)


def _budget(total: float, currency: str | None, items: list[dict] | None = None) -> Clause:
    data: dict[str, object] = {"stated_total": total}
    if currency is not None:
        data["currency"] = currency
    if items is not None:
        data["budget_items"] = items
    return Clause(id="budget", text="budget total", data=data)


@pytest.mark.unit
def test_assembly_keeps_each_side_denomination() -> None:
    inputs = assemble_cross_doc_inputs([_contract(1_600_000.0, "EUR"), _budget(1_200_000.0, "USD")])
    assert inputs.contract_currencies == frozenset({"EUR"})
    assert inputs.budget_currencies == frozenset({"USD"})


@pytest.mark.unit
def test_contract_and_budget_in_different_currencies_are_not_assessed() -> None:
    # 25% "gap" and a budget "overrun" that only exist if EUR == USD.
    clauses = [_contract(1_200_000.0, "EUR"), _budget(1_600_000.0, "USD")]
    assert cross_document_signals(clauses) == []

    assessment = assess_numeric_comparators(assemble_cross_doc_inputs(clauses))
    assert assessment.findings == []
    assert {(n.rule_id, n.reason, n.state) for n in assessment.not_assessed} == {
        (RULE_CONTRACT_VS_BUDGET, "CURRENCY_MISMATCH", "NOT_ASSESSED"),
        (RULE_BUDGET_EXCEEDS_CONTRACT, "CURRENCY_MISMATCH", "NOT_ASSESSED"),
    }


@pytest.mark.unit
def test_comparators_return_not_assessed_instead_of_a_finding() -> None:
    inputs = ProjectCrossDocInputs(
        contract_total=1_000_000.0,
        budget_total=2_000_000.0,
        contract_currencies=frozenset({"GBP"}),
        budget_currencies=frozenset({"EUR"}),
    )
    for comparator in (contract_vs_budget_total, budget_exceeds_contract):
        outcome = comparator(inputs)
        assert isinstance(outcome, CrossDocNotAssessed)
        assert not isinstance(outcome, CrossDocFinding)
        assert "GBP" in outcome.detail and "EUR" in outcome.detail
    assert run_numeric_comparators(inputs) == []


@pytest.mark.unit
def test_mixed_currency_budget_lines_are_not_assessed() -> None:
    clauses = [
        _contract(1_000_000.0, "EUR"),
        _budget(
            1_000_000.0,
            None,
            items=[
                {"amount": 500_000.0, "currency": "EUR"},
                {"amount": 500_000.0, "currency": "USD"},
            ],
        ),
    ]
    assessment = assess_numeric_comparators(assemble_cross_doc_inputs(clauses))
    assert assessment.findings == []
    assert {n.reason for n in assessment.not_assessed} == {"MIXED_CURRENCY"}


@pytest.mark.unit
def test_symbol_and_iso_code_of_one_currency_still_compare() -> None:
    clauses = [_contract(1_600_000.0, "€"), _budget(1_200_000.0, " eur ")]
    signals = cross_document_signals(clauses)
    assert {s.rule_id for s in signals} == {RULE_CONTRACT_VS_BUDGET}


@pytest.mark.unit
def test_same_currency_budget_overrun_is_still_flagged() -> None:
    clauses = [_contract(1_000_000.0, "USD"), _budget(1_100_000.0, "USD")]
    assert RULE_BUDGET_EXCEEDS_CONTRACT in {s.rule_id for s in cross_document_signals(clauses)}


@pytest.mark.unit
def test_unstated_currency_keeps_the_existing_comparison() -> None:
    # No denomination evidence on either side: behaviour is unchanged.
    clauses = [_contract(1_600_000.0, None), _budget(1_200_000.0, None)]
    assert {s.rule_id for s in cross_document_signals(clauses)} == {RULE_CONTRACT_VS_BUDGET}
