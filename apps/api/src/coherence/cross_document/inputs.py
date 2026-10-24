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

# Date kinds. Only a contractual COMPLETION deadline is comparable with the schedule's
# planned finish: a milestone date, a stated duration ("plazo") or a start date answer
# different questions and are never substituted for it.
DATE_KIND_CONTRACT_COMPLETION = "CONTRACT_COMPLETION_DEADLINE"
DATE_KIND_SCHEDULE_FINISH = "SCHEDULE_PLANNED_FINISH"


@dataclass(frozen=True)
class DatedSource:
    """A calendar date together with the evidence that supports it.

    ``value`` is None when the source exists but its date could not be assessed
    (``reason`` says why); the comparison is then NOT_ASSESSED, never a finding.
    ``locator`` is the clause id (contract) or the source row locator (schedule).
    """

    kind: str
    value: str | None = None  # ISO calendar date
    document_id: str | None = None
    revision_id: str | None = None
    locator: str | None = None
    reason: str | None = None  # why value is None (NOT_ASSESSED)


@dataclass(frozen=True)
class ProjectCrossDocInputs:
    """Cross-document numeric aggregates (each None when its source doc is missing)."""

    contract_total: float | None = None  # contractual price (from the contract)
    budget_total: float | None = None  # stated total (from the budget)
    budget_leaf_sum: float | None = None  # sum of budget line items
    wbs_total: float | None = None  # sum of WBS work-package costs
    bom_total: float | None = None  # sum of BOM line costs
    contingency: float | None = None  # contingency / reserve fund
    max_risk_exposure: float | None = None  # largest identified risk value (from risk analysis)
    # Calibration-corpus inputs: bare ISO dates with NO document/revision/source identity.
    # Production assembly never fills them; use the sourced fields below instead.
    contract_deadline: str | None = None  # ISO date the contract requires completion by
    schedule_end: str | None = None  # ISO date the schedule actually ends
    # Sourced dates: the contractual completion deadline and the schedule's planned finish.
    contract_completion: DatedSource | None = None
    schedule_finish: DatedSource | None = None
    currency: str | None = None  # first denomination seen (informational)
    # Normalized ISO codes seen with each side's money. Comparing totals across
    # different (or mixed) denominations is NOT_ASSESSED: there is no FX basis.
    contract_currencies: frozenset[str] = frozenset()
    budget_currencies: frozenset[str] = frozenset()


__all__ = [
    "DATE_KIND_CONTRACT_COMPLETION",
    "DATE_KIND_SCHEDULE_FINISH",
    "DatedSource",
    "ProjectCrossDocInputs",
]
