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

from collections.abc import Collection

from src.analysis.domain.budget_row_evidence import (
    BudgetAssessmentState,
    BudgetRowEvidence,
    assess_budget_comparability,
)

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


def structured_budget_assessment_from_rows(
    rows: Collection[BudgetRowEvidence],
) -> tuple[dict[str, bool], dict[str, str]]:
    """Keep coherence fail-closed while revision-bound rows await comparison.

    Structured source evidence is necessary but cannot itself approve a budget
    result.  In particular, a group of semantically compatible rows is only
    ready for a later comparison against an independently approved contractual
    baseline; it is never a zero variance or a passing score.
    """
    comparability = assess_budget_comparability(rows)
    reason = comparability.reason
    if comparability.state is BudgetAssessmentState.READY_FOR_COMPARISON:
        reason = "approved_budget_comparison_missing"
    return {"BUDGET": False}, {"BUDGET": reason or STRUCTURED_BUDGET_SOURCE_UNAVAILABLE}


__all__ = [
    "BUDGET_LINE_RULE_IDS",
    "STRUCTURED_BUDGET_SOURCE_UNAVAILABLE",
    "structured_budget_assessment",
    "structured_budget_assessment_from_rows",
]
