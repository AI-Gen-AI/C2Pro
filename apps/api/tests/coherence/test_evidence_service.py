"""
Tests for EvidenceService category-aware coverage (ADR-009 §2.2).

Phase 1 deterministic increment: collect() now uses MIN_EVIDENCE_BY_CATEGORY
to compute an honest evidence_coverage ratio instead of always returning 1.0.

Refers to Suite ID: TS-UA-COH-V2-EVID-001.
"""
from __future__ import annotations

import pytest

from src.coherence.domain.v2_constants import MIN_EVIDENCE_BY_CATEGORY
from src.coherence.services.v2.evidence_service import EvidenceBundle, EvidenceService


@pytest.mark.unit
class TestEvidenceServiceCategoryAware:
    """EvidenceService returns honest coverage ratios per ADR-009 §2.2 thresholds."""

    def setup_method(self) -> None:
        self.svc = EvidenceService()

    def test_empty_docs_returns_zero_bundle(self) -> None:
        result = self.svc.collect("SCOPE", [])
        assert result.count == 0
        assert result.evidence_coverage == 0.0
        assert result.avg_technical_reliability == 0.0
        assert result.missing_required == []

    def test_legal_threshold_one_single_doc_full_coverage(self) -> None:
        # LEGAL threshold = 1; one doc is enough
        assert MIN_EVIDENCE_BY_CATEGORY["LEGAL"] == 1
        result = self.svc.collect("LEGAL", ["doc_a"])
        assert result.count == 1
        assert result.evidence_coverage == 1.0
        assert result.missing_required == []

    def test_budget_one_doc_partial_coverage(self) -> None:
        # BUDGET threshold = 3; 1 doc → coverage = 1/3
        assert MIN_EVIDENCE_BY_CATEGORY["BUDGET"] == 3
        result = self.svc.collect("BUDGET", ["doc_a"])
        assert result.count == 1
        assert result.evidence_coverage == pytest.approx(1 / 3, abs=0.001)
        assert result.missing_required  # non-empty when below threshold

    def test_budget_exact_threshold_full_coverage(self) -> None:
        result = self.svc.collect("BUDGET", ["a", "b", "c"])
        assert result.count == 3
        assert result.evidence_coverage == 1.0
        assert result.missing_required == []

    def test_scope_one_doc_half_coverage(self) -> None:
        # SCOPE threshold = 2; 1 doc → coverage = 0.5
        assert MIN_EVIDENCE_BY_CATEGORY["SCOPE"] == 2
        result = self.svc.collect("SCOPE", ["doc_a"])
        assert result.count == 1
        assert result.evidence_coverage == pytest.approx(0.5, abs=0.001)
        assert result.missing_required  # non-empty

    def test_coverage_capped_at_one_with_surplus_docs(self) -> None:
        # LEGAL needs 1; passing 5 docs should not push coverage past 1.0
        result = self.svc.collect("LEGAL", list(range(5)))
        assert result.evidence_coverage == 1.0

    def test_unknown_category_defaults_to_threshold_one(self) -> None:
        result = self.svc.collect("UNKNOWN_DOMAIN", ["doc_a"])
        assert result.count == 1
        assert result.evidence_coverage == 1.0
        assert result.missing_required == []

    def test_references_length_matches_doc_count(self) -> None:
        docs = ["a", "b", "c"]
        result = self.svc.collect("SCOPE", docs)
        assert len(result.references) == len(docs)

    def test_budget_two_docs_still_below_threshold(self) -> None:
        # BUDGET=3; 2 docs → still insufficient, coverage ≈ 0.667
        result = self.svc.collect("BUDGET", ["a", "b"])
        assert result.count == 2
        assert result.evidence_coverage == pytest.approx(2 / 3, abs=0.001)
        assert result.missing_required  # must signal gap

    def test_time_threshold_two_exactly_two_docs(self) -> None:
        assert MIN_EVIDENCE_BY_CATEGORY["TIME"] == 2
        result = self.svc.collect("TIME", ["doc_x", "doc_y"])
        assert result.count == 2
        assert result.evidence_coverage == 1.0
        assert result.missing_required == []

    def test_return_type_is_evidence_bundle(self) -> None:
        result = self.svc.collect("TECHNICAL", ["doc"])
        assert isinstance(result, EvidenceBundle)
