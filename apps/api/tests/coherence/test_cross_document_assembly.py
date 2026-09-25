"""
Cross-document assembly + live-path injection (ADR-023 Phase 1b).

Refers to Suite ID: TS-UA-COH-XDOC-ASSEMBLY-001.
"""
from __future__ import annotations

import pytest

from src.coherence.cross_document import (
    assemble_cross_doc_inputs,
    cross_document_signals,
)
from src.coherence.models import Clause


@pytest.mark.unit
def test_assemble_pulls_totals_from_clause_data() -> None:
    clauses = [
        Clause(
            id="b1",
            text="budget",
            data={
                "contract_total": 1_600_000.0,
                "stated_total": 1_200_000.0,
                "budget_items": [{"amount": 700_000.0}, {"amount": 500_000.0}],
                "currency": "EUR",
            },
        )
    ]
    inputs = assemble_cross_doc_inputs(clauses)
    assert inputs.contract_total == pytest.approx(1_600_000.0)
    assert inputs.budget_total == pytest.approx(1_200_000.0)
    assert inputs.budget_leaf_sum == pytest.approx(1_200_000.0)
    assert inputs.currency == "EUR"


@pytest.mark.unit
def test_assemble_absent_totals_are_none() -> None:
    inputs = assemble_cross_doc_inputs([Clause(id="x", text="t", data={})])
    assert inputs.contract_total is None
    assert inputs.budget_total is None
    assert inputs.budget_leaf_sum is None


@pytest.mark.unit
def test_cross_document_signals_fires_critical_on_material_gap() -> None:
    clauses = [
        Clause(
            id="b1",
            text="budget",
            data={"contract_total": 1_600_000.0, "stated_total": 1_200_000.0},
        )
    ]
    signals = cross_document_signals(clauses)
    assert {s.rule_id for s in signals} == {"DET-CRS-CONBUD"}
    assert signals[0].category == "BUDGET"
    assert signals[0].severity == "critical"  # 25% > CRITICAL_MISMATCH_RATIO


@pytest.mark.unit
def test_cross_document_signals_silent_when_aligned() -> None:
    clauses = [
        Clause(
            id="b1",
            text="budget",
            data={"contract_total": 1_000_000.0, "stated_total": 1_000_000.0},
        )
    ]
    assert cross_document_signals(clauses) == []


@pytest.mark.integration
def test_cross_doc_finding_surfaces_in_evaluate_coherence() -> None:
    """End-to-end: a contract↔budget-total gap surfaces as a DET-CRS-CONBUD signal."""
    from src.coherence.graph.graph import evaluate_coherence
    from src.coherence.graph.state import EvaluationConfig

    clauses = [
        Clause(
            id="c-budget",
            text="Presupuesto total 1.200.000 EUR; contrato 1.600.000 EUR",
            data={
                "contract_total": 1_600_000.0,
                "stated_total": 1_200_000.0,
                "budget_items": [{"amount": 600_000.0}, {"amount": 600_000.0}],
                "currency": "EUR",
            },
        )
    ]
    result = evaluate_coherence(
        clauses=clauses,
        project_id="xdoc-test",
        config=EvaluationConfig(low_budget_mode=True, include_rag_similarity=False),
    )
    assert "DET-CRS-CONBUD" in {s.rule_id for s in result.finding_signals}
