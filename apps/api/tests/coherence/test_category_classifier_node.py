"""
CategoryClassifierNode tests — Capa 2 LLM escalation for ambiguous chunks only.
Suite ID: TS-UD-COH-CCN-001 — TASK-BCK-089

Key invariants:
- Chunks where ALL categories are clear (>= escalate_high) → no LLM call
- Chunks where ALL categories are below escalate_low threshold → no LLM call
- Chunks with ANY category in ambiguous zone (escalate_low, escalate_high) → LLM escalated
- LLM score overrides Capa 1 ONLY for ambiguous categories; clear categories keep Capa 1 score
- LLM call failure → graceful fallback to Capa 1 scores; was_escalated=False
- Batch: only ambiguous chunks trigger LLM; clear ones pass through
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.coherence.application.services.category_classifier_node import (
    CategoryClassifierNode,
    ChunkClassificationResult,
)
from src.coherence.application.services.category_router import ChunkSignal
from src.coherence.category_registry import CanonicalCategory, DefaultsThresholds

# ---------------------------------------------------------------------------
# Shared thresholds (matching registry defaults)
# ---------------------------------------------------------------------------

_THRESHOLDS = DefaultsThresholds(
    escalate_low=0.35,
    escalate_high=0.65,
    insufficient_evidence=0.20,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chunk(text: str = "sample text") -> ChunkSignal:
    return ChunkSignal(chunk_id=str(uuid4()), text=text)


def _all_clear_relevance(score: float = 0.80) -> dict[CanonicalCategory, float]:
    """All categories above escalate_high — no escalation needed."""
    return {cat: score for cat in CanonicalCategory}


def _all_low_relevance(score: float = 0.10) -> dict[CanonicalCategory, float]:
    """All categories below insufficient_evidence — no escalation needed."""
    return {cat: score for cat in CanonicalCategory}


def _ambiguous_relevance(
    ambiguous_cat: CanonicalCategory = CanonicalCategory.LEGAL,
    ambiguous_score: float = 0.50,
) -> dict[CanonicalCategory, float]:
    """One category in the ambiguous zone, rest are clear or low."""
    return {
        cat: (ambiguous_score if cat == ambiguous_cat else 0.10)
        for cat in CanonicalCategory
    }


def _mock_wrapper_returning(scores: dict[str, float]) -> MagicMock:
    """Return an AnthropicWrapper mock whose generate() yields the given JSON."""
    wrapper = MagicMock()
    response = MagicMock()
    response.content = json.dumps(scores)
    wrapper.generate = AsyncMock(return_value=response)
    return wrapper


def _make_node(wrapper: MagicMock | None = None) -> CategoryClassifierNode:
    if wrapper is None:
        wrapper = MagicMock()
        wrapper.generate = AsyncMock(return_value=MagicMock(content="{}"))
    return CategoryClassifierNode(wrapper=wrapper, thresholds=_THRESHOLDS)


# =============================================================================
# TS-UD-COH-CCN-001 — Ambiguity Detection
# =============================================================================


class TestAmbiguityDetection:
    """is_ambiguous_chunk() correctly identifies ambiguous chunks."""

    def test_all_clear_above_high_threshold_is_not_ambiguous(self):
        node = _make_node()
        relevance = _all_clear_relevance(0.80)
        assert not node.is_ambiguous_chunk(relevance)

    def test_all_below_low_threshold_is_not_ambiguous(self):
        node = _make_node()
        relevance = _all_low_relevance(0.10)
        assert not node.is_ambiguous_chunk(relevance)

    def test_one_category_in_zone_is_ambiguous(self):
        node = _make_node()
        relevance = _ambiguous_relevance(CanonicalCategory.LEGAL, 0.50)
        assert node.is_ambiguous_chunk(relevance)

    def test_exactly_at_escalate_low_is_not_ambiguous(self):
        # escalate_low=0.35: strict > so 0.35 is NOT in ambiguous zone
        node = _make_node()
        relevance = {cat: 0.35 for cat in CanonicalCategory}
        assert not node.is_ambiguous_chunk(relevance)

    def test_exactly_at_escalate_high_is_not_ambiguous(self):
        # escalate_high=0.65: strict < so 0.65 is NOT in ambiguous zone
        node = _make_node()
        relevance = {cat: 0.65 for cat in CanonicalCategory}
        assert not node.is_ambiguous_chunk(relevance)

    def test_multiple_categories_in_zone_is_ambiguous(self):
        node = _make_node()
        relevance = {
            CanonicalCategory.LEGAL: 0.40,
            CanonicalCategory.SCOPE: 0.55,
            CanonicalCategory.BUDGET: 0.10,
            CanonicalCategory.SCHEDULE: 0.80,
            CanonicalCategory.TECHNICAL: 0.10,
            CanonicalCategory.QUALITY: 0.10,
        }
        assert node.is_ambiguous_chunk(relevance)

    def test_ambiguous_categories_set_contains_only_in_zone(self):
        node = _make_node()
        relevance = {
            CanonicalCategory.LEGAL: 0.50,    # ambiguous
            CanonicalCategory.SCOPE: 0.80,    # clear
            CanonicalCategory.BUDGET: 0.10,   # low
            CanonicalCategory.SCHEDULE: 0.45, # ambiguous
            CanonicalCategory.TECHNICAL: 0.35, # exactly at low → not ambiguous
            CanonicalCategory.QUALITY: 0.65,  # exactly at high → not ambiguous
        }
        ambiguous = node.ambiguous_categories(relevance)
        assert ambiguous == {CanonicalCategory.LEGAL, CanonicalCategory.SCHEDULE}


# =============================================================================
# TS-UD-COH-CCN-002 — Single Chunk Classification
# =============================================================================


class TestClassifyChunk:
    """classify_chunk() respects the escalation gate."""

    @pytest.mark.asyncio
    async def test_clear_chunk_does_not_call_llm(self):
        """All categories clear → LLM wrapper.generate never called."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock()
        node = CategoryClassifierNode(wrapper=wrapper, thresholds=_THRESHOLDS)

        result = await node.classify_chunk(
            chunk=_chunk("Payment amount: $100,000"),
            capa1_relevance=_all_clear_relevance(0.80),
        )

        wrapper.generate.assert_not_called()
        assert not result.was_escalated
        assert len(result.escalated_categories) == 0

    @pytest.mark.asyncio
    async def test_below_threshold_chunk_does_not_call_llm(self):
        """All categories below threshold → no LLM call."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock()
        node = CategoryClassifierNode(wrapper=wrapper, thresholds=_THRESHOLDS)

        result = await node.classify_chunk(
            chunk=_chunk("Lorem ipsum"),
            capa1_relevance=_all_low_relevance(0.10),
        )

        wrapper.generate.assert_not_called()
        assert not result.was_escalated

    @pytest.mark.asyncio
    async def test_ambiguous_chunk_calls_llm(self):
        """Ambiguous chunk → wrapper.generate called exactly once."""
        llm_scores = {
            "LEGAL": 0.75, "SCOPE": 0.10, "BUDGET": 0.10,
            "SCHEDULE": 0.10, "TECHNICAL": 0.10, "QUALITY": 0.10,
        }
        wrapper = _mock_wrapper_returning(llm_scores)
        node = CategoryClassifierNode(wrapper=wrapper, thresholds=_THRESHOLDS)

        result = await node.classify_chunk(
            chunk=_chunk("This clause covers indemnification obligations."),
            capa1_relevance=_ambiguous_relevance(CanonicalCategory.LEGAL, 0.50),
        )

        wrapper.generate.assert_called_once()
        assert result.was_escalated
        assert CanonicalCategory.LEGAL in result.escalated_categories

    @pytest.mark.asyncio
    async def test_llm_overrides_only_ambiguous_categories(self):
        """LLM score replaces Capa 1 only for categories that were in the ambiguous zone."""
        capa1 = {
            CanonicalCategory.LEGAL: 0.50,    # ambiguous → LLM overrides
            CanonicalCategory.SCOPE: 0.80,    # clear → keep Capa 1
            CanonicalCategory.BUDGET: 0.10,   # low → keep Capa 1
            CanonicalCategory.SCHEDULE: 0.10,
            CanonicalCategory.TECHNICAL: 0.10,
            CanonicalCategory.QUALITY: 0.10,
        }
        llm_scores = {
            "LEGAL": 0.90, "SCOPE": 0.55, "BUDGET": 0.30,
            "SCHEDULE": 0.10, "TECHNICAL": 0.10, "QUALITY": 0.10,
        }
        wrapper = _mock_wrapper_returning(llm_scores)
        node = CategoryClassifierNode(wrapper=wrapper, thresholds=_THRESHOLDS)

        result = await node.classify_chunk(chunk=_chunk("text"), capa1_relevance=capa1)

        # LEGAL was ambiguous → LLM wins
        assert result.relevance[CanonicalCategory.LEGAL] == pytest.approx(0.90)
        # SCOPE was clear (0.80 >= 0.65) → Capa 1 preserved
        assert result.relevance[CanonicalCategory.SCOPE] == pytest.approx(0.80)
        # BUDGET was low (0.10 <= 0.35) → Capa 1 preserved
        assert result.relevance[CanonicalCategory.BUDGET] == pytest.approx(0.10)

    @pytest.mark.asyncio
    async def test_llm_exception_degrades_to_capa1(self):
        """If LLM call raises, fall back to Capa 1 scores; was_escalated=False."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        node = CategoryClassifierNode(wrapper=wrapper, thresholds=_THRESHOLDS)

        capa1 = _ambiguous_relevance(CanonicalCategory.LEGAL, 0.50)
        result = await node.classify_chunk(chunk=_chunk("text"), capa1_relevance=capa1)

        assert not result.was_escalated
        # Relevance unchanged — Capa 1 preserved
        for cat in CanonicalCategory:
            assert result.relevance[cat] == pytest.approx(capa1[cat])

    @pytest.mark.asyncio
    async def test_llm_invalid_json_degrades_to_capa1(self):
        """If LLM returns unparseable response, fall back to Capa 1."""
        wrapper = MagicMock()
        response = MagicMock()
        response.content = "NOT JSON AT ALL"
        wrapper.generate = AsyncMock(return_value=response)
        node = CategoryClassifierNode(wrapper=wrapper, thresholds=_THRESHOLDS)

        capa1 = _ambiguous_relevance(CanonicalCategory.SCOPE, 0.45)
        result = await node.classify_chunk(chunk=_chunk("scope of work"), capa1_relevance=capa1)

        assert not result.was_escalated
        for cat in CanonicalCategory:
            assert result.relevance[cat] == pytest.approx(capa1[cat])

    @pytest.mark.asyncio
    async def test_result_contains_all_categories(self):
        """Result relevance dict always contains all 6 CanonicalCategory keys."""
        llm_scores = {
            "LEGAL": 0.80, "SCOPE": 0.10, "BUDGET": 0.10,
            "SCHEDULE": 0.10, "TECHNICAL": 0.10, "QUALITY": 0.10,
        }
        wrapper = _mock_wrapper_returning(llm_scores)
        node = CategoryClassifierNode(wrapper=wrapper, thresholds=_THRESHOLDS)

        result = await node.classify_chunk(
            chunk=_chunk("indemnification clause text"),
            capa1_relevance=_ambiguous_relevance(CanonicalCategory.LEGAL, 0.50),
        )

        assert set(result.relevance.keys()) == set(CanonicalCategory)

    @pytest.mark.asyncio
    async def test_chunk_id_preserved_in_result(self):
        """ChunkClassificationResult.chunk_id matches input chunk."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock()
        node = CategoryClassifierNode(wrapper=wrapper, thresholds=_THRESHOLDS)

        chunk = _chunk("clear text")
        result = await node.classify_chunk(
            chunk=chunk,
            capa1_relevance=_all_clear_relevance(0.80),
        )

        assert result.chunk_id == chunk.chunk_id

    @pytest.mark.asyncio
    async def test_relevance_scores_clamped_to_unit_interval(self):
        """LLM scores outside [0, 1] are clamped before merging."""
        llm_scores = {
            "LEGAL": 1.5,   # above 1.0 → clamped to 1.0
            "SCOPE": -0.2,  # below 0.0 → clamped to 0.0
            "BUDGET": 0.10, "SCHEDULE": 0.10, "TECHNICAL": 0.10, "QUALITY": 0.10,
        }
        wrapper = _mock_wrapper_returning(llm_scores)
        node = CategoryClassifierNode(wrapper=wrapper, thresholds=_THRESHOLDS)

        capa1 = {
            CanonicalCategory.LEGAL: 0.50,   # ambiguous
            CanonicalCategory.SCOPE: 0.45,   # ambiguous
            CanonicalCategory.BUDGET: 0.10,
            CanonicalCategory.SCHEDULE: 0.10,
            CanonicalCategory.TECHNICAL: 0.10,
            CanonicalCategory.QUALITY: 0.10,
        }
        result = await node.classify_chunk(chunk=_chunk("text"), capa1_relevance=capa1)

        assert 0.0 <= result.relevance[CanonicalCategory.LEGAL] <= 1.0
        assert 0.0 <= result.relevance[CanonicalCategory.SCOPE] <= 1.0


# =============================================================================
# TS-UD-COH-CCN-003 — Batch Classification
# =============================================================================


class TestClassifyBatch:
    """classify_batch() processes multiple chunks; LLM called only for ambiguous ones."""

    @pytest.mark.asyncio
    async def test_empty_batch_returns_empty(self):
        wrapper = MagicMock()
        wrapper.generate = AsyncMock()
        node = CategoryClassifierNode(wrapper=wrapper, thresholds=_THRESHOLDS)

        results = await node.classify_batch(chunks=[], capa1_relevance_per_chunk=[])

        assert results == []
        wrapper.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_all_clear_batch_no_llm_calls(self):
        """3 clear chunks → 0 LLM calls."""
        wrapper = MagicMock()
        wrapper.generate = AsyncMock()
        node = CategoryClassifierNode(wrapper=wrapper, thresholds=_THRESHOLDS)

        chunks = [_chunk("clear chunk") for _ in range(3)]
        relevances = [_all_clear_relevance(0.80) for _ in range(3)]

        results = await node.classify_batch(chunks=chunks, capa1_relevance_per_chunk=relevances)

        assert len(results) == 3
        assert all(not r.was_escalated for r in results)
        wrapper.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_mixed_batch_only_escalates_ambiguous(self):
        """2 clear + 1 ambiguous → exactly 1 LLM call."""
        llm_scores = {
            "LEGAL": 0.85, "SCOPE": 0.10, "BUDGET": 0.10,
            "SCHEDULE": 0.10, "TECHNICAL": 0.10, "QUALITY": 0.10,
        }
        wrapper = _mock_wrapper_returning(llm_scores)
        node = CategoryClassifierNode(wrapper=wrapper, thresholds=_THRESHOLDS)

        chunks = [
            _chunk("clear chunk 1"),
            _chunk("ambiguous legal chunk"),
            _chunk("clear chunk 2"),
        ]
        relevances = [
            _all_clear_relevance(0.80),
            _ambiguous_relevance(CanonicalCategory.LEGAL, 0.50),
            _all_low_relevance(0.10),
        ]

        results = await node.classify_batch(chunks=chunks, capa1_relevance_per_chunk=relevances)

        assert len(results) == 3
        assert not results[0].was_escalated
        assert results[1].was_escalated
        assert not results[2].was_escalated
        assert wrapper.generate.call_count == 1

    @pytest.mark.asyncio
    async def test_batch_result_order_matches_input_order(self):
        """Results are returned in the same order as input chunks."""
        chunk_ids = [str(uuid4()) for _ in range(3)]
        chunks = [ChunkSignal(chunk_id=cid, text="text") for cid in chunk_ids]
        relevances = [_all_clear_relevance(0.80) for _ in range(3)]

        wrapper = MagicMock()
        wrapper.generate = AsyncMock()
        node = CategoryClassifierNode(wrapper=wrapper, thresholds=_THRESHOLDS)

        results = await node.classify_batch(chunks=chunks, capa1_relevance_per_chunk=relevances)

        assert [r.chunk_id for r in results] == chunk_ids


# =============================================================================
# TS-UD-COH-CCN-004 — Result dataclass contract
# =============================================================================


class TestChunkClassificationResult:
    """ChunkClassificationResult dataclass satisfies expected contract."""

    def test_is_immutable(self):
        result = ChunkClassificationResult(
            chunk_id="test-id",
            relevance={cat: 0.5 for cat in CanonicalCategory},
            was_escalated=False,
            escalated_categories=frozenset(),
        )
        with pytest.raises((AttributeError, TypeError)):
            result.was_escalated = True  # type: ignore[misc]

    def test_relevant_categories_above_insufficient_threshold(self):
        """relevant_categories() returns cats above insufficient_evidence (0.20)."""
        result = ChunkClassificationResult(
            chunk_id="test-id",
            relevance={
                CanonicalCategory.LEGAL: 0.80,   # relevant
                CanonicalCategory.SCOPE: 0.25,   # relevant (> 0.20)
                CanonicalCategory.BUDGET: 0.10,  # irrelevant
                CanonicalCategory.SCHEDULE: 0.10,
                CanonicalCategory.TECHNICAL: 0.10,
                CanonicalCategory.QUALITY: 0.10,
            },
            was_escalated=False,
            escalated_categories=frozenset(),
            insufficient_evidence_threshold=0.20,
        )
        relevant = result.relevant_categories()
        assert CanonicalCategory.LEGAL in relevant
        assert CanonicalCategory.SCOPE in relevant
        assert CanonicalCategory.BUDGET not in relevant
