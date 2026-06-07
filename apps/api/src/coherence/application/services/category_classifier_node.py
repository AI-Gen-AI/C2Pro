"""
CategoryClassifierNode — Capa 2 LLM escalation for ambiguous chunks.

Suite ID: TS-UD-COH-CCN-001 — TASK-BCK-089

Implements SPEC §D3 (Cascada en capas):
  Capa 0 — doc_type priors (CategoryRouter)
  Capa 1 — deterministic structural + lexicon (CategoryRouter)
  Capa 2 — LLM multi-label classifier, invoked ONLY for ambiguous chunks
             (escalate_low < relevance < escalate_high for at least one category)

Cost invariants:
  - A chunk where ALL categories are clear (>= escalate_high) is NOT escalated.
  - A chunk where ALL categories are below escalate_low is NOT escalated.
  - LLM is called at most once per ambiguous chunk (not per ambiguous category).
  - On LLM failure the node degrades gracefully to Capa 1 scores.

Location: apps/api/src/coherence/application/services/category_classifier_node.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog

from src.coherence.application.services.category_router import ChunkSignal
from src.coherence.category_registry import CanonicalCategory, DefaultsThresholds

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Prompt (English — best LLM performance per project convention)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a construction-contract document categorization assistant. "
    "You receive a text chunk and return multi-label relevance scores (0.0–1.0) "
    "indicating how relevant the chunk is to each of 6 coherence categories. "
    "Return ONLY valid JSON — no prose, no markdown fences."
)

_USER_PROMPT_TEMPLATE = """\
Classify the relevance of the following text chunk for each category.

Categories:
- LEGAL: Indemnification, liability, penalties, jurisdiction, termination, warranties
- SCOPE: Scope of work, deliverables, project boundaries, inclusions/exclusions
- BUDGET: Financial amounts, pricing, cost estimates, payment schedules, invoicing
- SCHEDULE: Timeline, milestones, start/end dates, durations, deadlines
- TECHNICAL: Technical specifications, materials, methods, engineering standards
- QUALITY: Quality requirements, acceptance criteria, inspections, certifications

Text chunk:
<chunk>
{text}
</chunk>

