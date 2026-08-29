"""TS-UA-HEALTH-024-L4-2 — wire single-document analysis output into the L4-1 coverage contract.

Maps extracted ``Clause`` evidence + intrinsic ``FindingSignal`` findings for ONE document
into per-category assessments: ``{state, evidence, findings, missing_data, gap}`` over the six
canonical categories, plus the preserved cross-dimensional ``CROSS`` findings. The
qualifying-evidence decision is owned here and is threshold-gated by the deterministic
``CategoryRouter`` (never "a clause exists"); relational Coherence is out of scope for a
single document (no ``coherence_subscore``, no numeric Health score).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from src.coherence.category_registry import CanonicalCategory
from src.coherence.domain.category_weights import CoherenceCategory
from src.coherence.models import Clause, FindingSignal
from src.health.application.single_document_coverage import (
    CategoryAssessment,
    SingleDocumentCoverage,
    assess_single_document_coverage,
)
from src.health.domain.category_coverage import CategoryCoverageState, CategoryGapAlert

Qualifier = Callable[[str], set[CanonicalCategory]]
ALL = tuple(CoherenceCategory)


def _stub(mapping: dict[str, set[CanonicalCategory]]) -> Qualifier:
    def qualify(text: str) -> set[CanonicalCategory]:
        return set(mapping.get(text, set()))

    return qualify


def _by_cat(result: SingleDocumentCoverage, category: CoherenceCategory) -> CategoryAssessment:
    return next(a for a in result.assessments if a.category == category)


def _cross(rule_id: str = "CROSS-BUDGET-SCOPE", clause_id: str = "c1|c2") -> FindingSignal:
    """A CROSS finding as the real producers emit it: composite clause_id spanning two clauses."""
    return FindingSignal(rule_id=rule_id, clause_id=clause_id, impact_score=0.5, category="CROSS")


# =====================================================================================
# Coverage shape
# =====================================================================================


def test_covers_all_six_categories() -> None:
    result = assess_single_document_coverage([], [], qualifier=_stub({}))
    assert len(result.assessments) == 6
    assert {a.category for a in result.assessments} == set(ALL)


def test_qualifying_clause_reaches_its_category_as_present() -> None:
    clauses = [Clause(id="c1", text="budget text"), Clause(id="c2", text="scope text")]
    qualifier = _stub({"budget text": {CanonicalCategory.BUDGET}, "scope text": {CanonicalCategory.SCOPE}})
    result = assess_single_document_coverage(clauses, [], qualifier=qualifier)

    budget = _by_cat(result, CoherenceCategory.BUDGET)
    assert budget.state is CategoryCoverageState.PRESENT
    assert budget.evidence_count == 1
    assert budget.evidence_clause_ids == ("c1",)
    assert budget.gap is None
    assert budget.missing_data == ()


def test_absent_category_is_insufficient_with_factual_missing_data_and_gap() -> None:
    clauses = [Clause(id="c1", text="budget text")]
    result = assess_single_document_coverage(
        clauses, [], qualifier=_stub({"budget text": {CanonicalCategory.BUDGET}})
    )
    technical = _by_cat(result, CoherenceCategory.TECHNICAL)
    assert technical.state is CategoryCoverageState.INSUFFICIENT_EVIDENCE
    assert technical.evidence_count == 0
    assert technical.evidence_clause_ids == ()
    # factual missing_data (not an instruction) ...
    assert technical.missing_data and "Upload" not in technical.missing_data[0]
    # ... and a separate actionable gap, owned by this same category
    assert technical.gap is not None
    assert technical.gap.action.startswith("Upload")
    assert technical.gap.category is CoherenceCategory.TECHNICAL


def test_schedule_canonical_category_maps_to_time() -> None:
    clauses = [Clause(id="c1", text="schedule text")]
    result = assess_single_document_coverage(
        clauses, [], qualifier=_stub({"schedule text": {CanonicalCategory.SCHEDULE}})
    )
    time = _by_cat(result, CoherenceCategory.TIME)
    assert time.state is CategoryCoverageState.PRESENT
    assert time.evidence_clause_ids == ("c1",)


def test_non_qualifying_clauses_do_not_fabricate_coverage() -> None:
    # Clauses the classifier does not qualify for any category (and an empty-text clause)
    # must never produce PRESENT coverage.
    clauses = [Clause(id="c1", text="noise"), Clause(id="c2", text="")]
    result = assess_single_document_coverage(clauses, [], qualifier=_stub({}))
    assert all(a.state is CategoryCoverageState.INSUFFICIENT_EVIDENCE for a in result.assessments)
    assert all(a.evidence_count == 0 for a in result.assessments)


def test_empty_document_yields_six_insufficient_and_six_gaps() -> None:
    result = assess_single_document_coverage([], [], qualifier=_stub({}))
    assert all(a.state is CategoryCoverageState.INSUFFICIENT_EVIDENCE for a in result.assessments)
    assert sum(a.gap is not None for a in result.assessments) == 6


def test_single_document_emits_no_relational_coherence_or_score() -> None:
    result = assess_single_document_coverage(
        [Clause(id="c1", text="budget text")], [], qualifier=_stub({"budget text": {CanonicalCategory.BUDGET}})
    )
    # No numeric Health score and no relational coherence subscore in the single-doc path.
    assert not hasattr(result, "score")
    assert not hasattr(result, "coherence_subscore")
    for assessment in result.assessments:
        assert not hasattr(assessment, "score")
        assert not hasattr(assessment, "coherence_subscore")


def test_clause_qualifying_multiple_categories_counts_in_each() -> None:
    clauses = [Clause(id="c1", text="budget and schedule")]
    result = assess_single_document_coverage(
        clauses,
        [],
        qualifier=_stub({"budget and schedule": {CanonicalCategory.BUDGET, CanonicalCategory.SCHEDULE}}),
    )
    assert _by_cat(result, CoherenceCategory.BUDGET).evidence_clause_ids == ("c1",)
    assert _by_cat(result, CoherenceCategory.TIME).evidence_clause_ids == ("c1",)


def test_all_present_yields_zero_gaps() -> None:
    canonicals: list[CanonicalCategory] = list(CanonicalCategory)
    clauses = [Clause(id=f"c{i}", text=f"t{i}") for i in range(len(canonicals))]
    mapping: dict[str, set[CanonicalCategory]] = {f"t{i}": {canonicals[i]} for i in range(len(canonicals))}
    result = assess_single_document_coverage(clauses, [], qualifier=_stub(mapping))
    assert all(a.state is CategoryCoverageState.PRESENT for a in result.assessments)
    assert all(a.gap is None for a in result.assessments)


# =====================================================================================
# A — CROSS is PRESERVED, never discarded, never fabricated onto a canonical category
# =====================================================================================


def test_findings_are_attached_to_their_own_category_only() -> None:
    findings = [
        FindingSignal(rule_id="R1", clause_id="c1", impact_score=0.4, category="BUDGET"),
        FindingSignal(rule_id="R2", clause_id="c2", impact_score=0.6, category="LEGAL"),
    ]
    clauses = [Clause(id="c1", text="budget text")]
    result = assess_single_document_coverage(
        clauses, findings, qualifier=_stub({"budget text": {CanonicalCategory.BUDGET}})
    )
    assert [f.rule_id for f in _by_cat(result, CoherenceCategory.BUDGET).findings] == ["R1"]
    assert [f.rule_id for f in _by_cat(result, CoherenceCategory.LEGAL).findings] == ["R2"]
    assert _by_cat(result, CoherenceCategory.TECHNICAL).findings == ()


def test_cross_findings_are_preserved_and_not_attached_to_any_category() -> None:
    # Producer audit: CROSS-BUDGET-SCOPE (BUDGET x SCOPE) and CROSS-SCHEDULE-DELIVERY
    # (TIME x TECHNICAL) are cross-dimensional and CAN occur inside ONE document, so they
    # must be preserved — not skipped — while never being attributed to a single category.
    findings = [_cross("CROSS-BUDGET-SCOPE", "c1|c2"), _cross("CROSS-SCHEDULE-DELIVERY", "c3|c4")]
    result = assess_single_document_coverage([], findings, qualifier=_stub({}))

    assert all(a.findings == () for a in result.assessments)
    assert [f.rule_id for f in result.cross_findings] == [
        "CROSS-BUDGET-SCOPE",
        "CROSS-SCHEDULE-DELIVERY",
    ]


def test_cross_findings_are_preserved_verbatim_with_composite_clause_id() -> None:
    # The composite clause_id ("<a>|<b>") is exactly why a CROSS finding has no single
    # canonical home — it must survive the mapping untouched for L4-3.
    finding = _cross("CROSS-BUDGET-SCOPE", "budget-7|scope-3")
    result = assess_single_document_coverage([], [finding], qualifier=_stub({}))

    assert len(result.cross_findings) == 1
    preserved = result.cross_findings[0]
    assert preserved == finding
    assert preserved.clause_id == "budget-7|scope-3"
    assert preserved.category == "CROSS"


def test_cross_and_canonical_findings_are_partitioned_not_merged() -> None:
    findings = [
        FindingSignal(rule_id="R1", clause_id="c1", impact_score=0.4, category="BUDGET"),
        _cross("CROSS-BUDGET-SCOPE", "c1|c2"),
    ]
    result = assess_single_document_coverage([], findings, qualifier=_stub({}))

    assert [f.rule_id for f in _by_cat(result, CoherenceCategory.BUDGET).findings] == ["R1"]
    assert [f.rule_id for f in result.cross_findings] == ["CROSS-BUDGET-SCOPE"]
    # The CROSS finding is counted once, in exactly one place.
    attached = sum(len(a.findings) for a in result.assessments)
    assert attached + len(result.cross_findings) == len(findings)


def test_cross_findings_default_empty_when_document_has_none() -> None:
    result = assess_single_document_coverage([], [], qualifier=_stub({}))
    assert result.cross_findings == ()


def test_cross_findings_never_contribute_evidence() -> None:
    # A CROSS finding is an issue, not supporting evidence — it must not create coverage.
    result = assess_single_document_coverage([], [_cross()], qualifier=_stub({}))
    assert all(a.state is CategoryCoverageState.INSUFFICIENT_EVIDENCE for a in result.assessments)
    assert all(a.evidence_count == 0 for a in result.assessments)


def test_cross_findings_bucket_rejects_a_non_cross_finding() -> None:
    canonical = FindingSignal(rule_id="R1", clause_id="c1", impact_score=0.4, category="BUDGET")
    with pytest.raises(ValidationError, match="only CROSS-category findings"):
        SingleDocumentCoverage(
            assessments=assess_single_document_coverage([], [], qualifier=_stub({})).assessments,
            cross_findings=(canonical,),
        )


# =====================================================================================
# B — CategoryAssessment invariants (negative tests)
# =====================================================================================


def _insufficient_kwargs(category: CoherenceCategory = CoherenceCategory.BUDGET) -> dict[str, object]:
    return {
        "category": category,
        "state": CategoryCoverageState.INSUFFICIENT_EVIDENCE,
        "missing_data": ("budget / bill of quantities (BoQ) not detected",),
        "gap": CategoryGapAlert(category=category, action="Upload the budget to assess BUDGET."),
    }


def test_duplicate_evidence_clause_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="must not repeat a clause id"):
        CategoryAssessment(
            category=CoherenceCategory.BUDGET,
            state=CategoryCoverageState.PRESENT,
            evidence_count=2,
            evidence_clause_ids=("c1", "c1"),
        )


def test_evidence_count_must_equal_distinct_evidence_clause_ids() -> None:
    with pytest.raises(ValidationError, match="evidence_count must equal"):
        CategoryAssessment(
            category=CoherenceCategory.BUDGET,
            state=CategoryCoverageState.PRESENT,
            evidence_count=3,
            evidence_clause_ids=("c1", "c2"),
        )


def test_evidence_count_may_not_overstate_a_single_clause() -> None:
    with pytest.raises(ValidationError, match="evidence_count must equal"):
        CategoryAssessment(
            category=CoherenceCategory.BUDGET,
            state=CategoryCoverageState.PRESENT,
            evidence_count=1,
            evidence_clause_ids=(),
        )


def test_gap_category_must_match_the_assessment_category() -> None:
    kwargs = _insufficient_kwargs(CoherenceCategory.BUDGET)
    kwargs["gap"] = CategoryGapAlert(
        category=CoherenceCategory.LEGAL, action="Upload the legal terms to assess LEGAL."
    )
    with pytest.raises(ValidationError, match="gap alert category must match"):
        CategoryAssessment(**kwargs)  # type: ignore[arg-type]


def test_matching_gap_category_is_accepted() -> None:
    assessment = CategoryAssessment(**_insufficient_kwargs(CoherenceCategory.BUDGET))  # type: ignore[arg-type]
    assert assessment.gap is not None
    assert assessment.gap.category is assessment.category


def test_repeated_clause_id_never_inflates_evidence_count() -> None:
    # The same clause id qualifying twice for one category is counted ONCE — double
    # counting would overstate coverage strength (INV-1).
    clauses = [Clause(id="c1", text="budget text"), Clause(id="c1", text="budget text")]
    result = assess_single_document_coverage(
        clauses, [], qualifier=_stub({"budget text": {CanonicalCategory.BUDGET}})
    )
    budget = _by_cat(result, CoherenceCategory.BUDGET)
    assert budget.evidence_clause_ids == ("c1",)
    assert budget.evidence_count == 1


def test_every_produced_assessment_satisfies_the_count_invariant() -> None:
    clauses = [Clause(id="c1", text="budget text"), Clause(id="c2", text="budget text")]
    result = assess_single_document_coverage(
        clauses, [], qualifier=_stub({"budget text": {CanonicalCategory.BUDGET}})
    )
    for assessment in result.assessments:
        assert assessment.evidence_count == len(set(assessment.evidence_clause_ids))
        if assessment.gap is not None:
            assert assessment.gap.category is assessment.category


def test_assessments_must_cover_exactly_the_six_categories() -> None:
    only_one = assess_single_document_coverage([], [], qualifier=_stub({})).assessments[:1]
    with pytest.raises(ValidationError, match="exactly one entry per canonical category"):
        SingleDocumentCoverage(assessments=only_one)


# =====================================================================================
# C — real CategoryRouter boundary (thresholds and INV-1 unchanged)
# =====================================================================================

# Substantive, prior-free clause text per canonical category. Each clears the registry
# ``insufficient_evidence`` threshold (0.20) on Capa-1 structural + lexicon signal ALONE,
# with doc_type="" — no prior, no threshold change, no lexicon change.
_REAL_ROUTER_CASES: list[tuple[CanonicalCategory, CoherenceCategory, str]] = [
    (
        CanonicalCategory.SCOPE,
        CoherenceCategory.SCOPE,
        "Scope of work and deliverables: this SOW defines the battery limits, "
        "interfaces and exclusions of the supply.",
    ),
    (
        CanonicalCategory.BUDGET,
        CoherenceCategory.BUDGET,
        "Payment terms and price: the budget and bill of quantities (BoQ) set the "
        "unit rates; invoicing of 1.500,00 EUR applies.",
    ),
    (
        CanonicalCategory.SCHEDULE,
        CoherenceCategory.TIME,
        "Project schedule and milestones: the programme baseline sets the completion "
        "timeline with a Gantt chart and a 30 days deadline.",
    ),
    (
        CanonicalCategory.TECHNICAL,
        CoherenceCategory.TECHNICAL,
        "Technical specifications and design basis: the drawings, datasheets and "
        "standards IEC 61850 govern commissioning of the 400 kV equipment.",
    ),
    (
        CanonicalCategory.LEGAL,
        CoherenceCategory.LEGAL,
        "Clause 14 - Termination, liability and indemnification: governing law, "
        "arbitration, force majeure, confidentiality and insurance apply under this contract.",
    ),
    (
        CanonicalCategory.QUALITY,
        CoherenceCategory.QUALITY,
        "Quality plan and quality control: the ITP defines inspection, test plan, FAT "
        "and SAT acceptance, non-conformity handling and defects liability under ISO 9001.",
    ),
]


@pytest.mark.parametrize(
    ("canonical", "expected", "text"),
    _REAL_ROUTER_CASES,
    ids=[case[0].value for case in _REAL_ROUTER_CASES],
)
def test_real_router_finds_substantive_evidence_for_each_category(
    canonical: CanonicalCategory, expected: CoherenceCategory, text: str
) -> None:
    # Uses the DEFAULT (real CategoryRouter) qualifier — no stub, no doc_type prior.
    result = assess_single_document_coverage([Clause(id="c1", text=text)], [])
    assessment = _by_cat(result, expected)
    assert assessment.state is CategoryCoverageState.PRESENT
    assert assessment.evidence_clause_ids == ("c1",)
    assert assessment.evidence_count == 1
    assert assessment.gap is None


def test_real_router_noise_clause_qualifies_no_category() -> None:
    # Negative boundary: text with no category signal must stay INSUFFICIENT everywhere.
    text = "The weather was pleasant and the team gathered for lunch near the river."
    result = assess_single_document_coverage([Clause(id="c1", text=text)], [])
    assert all(a.state is CategoryCoverageState.INSUFFICIENT_EVIDENCE for a in result.assessments)
    assert all(a.evidence_count == 0 for a in result.assessments)


def test_default_real_router_runs_and_is_prior_free() -> None:
    # Smoke: the default (real CategoryRouter) qualifier runs end-to-end. An empty-text
    # clause must not fabricate any coverage (prior-free, in-document evidence only).
    result = assess_single_document_coverage([Clause(id="c1", text="   ")], [])
    assert all(a.state is CategoryCoverageState.INSUFFICIENT_EVIDENCE for a in result.assessments)


def test_default_real_router_classifies_a_strong_budget_clause() -> None:
    # A clause with strong, unambiguous budget signal should qualify BUDGET via the real router.
    text = (
        "Budget and cost breakdown: the total contract budget is USD 1,500,000. "
        "Payment shall be made per the cost schedule; the price includes all costs."
    )
    result = assess_single_document_coverage([Clause(id="c1", text=text)], [])
    assert _by_cat(result, CoherenceCategory.BUDGET).state is CategoryCoverageState.PRESENT
