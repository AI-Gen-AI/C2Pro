"""
Refers to Suite ID: TS-UD-ANA-HYB-001

RED phase tests for Hybrid Search Result domain contract.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


def _hybrid_result_cls():
    try:
        from src.analysis.domain.search import HybridSearchResult
    except Exception as exc:  # pragma: no cover - intentional RED bootstrap
        pytest.fail(f"RED: missing HybridSearchResult contract: {exc}")
    return HybridSearchResult


def test_001_hybrid_search_result_creation_with_valid_data() -> None:
    """TS-UD-ANA-HYB-001: valid input creates a typed hybrid result entity."""
    HybridSearchResult = _hybrid_result_cls()

    result = HybridSearchResult(
        document_id=uuid4(),
        clause_id=uuid4(),
        text="Payment milestone tied to mechanical completion.",
        semantic_score=0.80,
        keyword_score=0.60,
        fusion_weight=0.70,
        rank=1,
        metadata={"source": "clauses"},
    )

    assert result.rank == 1
    assert result.text.startswith("Payment")
    assert result.metadata["source"] == "clauses"


def test_002_hybrid_score_uses_weighted_fusion() -> None:
    """TS-UD-ANA-HYB-001: hybrid_score must follow weighted semantic+keyword fusion."""
    HybridSearchResult = _hybrid_result_cls()

    result = HybridSearchResult(
        document_id=uuid4(),
        clause_id=uuid4(),
        text="Delivery lead time and penalties.",
        semantic_score=0.80,
        keyword_score=0.60,
        fusion_weight=0.70,
        rank=2,
    )

    assert result.hybrid_score == pytest.approx(0.74, rel=1e-4)


def test_003_hybrid_score_is_normalized_between_zero_and_one() -> None:
    """TS-UD-ANA-HYB-001: computed hybrid_score must be normalized to [0.0, 1.0]."""
    HybridSearchResult = _hybrid_result_cls()

    best = HybridSearchResult(
        document_id=uuid4(),
        clause_id=uuid4(),
        text="Warranty obligations with explicit acceptance criteria.",
        semantic_score=1.0,
        keyword_score=1.0,
        fusion_weight=0.5,
        rank=1,
    )
    worst = HybridSearchResult(
        document_id=uuid4(),
        clause_id=uuid4(),
        text="Unrelated text.",
        semantic_score=0.0,
        keyword_score=0.0,
        fusion_weight=0.5,
        rank=99,
    )

    assert 0.0 <= best.hybrid_score <= 1.0
    assert 0.0 <= worst.hybrid_score <= 1.0
    assert best.hybrid_score == pytest.approx(1.0)
    assert worst.hybrid_score == pytest.approx(0.0)


def test_004_rejects_empty_text() -> None:
    """TS-UD-ANA-HYB-001: text evidence is mandatory and cannot be blank."""
    HybridSearchResult = _hybrid_result_cls()

    with pytest.raises(ValueError, match="text"):
        HybridSearchResult(
            document_id=uuid4(),
            clause_id=uuid4(),
            text="   ",
            semantic_score=0.40,
            keyword_score=0.55,
            fusion_weight=0.50,
            rank=1,
        )


def test_005_rejects_semantic_score_out_of_range() -> None:
    """TS-UD-ANA-HYB-001: semantic_score must be in [0.0, 1.0]."""
    HybridSearchResult = _hybrid_result_cls()

    with pytest.raises(ValueError, match="semantic_score"):
        HybridSearchResult(
            document_id=uuid4(),
            clause_id=uuid4(),
            text="Scope inclusion clause.",
            semantic_score=1.20,
            keyword_score=0.30,
            fusion_weight=0.60,
            rank=1,
        )


def test_006_rejects_keyword_score_out_of_range() -> None:
    """TS-UD-ANA-HYB-001: keyword_score must be in [0.0, 1.0]."""
    HybridSearchResult = _hybrid_result_cls()

    with pytest.raises(ValueError, match="keyword_score"):
        HybridSearchResult(
            document_id=uuid4(),
            clause_id=uuid4(),
            text="Budget cap and escalation clause.",
            semantic_score=0.30,
            keyword_score=-0.10,
            fusion_weight=0.60,
            rank=1,
        )


def test_007_rejects_invalid_fusion_weight() -> None:
    """TS-UD-ANA-HYB-001: fusion_weight must be in [0.0, 1.0]."""
    HybridSearchResult = _hybrid_result_cls()

    with pytest.raises(ValueError, match="fusion_weight"):
        HybridSearchResult(
            document_id=uuid4(),
            clause_id=uuid4(),
            text="Milestone completion terms.",
            semantic_score=0.60,
            keyword_score=0.70,
            fusion_weight=1.10,
            rank=1,
        )


def test_008_rejects_non_positive_rank() -> None:
    """TS-UD-ANA-HYB-001: ranking position must be a positive integer."""
    HybridSearchResult = _hybrid_result_cls()

    with pytest.raises(ValueError, match="rank"):
        HybridSearchResult(
            document_id=uuid4(),
            clause_id=uuid4(),
            text="Termination rights clause.",
            semantic_score=0.50,
            keyword_score=0.50,
            fusion_weight=0.50,
            rank=0,
        )
