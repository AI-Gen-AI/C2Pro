"""TS-UA-HEALTH-024-R1-C — the real ingestion splitter → adapter → real router boundary.

R1's whole premise is that ingestion already segments contracts well enough to serve as
evidence. That premise is only worth anything if it is checked against the **real**
splitter and the **real** prior-free ``CategoryRouter``, on realistic contract prose,
in CI — not against hand-built clause lists.

This is a deterministic boundary regression over the pinned canonical fixture
(:mod:`tests.fixtures.canonical_contract`). It asserts the structural guarantees R1
owns and deliberately does **not** demand six-of-six categories: see that module for the
measured explanation of the earlier 6-of-6 probe versus the 5-of-6 seen on realistic
prose. No threshold or lexicon is tuned to make anything here pass.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from src.analysis.application.clause_evidence import to_coherence_clauses
from src.health.application.single_document_coverage import assess_single_document_coverage
from src.health.domain.category_coverage import CategoryCoverageState
from tests.fixtures.canonical_contract import (
    BOILERPLATE_ONLY_CONTRACT,
    CANONICAL_EPC_CONTRACT,
)

PROJECT_ID = UUID("22222222-2222-2222-2222-222222222222")
TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")


def _split(parsed_text: str, document_id: UUID | None = None):
    """Run the real deterministic ingestion splitter — no test double."""
    from src.core.tasks.ingestion_tasks import _extract_contract_clauses

    return _extract_contract_clauses(
        document_id=document_id or uuid4(),
        project_id=PROJECT_ID,
        tenant_id=TENANT_ID,
        parsed_text=parsed_text,
    )


class TestRealSplitterBoundary:
    def test_the_real_splitter_yields_more_than_one_clause(self) -> None:
        """The premise R1 rests on: ingestion really does segment a contract."""
        persisted = _split(CANONICAL_EPC_CONTRACT)

        assert len(persisted) > 1
        assert all((clause.full_text or "").strip() for clause in persisted)

    def test_clause_identities_are_distinct_and_stable_through_the_adapter(self) -> None:
        persisted = _split(CANONICAL_EPC_CONTRACT)

        clauses = to_coherence_clauses(persisted, doc_type="contract")

        assert len(clauses) == len(persisted)
        assert len({c.id for c in clauses}) == len(clauses)
        # Identity is the persisted UUID, and the adapter neither renames nor reorders.
        assert [c.id for c in clauses] == [str(p.id) for p in persisted]
        assert [UUID(c.id) for c in clauses] == [p.id for p in persisted]

    def test_the_real_router_finds_multiple_legitimate_categories(self) -> None:
        """Several distinct categories, each backed by its own clause — not one blob."""
        clauses = to_coherence_clauses(_split(CANONICAL_EPC_CONTRACT), doc_type="contract")

        coverage = assess_single_document_coverage(clauses, [])

        evidenced = {a.category.value for a in coverage.assessments if a.evidence_count > 0}
        assert len(evidenced) >= 3, f"granular evidence collapsed to {evidenced}"

        evidence_ids = {
            clause_id for a in coverage.assessments for clause_id in a.evidence_clause_ids
        }
        # Distinct clauses carry the evidence; a single id backing everything would mean
        # the whole-document blob is back.
        assert len(evidence_ids) >= 3

    def test_every_evidence_id_is_a_real_persisted_clause(self) -> None:
        persisted = _split(CANONICAL_EPC_CONTRACT)
        clauses = to_coherence_clauses(persisted, doc_type="contract")

        coverage = assess_single_document_coverage(clauses, [])

        known = {str(p.id) for p in persisted}
        for assessment in coverage.assessments:
            assert set(assessment.evidence_clause_ids) <= known

    def test_boilerplate_does_not_fabricate_coverage(self) -> None:
        """Segmenting noise must not manufacture green (INV-1)."""
        clauses = to_coherence_clauses(_split(BOILERPLATE_ONLY_CONTRACT), doc_type="contract")

        coverage = assess_single_document_coverage(clauses, [])

        assert all(
            assessment.state is CategoryCoverageState.INSUFFICIENT_EVIDENCE
            for assessment in coverage.assessments
        )
        assert all(assessment.evidence_count == 0 for assessment in coverage.assessments)

    def test_the_boundary_is_deterministic_on_replay(self) -> None:
        """Same text twice ⇒ same segmentation, same order, same coverage shape.

        Clause ids are generated per split (ingestion assigns them once and persists
        them), so replay determinism is asserted over the clause *texts*, codes and the
        resulting coverage — the parts that must not drift between runs.
        """
        first = _split(CANONICAL_EPC_CONTRACT)
        second = _split(CANONICAL_EPC_CONTRACT)

        assert [c.clause_code for c in first] == [c.clause_code for c in second]
        assert [c.full_text for c in first] == [c.full_text for c in second]

        def shape(persisted):
            coverage = assess_single_document_coverage(
                to_coherence_clauses(persisted, doc_type="contract"), []
            )
            return [(a.category.value, a.state.value, a.evidence_count) for a in coverage.assessments]

        assert shape(first) == shape(second)

    def test_persisted_ids_are_assigned_once_not_per_read(self) -> None:
        """Evidence identity comes from persistence, so re-adapting the same rows is stable."""
        persisted = _split(CANONICAL_EPC_CONTRACT)

        first = to_coherence_clauses(persisted, doc_type="contract")
        second = to_coherence_clauses(persisted, doc_type="contract")

        assert [c.id for c in first] == [c.id for c in second]


class TestSixOfSixDiscrepancy:
    def test_crafted_single_category_text_clears_the_threshold(self) -> None:
        """The 6-of-6 side of the discrepancy: dense crafted prose does qualify."""
        from src.coherence.application.services.category_router import (
            CategoryRouter,
            ChunkSignal,
        )

        crafted = (
            "Quality plan and quality control: the ITP defines inspection, test plan, FAT "
            "and SAT acceptance, non-conformity handling and defects liability under ISO 9001."
        )
        result = CategoryRouter.from_registry().route(
            [ChunkSignal(chunk_id="c", text=crafted)], doc_type="", segments=[]
        )

        evidenced = {c.value for c, s in result.category_status.items() if s == "has_evidence"}
        assert "QUALITY" in evidenced

    def test_realistic_quality_prose_does_not_and_that_is_not_a_regression(self) -> None:
        """The 5-of-6 side: the same category in natural contract prose stays below it.

        Pinned so a future threshold or lexicon change is a deliberate, visible decision
        rather than something that silently reclassifies this fixture.
        """
        from src.coherence.application.services.category_router import (
            CategoryRouter,
            ChunkSignal,
        )

        persisted = _split(CANONICAL_EPC_CONTRACT)
        quality_clause = next(
            c for c in persisted if "QUALITY ASSURANCE" in (c.full_text or "")
        )
        result = CategoryRouter.from_registry().route(
            [ChunkSignal(chunk_id="c", text=quality_clause.full_text or "")],
            doc_type="",
            segments=[],
        )

        evidenced = {c.value for c, s in result.category_status.items() if s == "has_evidence"}
        assert "QUALITY" not in evidenced
