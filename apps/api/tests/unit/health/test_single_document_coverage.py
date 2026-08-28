"""TS-UA-HEALTH-024-L4-2 — wire single-document analysis output into the L4-1 coverage contract.

Maps extracted ``Clause`` evidence + intrinsic ``FindingSignal`` findings for ONE document
into per-category assessments: ``{state, evidence, findings, missing_data, gap}`` over the six
canonical categories. The qualifying-evidence decision is owned here and is threshold-gated by
the deterministic ``CategoryRouter`` (never "a clause exists"); relational Coherence is out of
scope for a single document (no ``coherence_subscore``, no numeric Health score).
"""

from __future__ import annotations

from collections.abc import Callable

from src.coherence.category_registry import CanonicalCategory
from src.coherence.domain.category_weights import CoherenceCategory
from src.coherence.models import Clause, FindingSignal
from src.health.application.single_document_coverage import (
    CategoryAssessment,
    assess_single_document_coverage,
)
from src.health.domain.category_coverage import CategoryCoverageState

Qualifier = Callable[[str], set[CanonicalCategory]]
ALL = tuple(CoherenceCategory)


def _stub(mapping: dict[str, set[CanonicalCategory]]) -> Qualifier:
    def qualify(text: str) -> set[CanonicalCategory]:
        return set(mapping.get(text, set()))

    return qualify


def _by_cat(assessments: tuple[CategoryAssessment, ...], category: CoherenceCategory) -> CategoryAssessment:
    return next(a for a in assessments if a.category == category)


def test_covers_all_six_categories() -> None:
    result = assess_single_document_coverage([], [], qualifier=_stub({}))
    assert len(result) == 6
    assert {a.category for a in result} == set(ALL)


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
    # ... and a separate actionable gap
    assert technical.gap is not None
    assert technical.gap.action.startswith("Upload")


def test_schedule_canonical_category_maps_to_time() -> None:
    clauses = [Clause(id="c1", text="schedule text")]
    result = assess_single_document_coverage(
        clauses, [], qualifier=_stub({"schedule text": {CanonicalCategory.SCHEDULE}})
    )
    time = _by_cat(result, CoherenceCategory.TIME)
    assert time.state is CategoryCoverageState.PRESENT
    assert time.evidence_clause_ids == ("c1",)


def test_findings_are_attached_to_their_own_category_only() -> None:
    findings = [
        FindingSignal(rule_id="R1", clause_id="c1", impact_score=0.4, category="BUDGET"),
        FindingSignal(rule_id="R2", clause_id="c2", impact_score=0.6, category="LEGAL"),
    ]
    clauses = [Clause(id="c1", text="budget text")]
    result = assess_single_document_coverage(
        clauses, findings, qualifier=_stub({"budget text": {CanonicalCategory.BUDGET}})
    )
    budget = _by_cat(result, CoherenceCategory.BUDGET)
    legal = _by_cat(result, CoherenceCategory.LEGAL)
    technical = _by_cat(result, CoherenceCategory.TECHNICAL)
    assert [f.rule_id for f in budget.findings] == ["R1"]
    assert [f.rule_id for f in legal.findings] == ["R2"]
    assert technical.findings == ()


def test_cross_category_findings_are_not_attached_to_any_single_category() -> None:
    # A CROSS finding is relational (>=2-doc) — it has no single-document category home.
    findings = [FindingSignal(rule_id="X", clause_id="c1", impact_score=0.5, category="CROSS")]
    result = assess_single_document_coverage([], findings, qualifier=_stub({}))
    assert all(a.findings == () for a in result)


def test_non_qualifying_clauses_do_not_fabricate_coverage() -> None:
    # Clauses the classifier does not qualify for any category (and an empty-text clause)
    # must never produce PRESENT coverage.
    clauses = [Clause(id="c1", text="noise"), Clause(id="c2", text="")]
    result = assess_single_document_coverage(clauses, [], qualifier=_stub({}))
    assert all(a.state is CategoryCoverageState.INSUFFICIENT_EVIDENCE for a in result)
    assert all(a.evidence_count == 0 for a in result)


def test_empty_document_yields_six_insufficient_and_six_gaps() -> None:
    result = assess_single_document_coverage([], [], qualifier=_stub({}))
    assert all(a.state is CategoryCoverageState.INSUFFICIENT_EVIDENCE for a in result)
    assert sum(a.gap is not None for a in result) == 6


def test_single_document_emits_no_relational_coherence_or_score() -> None:
    result = assess_single_document_coverage(
        [Clause(id="c1", text="budget text")], [], qualifier=_stub({"budget text": {CanonicalCategory.BUDGET}})
    )
    for assessment in result:
        # No numeric Health score and no relational coherence subscore in the single-doc path.
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
    assert all(a.state is CategoryCoverageState.PRESENT for a in result)
    assert all(a.gap is None for a in result)


def test_default_real_router_runs_and_is_prior_free() -> None:
    # Smoke: the default (real CategoryRouter) qualifier runs end-to-end. An empty-text
    # clause must not fabricate any coverage (prior-free, in-document evidence only).
    result = assess_single_document_coverage([Clause(id="c1", text="   ")], [])
    assert all(a.state is CategoryCoverageState.INSUFFICIENT_EVIDENCE for a in result)


def test_default_real_router_classifies_a_strong_budget_clause() -> None:
    # A clause with strong, unambiguous budget signal should qualify BUDGET via the real router.
    text = (
        "Budget and cost breakdown: the total contract budget is USD 1,500,000. "
        "Payment shall be made per the cost schedule; the price includes all costs."
    )
    result = assess_single_document_coverage([Clause(id="c1", text=text)], [])
    assert _by_cat(result, CoherenceCategory.BUDGET).state is CategoryCoverageState.PRESENT
