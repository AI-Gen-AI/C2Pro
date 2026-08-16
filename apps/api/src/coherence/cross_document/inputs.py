"""
Assembled cross-document inputs for the Phase-1b comparators (ADR-023).

`ProjectCrossDocInputs` is the *assembled* view — one numeric aggregate per document,
each `None` when that document is absent or the value couldn't be extracted. The
extraction/assembly that populates this (per-document totals) is a separate step; the
comparators depend only on this typed struct, which keeps them pure and testable.

Refers to Suite ID: TS-UD-COH-XDOC-INPUTS-001.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectCrossDocInputs:
    """Cross-document numeric aggregates (each None when its source doc is missing)."""

    contract_total: float | None = None  # contractual price (from the contract)
    budget_total: float | None = None  # stated total (from the budget)
    budget_leaf_sum: float | None = None  # sum of budget line items
    wbs_total: float | None = None  # sum of WBS work-package costs
    bom_total: float | None = None  # sum of BOM line costs
    currency: str | None = None  # reserved for a future FX-mismatch guard


__all__ = ["ProjectCrossDocInputs"]
