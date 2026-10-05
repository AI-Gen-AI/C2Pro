"""#860 -- structured budget LINE assessment is UNAVAILABLE, never clean-by-absence.

TS-UT-860-BUDGET-LINE-UNAVAILABLE-001. Until a revision-bound Budget / Cost model
exists there is no authoritative structured budget-line source: the BOM table is a
mixed legacy object, not budget truth, and a budget document's ``stated_total`` is
a total, not a line set. So DET-BUD-LINEITEM / SUM / INTERNAL cannot be assessed.

The decision lives UPSTREAM (the evaluation-assembly boundary decides what was
assessable); ``CategoryAggregator`` stays generic -- it only learns ``assessed`` and
an optional ``assessment_reason``, for any category:

* BUDGET stays APPLICABLE but is UNASSESSED (INSUFFICIENT_EVIDENCE, score None) --
  never SCORED=100 because a budget document / BOM rows exist;
* the reason ``structured_budget_source_unavailable`` reaches the read model;
* findings of independent budget rules are preserved, never upgraded to "clean";
* ``budget_reconciliation`` is never synthesised without structured lines.
"""

from __future__ import annotations

import ast
import inspect
from uuid import uuid4

import pytest

from src.coherence.application.dtos.coherence_v2_dtos import CategoryStatus
from src.coherence.domain.budget_line_availability import (
    BUDGET_LINE_RULE_IDS,
    STRUCTURED_BUDGET_SOURCE_UNAVAILABLE,
    structured_budget_assessment,
)
from src.coherence.domain.v2_constants import MIN_EVIDENCE_BY_CATEGORY
from src.coherence.models import FindingSignal
from src.coherence.scoring import calculate_v2_from_signals
from src.coherence.services.v2 import category_aggregator as category_aggregator_module
from src.coherence.services.v2.category_aggregator import CategoryAggregator
from src.coherence.services.v2.conflict_service import ConflictReport
from src.coherence.services.v2.evidence_service import EvidenceBundle

REASON = "structured_budget_source_unavailable"


def _bundle(count: int) -> EvidenceBundle:
    return EvidenceBundle(
        count=count,
        evidence_coverage=0.8 if count else 0.0,
        evidence_freshness=1.0 if count else 0.0,
        avg_technical_reliability=1.0 if count else 0.0,
        missing_required=[],
        references=[f"ref-{i}" for i in range(count)],
    )


def _no_conflict() -> ConflictReport:
    return ConflictReport(severity="none", hard_conflict=False)


def _v2(signals: list[FindingSignal]):
    assessed, reasons = structured_budget_assessment()
    evidence = {cat: _bundle(0) for cat in MIN_EVIDENCE_BY_CATEGORY}
    evidence["BUDGET"] = _bundle(3)  # a budget document + manual BOM exist
    payload = calculate_v2_from_signals(
        signals=signals,
        evidence_bundles=evidence,
        applicability_map=dict.fromkeys(MIN_EVIDENCE_BY_CATEGORY, (True, None)),
        project_id=uuid4(),
        assessment_by_category=assessed,
        assessment_reason_by_category=reasons,
    )
    return next(c for c in payload.categories if c.category == "BUDGET")


def test_upstream_policy_marks_budget_unassessed_with_reason() -> None:
    assessed, reasons = structured_budget_assessment()
    assert assessed == {"BUDGET": False}
    assert reasons == {"BUDGET": REASON}
    assert STRUCTURED_BUDGET_SOURCE_UNAVAILABLE == REASON
    assert BUDGET_LINE_RULE_IDS == ("DET-BUD-LINEITEM", "DET-BUD-SUM", "DET-BUD-INTERNAL")


# A + D + E: a budget document and manual BOM are not a clean structured budget.
def test_budget_is_applicable_but_never_assessed_clean() -> None:
    budget = _v2([])
    assert budget.status is CategoryStatus.INSUFFICIENT_EVIDENCE
    assert budget.status is not CategoryStatus.NOT_APPLICABLE
    assert budget.coherence_score is None
    assert budget.rationale == REASON
    assert budget.calculation_metadata["assessment_state"] == "unassessed"
    assert budget.calculation_metadata["assessment_reason"] == REASON
    assert budget.budget_reconciliation is None


# 9: independent budget findings are preserved, but never make BUDGET "assessed".
def test_independent_budget_findings_are_preserved_not_upgraded() -> None:
    retention = FindingSignal(
        rule_id="DET-BUD-RETENTION", clause_id="contract-clause-3", source="deterministic",
        impact_score=0.5, category="BUDGET", raw_data={"retention_pct": 15.0},
    )
    budget = _v2([retention])
    assert budget.status is CategoryStatus.INSUFFICIENT_EVIDENCE
    assert budget.coherence_score is None
    assert budget.rationale == REASON
    assert budget.calculation_metadata["available_rule_signals"] == ["DET-BUD-RETENTION"]


def test_reconciliation_is_never_synthesised_without_structured_lines() -> None:
    contract_sum = FindingSignal(
        rule_id="DET-BUD-SUM", clause_id="contract-clause-7", source="deterministic",
        impact_score=0.6, category="BUDGET",
        raw_data={"items_sum": 110.0, "contract_total": 100.0, "deviation_pct": 10.0,
                  "direction": "exceeds"},
    )
    budget = _v2([contract_sum])
    assert budget.coherence_score is None
    assert budget.budget_reconciliation is None


# H: the aggregator stays generic -- the same contract works for ANY category.
@pytest.mark.parametrize("category", sorted(MIN_EVIDENCE_BY_CATEGORY))
def test_aggregator_assessment_reason_is_generic(category: str) -> None:
    out = CategoryAggregator().aggregate(
        category=category, evidence=_bundle(3), conflict=_no_conflict(),
        rule_signals=[("R-ANY", 40.0)], applicable=True,
        assessed=False, assessment_reason="some_source_unavailable",
    )
    assert out.status is CategoryStatus.INSUFFICIENT_EVIDENCE
    assert out.coherence_score is None
    assert out.rationale == "some_source_unavailable"
    assert out.calculation_metadata == {
        "assessment_state": "unassessed",
        "assessment_reason": "some_source_unavailable",
        "available_rule_signals": ["R-ANY"],
    }


def test_aggregator_has_no_category_specific_branch() -> None:
    tree = ast.parse(inspect.getsource(category_aggregator_module))
    literals = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not literals & set(MIN_EVIDENCE_BY_CATEGORY)
    assert REASON not in literals
    assert not literals & set(BUDGET_LINE_RULE_IDS)


def test_other_categories_keep_their_assessment() -> None:
    evidence = {cat: _bundle(3) for cat in MIN_EVIDENCE_BY_CATEGORY}
    assessed, reasons = structured_budget_assessment()
    payload = calculate_v2_from_signals(
        signals=[], evidence_bundles=evidence,
        applicability_map=dict.fromkeys(MIN_EVIDENCE_BY_CATEGORY, (True, None)),
        project_id=uuid4(), assessment_by_category=assessed,
        assessment_reason_by_category=reasons,
    )
    time = next(c for c in payload.categories if c.category == "TIME")
    assert time.status is CategoryStatus.SCORED
    assert time.calculation_metadata["assessment_state"] == "assessed_clean"
