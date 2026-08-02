"""
Tests for EvidenceService — category-aware coverage + doc-type filtering.

Phase 1 deterministic increment (ADR-009 §2.2):
- Coverage = min(1.0, count / MIN_EVIDENCE_BY_CATEGORY[category])
- Only docs whose document_type matches COHERENCE_CATEGORY_TO_DOC_TYPES[category]
  are counted as relevant evidence; mismatched types are excluded.

Refers to Suite ID: TS-UA-COH-V2-EVID-001.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.coherence.domain.v2_constants import (
    COHERENCE_CATEGORY_TO_DOC_TYPES,
    MIN_EVIDENCE_BY_CATEGORY,
)
from src.coherence.services.v2.evidence_service import EvidenceBundle, EvidenceService


def _doc(doc_type: str) -> SimpleNamespace:
    """Minimal Document-like object with a document_type attribute."""
    return SimpleNamespace(document_type=doc_type)


@pytest.mark.unit
class TestEvidenceServiceCategoryAware:
    """EvidenceService returns honest coverage ratios per ADR-009 §2.2 thresholds."""

    def setup_method(self) -> None:
        self.svc = EvidenceService()

    # ------------------------------------------------------------------
    # Empty docs — zero bundle regardless of category
    # ------------------------------------------------------------------

    def test_empty_docs_returns_zero_bundle(self) -> None:
        result = self.svc.collect("SCOPE", [])
        assert result.count == 0
        assert result.evidence_coverage == 0.0
        assert result.avg_technical_reliability == 0.0
        assert result.missing_required == []

    # ------------------------------------------------------------------
    # LEGAL (threshold=1, relevant type: contract)
    # ------------------------------------------------------------------

    def test_legal_contract_doc_full_coverage(self) -> None:
        assert MIN_EVIDENCE_BY_CATEGORY["LEGAL"] == 1
        result = self.svc.collect("LEGAL", [_doc("contract")])
        assert result.count == 1
        assert result.evidence_coverage == 1.0
        assert result.missing_required == []

    def test_legal_ignores_budget_docs(self) -> None:
        # budget docs are not relevant evidence for LEGAL
        result = self.svc.collect("LEGAL", [_doc("budget"), _doc("budget")])
        assert result.count == 0
        assert result.evidence_coverage == 0.0

    # ------------------------------------------------------------------
    # BUDGET (threshold=3, relevant type: budget)
    # ------------------------------------------------------------------

    def test_budget_one_doc_partial_coverage(self) -> None:
        assert MIN_EVIDENCE_BY_CATEGORY["BUDGET"] == 3
        result = self.svc.collect("BUDGET", [_doc("budget")])
        assert result.count == 1
        assert result.evidence_coverage == pytest.approx(1 / 3, abs=0.001)
        assert result.missing_required  # non-empty when below threshold

    def test_budget_exact_threshold_full_coverage(self) -> None:
        docs = [_doc("budget"), _doc("budget"), _doc("budget")]
        result = self.svc.collect("BUDGET", docs)
        assert result.count == 3
        assert result.evidence_coverage == 1.0
        assert result.missing_required == []

    def test_budget_ignores_contract_docs(self) -> None:
        # contract docs do not count as budget evidence
        result = self.svc.collect("BUDGET", [_doc("contract"), _doc("contract")])
        assert result.count == 0
        assert result.evidence_coverage == 0.0

    def test_budget_two_docs_still_below_threshold(self) -> None:
        result = self.svc.collect("BUDGET", [_doc("budget"), _doc("budget")])
        assert result.count == 2
        assert result.evidence_coverage == pytest.approx(2 / 3, abs=0.001)
        assert result.missing_required  # must signal gap

    # ------------------------------------------------------------------
    # SCOPE (threshold=2, relevant type: contract)
    # ------------------------------------------------------------------

    def test_scope_one_contract_doc_half_coverage(self) -> None:
        assert MIN_EVIDENCE_BY_CATEGORY["SCOPE"] == 2
        result = self.svc.collect("SCOPE", [_doc("contract")])
        assert result.count == 1
        assert result.evidence_coverage == pytest.approx(0.5, abs=0.001)
        assert result.missing_required

    def test_scope_budget_doc_does_not_inflate_scope_count(self) -> None:
        result = self.svc.collect("SCOPE", [_doc("budget"), _doc("budget")])
        assert result.count == 0

    # ------------------------------------------------------------------
    # TIME (threshold=2, relevant type: schedule)
    # KEY ASSERTION: budget docs must NOT inflate TIME's evidence count.
    # ------------------------------------------------------------------

    def test_time_two_schedule_docs_full_coverage(self) -> None:
        assert MIN_EVIDENCE_BY_CATEGORY["TIME"] == 2
        result = self.svc.collect("TIME", [_doc("schedule"), _doc("schedule")])
        assert result.count == 2
        assert result.evidence_coverage == 1.0
        assert result.missing_required == []

    def test_time_budget_doc_does_not_inflate_time_count(self) -> None:
        # Core correctness test: cross-category contamination must be zero
        result = self.svc.collect("TIME", [_doc("budget"), _doc("contract")])
        assert result.count == 0, (
            "budget/contract docs must not count as TIME evidence — "
            "only schedule docs are relevant for TIME"
        )
        assert result.evidence_coverage == 0.0

    def test_time_mixed_types_counts_only_schedule(self) -> None:
        # 3 docs total; only the schedule one counts for TIME
        result = self.svc.collect(
            "TIME",
            [_doc("budget"), _doc("contract"), _doc("schedule")],
        )
        assert result.count == 1
        assert result.evidence_coverage == pytest.approx(0.5, abs=0.001)

    # ------------------------------------------------------------------
    # TECHNICAL (threshold=2, relevant types: technical_spec, drawing)
    # ------------------------------------------------------------------

    def test_technical_spec_counts_for_technical(self) -> None:
        result = self.svc.collect("TECHNICAL", [_doc("technical_spec"), _doc("technical_spec")])
        assert result.count == 2
        assert result.evidence_coverage == 1.0

    def test_drawing_counts_for_technical(self) -> None:
        result = self.svc.collect("TECHNICAL", [_doc("drawing")])
        assert result.count == 1
        assert result.evidence_coverage == pytest.approx(0.5, abs=0.001)

    def test_technical_mixed_technical_types(self) -> None:
        result = self.svc.collect("TECHNICAL", [_doc("technical_spec"), _doc("drawing")])
        assert result.count == 2
        assert result.evidence_coverage == 1.0

    # ------------------------------------------------------------------
    # QUALITY (no canonical prior → all doc types contribute)
    # ------------------------------------------------------------------

    def test_quality_accepts_all_doc_types(self) -> None:
        docs = [_doc("contract"), _doc("budget"), _doc("schedule")]
        result = self.svc.collect("QUALITY", docs)
        assert result.count == len(docs)  # no filter for QUALITY

    def test_quality_threshold_with_any_docs(self) -> None:
        assert MIN_EVIDENCE_BY_CATEGORY["QUALITY"] == 2
        result = self.svc.collect("QUALITY", [_doc("other")])
        assert result.count == 1
        assert result.evidence_coverage == pytest.approx(0.5, abs=0.001)

    # ------------------------------------------------------------------
    # Unknown category — falls back to no filter
    # ------------------------------------------------------------------

    def test_unknown_category_no_filter_all_docs_count(self) -> None:
        result = self.svc.collect("UNKNOWN_DOMAIN", [_doc("contract")])
        assert result.count == 1
        assert result.evidence_coverage == 1.0
        assert result.missing_required == []

    # ------------------------------------------------------------------
    # Coverage cap and references
    # ------------------------------------------------------------------

    def test_coverage_capped_at_one_with_surplus_docs(self) -> None:
        # LEGAL needs 1 contract doc; passing 5 should not push coverage past 1.0
        docs = [_doc("contract") for _ in range(5)]
        result = self.svc.collect("LEGAL", docs)
        assert result.evidence_coverage == 1.0

    def test_references_reflect_filtered_doc_count(self) -> None:
        # 3 docs: 2 budget, 1 contract; only 2 budget docs count for BUDGET
        docs = [_doc("budget"), _doc("budget"), _doc("contract")]
        result = self.svc.collect("BUDGET", docs)
        assert len(result.references) == 2  # only the 2 budget docs

    def test_return_type_is_evidence_bundle(self) -> None:
        result = self.svc.collect("TECHNICAL", [_doc("technical_spec")])
        assert isinstance(result, EvidenceBundle)

    # ------------------------------------------------------------------
    # Mapping completeness sanity check
    # ------------------------------------------------------------------

    def test_all_v2_categories_have_mapping_entry(self) -> None:
        for cat in MIN_EVIDENCE_BY_CATEGORY:
            assert cat in COHERENCE_CATEGORY_TO_DOC_TYPES, (
                f"Category {cat!r} missing from COHERENCE_CATEGORY_TO_DOC_TYPES"
            )
