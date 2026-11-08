"""ADR-024 isolated calibration: real clauses may meet direct source evidence
while the scoring router's reserved embedding weight keeps them below 0.20.

A Health PRESENT here means *source content exists*, never a Coherence score,
an approved risk or an N4/N12 fidelity verdict.
"""

from __future__ import annotations

from scripts.n4_n12_real_ai_eval import load_fixture
from src.coherence.application.services.category_router import CategoryRouter, ChunkSignal
from src.coherence.category_registry import CanonicalCategory
from src.coherence.domain.category_weights import CoherenceCategory
from src.coherence.models import Clause
from src.health.application.single_document_coverage import assess_single_document_coverage
from src.health.domain.category_coverage import CategoryCoverageState


def _coverage():
    fixture = load_fixture()  # nine versioned source clauses; SHA pinned by fixture loader
    clauses = [Clause(id=part["id"], text=part["text"]) for part in fixture["contract"]["clauses"]]
    return assess_single_document_coverage(clauses, [])


def test_rich_epc_contract_carries_exact_category_evidence_without_score() -> None:
    coverage = _coverage()
    by_cat = {a.category: a for a in coverage.assessments}
    for category in (CoherenceCategory.LEGAL, CoherenceCategory.BUDGET, CoherenceCategory.TIME):
        item = by_cat[category]
        assert item.state is CategoryCoverageState.PRESENT
        assert item.evidence_count >= 1
        assert all(clause_id.startswith("EPC-") for clause_id in item.evidence_clause_ids)
    for category in (
        CoherenceCategory.SCOPE,
        CoherenceCategory.TECHNICAL,
        CoherenceCategory.QUALITY,
    ):
        assert by_cat[category].state is CategoryCoverageState.INSUFFICIENT_EVIDENCE
    assert not hasattr(coverage, "score")


def test_health_recalibration_does_not_change_coherence_router_threshold() -> None:
    router = CategoryRouter.from_registry()
    clause = load_fixture()["contract"]["clauses"][1]["text"]
    result = router.route([ChunkSignal(chunk_id="EPC-02", text=clause)], doc_type="", segments=[])
    assert result.category_status[CanonicalCategory.BUDGET] == "insufficient_evidence"
    assert CanonicalCategory.BUDGET in router.clause_source_evidence_categories(clause)


def test_isolated_single_words_and_irrelevant_text_never_generate_presence() -> None:
    for sentence in (
        "",
        " ",
        "budget",
        "budget budget budget",
        "scope",
        "contract",
        "The conference starts on Friday; refreshments are available.",
        "Price list: miscellaneous ancillary supplies.",
    ):
        router = CategoryRouter.from_registry()
        assert not router.clause_source_evidence_categories(sentence), sentence
        coverage = assess_single_document_coverage([Clause(id="one", text=sentence)], [])
        assert all(a.evidence_count == 0 for a in coverage.assessments), sentence


def test_category_evidence_retains_document_clause_identity_and_no_fabricated_dimensions() -> None:
    fixture = load_fixture()
    clauses = [
        Clause(
            id="EPC-02",
            text=next(c["text"] for c in fixture["contract"]["clauses"] if c["id"] == "EPC-02"),
        ),
    ]
    coverage = assess_single_document_coverage(clauses, [])
    budget = next(a for a in coverage.assessments if a.category is CoherenceCategory.BUDGET)
    assert budget.evidence_clause_ids == ("EPC-02",)
    assert budget.evidence_count == 1
    assert all(
        a.evidence_count == 0
        for a in coverage.assessments
        if a.category is not CoherenceCategory.BUDGET
    )
