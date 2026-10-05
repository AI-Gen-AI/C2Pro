"""#860: availability of structured budget-line evidence for coherence.

A budget LINE is not a canonical BOM ITEM. The procurement BOM table is a mixed
legacy object (manual procurement BOM, historical budget-derived rows, procurement
edits), so it is never budget truth; and a budget document's ``stated_total`` is a
total, not a line set. Until a revision-bound Budget / Cost model exists there is
NO authoritative structured budget-line source, so the rules that need one
(DET-BUD-LINEITEM / SUM / INTERNAL) cannot be assessed.

This is the evaluation-assembly policy: it is applied where the evaluation inputs
are assembled (the budget clause builder and the v2 shadow inputs), never inside
the generic per-category scorer.
"""

from __future__ import annotations

STRUCTURED_BUDGET_SOURCE_UNAVAILABLE = "structured_budget_source_unavailable"

# Rules whose required input is an authoritative structured budget LINE set.
BUDGET_LINE_RULE_IDS: tuple[str, ...] = (
    "DET-BUD-LINEITEM",
    "DET-BUD-SUM",
    "DET-BUD-INTERNAL",
)


def structured_budget_assessment() -> tuple[dict[str, bool], dict[str, str]]:
    """Generic v2 assessment inputs: BUDGET is applicable but not assessable.

    Returns ``(assessment_by_category, assessment_reason_by_category)``.
    """
    return {"BUDGET": False}, {"BUDGET": STRUCTURED_BUDGET_SOURCE_UNAVAILABLE}


__all__ = [
    "BUDGET_LINE_RULE_IDS",
    "STRUCTURED_BUDGET_SOURCE_UNAVAILABLE",
    "structured_budget_assessment",
]
