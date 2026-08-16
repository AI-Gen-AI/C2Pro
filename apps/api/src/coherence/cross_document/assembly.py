"""
Assemble project-level cross-document inputs from clause data (ADR-023 Phase 1b).

Interim heuristic assembly: reads the same fields the deterministic budget evaluators
already rely on — the contract total (`contract_total` / `total_amount`), the budget's
declared total (`stated_total`), and the budget leaf sum (`budget_items[].amount`) —
from whichever clauses carry them. The real, typed assembly is the Tier-2 artifact
layer (ADR-017); this lets the Phase-1b comparators surface findings on the current
per-clause pipeline without waiting for it.

Refers to Suite ID: TS-UA-COH-XDOC-ASSEMBLY-001.
"""
from __future__ import annotations

from collections.abc import Iterable

from src.coherence.cross_document.comparators import run_numeric_comparators
from src.coherence.cross_document.inputs import ProjectCrossDocInputs
from src.coherence.cross_document.signal_adapter import to_finding_signal
from src.coherence.models import Clause, FindingSignal


def _num(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def assemble_cross_doc_inputs(clauses: Iterable[Clause]) -> ProjectCrossDocInputs:
    """Build `ProjectCrossDocInputs` from the totals carried in clause data.

    Contract/budget totals are taken as the maximum seen (the project-level figure
    dominates individual line totals). Absent values stay None so the comparators
    simply do not fire — no false positives on missing data.
    """
    contract_totals: list[float] = []
    budget_totals: list[float] = []
    leaf_sum = 0.0
    leaf_seen = False
    currency: str | None = None

    for clause in clauses:
        data = getattr(clause, "data", None) or {}

        contract_total = _num(data.get("contract_total"))
        if contract_total is None:
            contract_total = _num(data.get("total_amount"))
        if contract_total is not None:
            contract_totals.append(contract_total)

        stated_total = _num(data.get("stated_total"))
        if stated_total is not None:
            budget_totals.append(stated_total)

        items = data.get("budget_items")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    amount = _num(item.get("amount"))
                    if amount is not None:
                        leaf_sum += amount
                        leaf_seen = True

        if currency is None and isinstance(data.get("currency"), str):
            currency = data["currency"]

    return ProjectCrossDocInputs(
        contract_total=max(contract_totals) if contract_totals else None,
        budget_total=max(budget_totals) if budget_totals else None,
        budget_leaf_sum=leaf_sum if leaf_seen else None,
        currency=currency,
    )


def cross_document_signals(clauses: Iterable[Clause]) -> list[FindingSignal]:
    """Assemble inputs, run the numeric comparators, and adapt findings to signals."""
    inputs = assemble_cross_doc_inputs(clauses)
    return [to_finding_signal(finding) for finding in run_numeric_comparators(inputs)]


__all__ = ["assemble_cross_doc_inputs", "cross_document_signals"]