Return ONLY a JSON object with scores 0.0 (not relevant) to 1.0 (highly relevant):
{{"LEGAL": 0.0, "SCOPE": 0.0, "BUDGET": 0.0, "SCHEDULE": 0.0, "TECHNICAL": 0.0, "QUALITY": 0.0}}"""

# Mapping from LLM string keys back to enum
_STR_TO_CATEGORY: dict[str, CanonicalCategory] = {cat.value: cat for cat in CanonicalCategory}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ChunkClassificationResult:
    """Immutable result of Capa 2 classification for a single chunk."""

    chunk_id: str
    relevance: dict[CanonicalCategory, float]
    was_escalated: bool
    escalated_categories: frozenset[CanonicalCategory]
    insufficient_evidence_threshold: float = 0.20

    def relevant_categories(self) -> list[CanonicalCategory]:
        """Categories with relevance above the insufficient_evidence threshold."""
        t = self.insufficient_evidence_threshold
        return [cat for cat, rel in self.relevance.items() if rel > t]


# ---------------------------------------------------------------------------
# CategoryClassifierNode
# ---------------------------------------------------------------------------

class CategoryClassifierNode:
    """Capa 2 LLM escalation node.

    Usage:
        node = CategoryClassifierNode.from_wrapper(wrapper, thresholds)
        result = await node.classify_chunk(chunk, capa1_relevance)
        # result.was_escalated is True iff LLM was called
    """

    def __init__(
        self,
        wrapper: Any,  # AnthropicWrapper (typed as Any to avoid circular import)
        thresholds: DefaultsThresholds,
    ) -> None:
        self._wrapper = wrapper
        self._thresholds = thresholds

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def ambiguous_categories(
        self, relevance: dict[CanonicalCategory, float]
    ) -> set[CanonicalCategory]:
        """Categories strictly inside the ambiguous zone (escalate_low, escalate_high)."""
        lo = self._thresholds.escalate_low
        hi = self._thresholds.escalate_high
        return {cat for cat, rel in relevance.items() if lo < rel < hi}

    def is_ambiguous_chunk(self, relevance: dict[CanonicalCategory, float]) -> bool:
        """True iff at least one category is in the ambiguous zone."""
        return bool(self.ambiguous_categories(relevance))

    # ------------------------------------------------------------------
    # Single-chunk classification
    # ------------------------------------------------------------------

    async def classify_chunk(
        self,
        chunk: ChunkSignal,
        capa1_relevance: dict[CanonicalCategory, float],
        *,
        tenant_id: UUID | None = None,
    ) -> ChunkClassificationResult:
        """Classify a single chunk.

        Returns Capa 1 scores unchanged if the chunk is not ambiguous.
        Calls LLM and merges scores for ambiguous chunks.
        Degrades gracefully to Capa 1 on LLM error.
        """
        ambiguous = self.ambiguous_categories(capa1_relevance)

        if not ambiguous:
            return ChunkClassificationResult(
                chunk_id=chunk.chunk_id,
                relevance=dict(capa1_relevance),
                was_escalated=False,
                escalated_categories=frozenset(),
                insufficient_evidence_threshold=self._thresholds.insufficient_evidence,
            )

        try:
            llm_scores = await self._call_llm(chunk.text, tenant_id)
        except Exception as exc:  # noqa: BLE001 — never block evaluation
            logger.warning(
                "CategoryClassifierNode LLM call failed; falling back to Capa 1",
                chunk_id=chunk.chunk_id,
                error=str(exc),
            )
            return ChunkClassificationResult(
                chunk_id=chunk.chunk_id,
                relevance=dict(capa1_relevance),
                was_escalated=False,
                escalated_categories=frozenset(),
                insufficient_evidence_threshold=self._thresholds.insufficient_evidence,
            )

        merged = self._merge_scores(capa1_relevance, llm_scores, ambiguous)
        return ChunkClassificationResult(
            chunk_id=chunk.chunk_id,
            relevance=merged,
            was_escalated=True,
            escalated_categories=frozenset(ambiguous),
            insufficient_evidence_threshold=self._thresholds.insufficient_evidence,
        )

    # ------------------------------------------------------------------
    # Batch classification
    # ------------------------------------------------------------------

    async def classify_batch(
        self,
        chunks: list[ChunkSignal],
        capa1_relevance_per_chunk: list[dict[CanonicalCategory, float]],
        *,
        tenant_id: UUID | None = None,
    ) -> list[ChunkClassificationResult]:
        """Classify a batch of chunks.

        Processes each chunk independently. Order is preserved.
        LLM is called only for chunks that are ambiguous.
        """
        results: list[ChunkClassificationResult] = []
        for chunk, relevance in zip(chunks, capa1_relevance_per_chunk, strict=True):
            result = await self.classify_chunk(
                chunk=chunk, capa1_relevance=relevance, tenant_id=tenant_id
            )
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Private: LLM call + parsing
    # ------------------------------------------------------------------

    async def _call_llm(
        self, text: str, tenant_id: UUID | None
    ) -> dict[CanonicalCategory, float]:
        from src.core.ai.anthropic_wrapper import AIRequest
        from src.core.ai.model_router import AITaskType

        prompt = _USER_PROMPT_TEMPLATE.format(text=text)
        request = AIRequest(
            prompt=prompt,
            task_type=AITaskType.CLASSIFICATION,
            system_prompt=_SYSTEM_PROMPT,
            tenant_id=tenant_id,
            low_budget_mode=True,  # Haiku — classification is bounded judgment
            use_cache=True,
        )
        response = await self._wrapper.generate(request)
        return self._parse_response(response.content)

    def _parse_response(self, content: str) -> dict[CanonicalCategory, float]:
        """Parse LLM JSON response to per-category scores, clamped to [0, 1]."""
        try:
            raw: dict[str, Any] = json.loads(content)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"LLM returned non-JSON: {content!r}") from exc

        result: dict[CanonicalCategory, float] = {}
        for cat in CanonicalCategory:
            key = cat.value
            raw_score = raw.get(key, 0.0)
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                score = 0.0
            result[cat] = max(0.0, min(1.0, score))  # clamp to [0, 1]

        return result

    @staticmethod
    def _merge_scores(
        capa1: dict[CanonicalCategory, float],
        llm: dict[CanonicalCategory, float],
        ambiguous: set[CanonicalCategory],
    ) -> dict[CanonicalCategory, float]:
        """Merge LLM scores into Capa 1 scores for ambiguous categories only."""
        return {
            cat: (llm[cat] if cat in ambiguous else capa1[cat])
            for cat in CanonicalCategory
        }
