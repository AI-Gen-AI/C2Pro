"""
Global aggregator for ECOA v2 (ADR-009 §14, §15).

Produces a `GlobalV2` from a list of `CategoryV2` objects, enforcing the
`MIN_ACTIVE_WEIGHT` stability rule and emitting the three independent axes
(`coherence_score`, `completeness_score`, `technical_reliability_index`)
without ever collapsing them into a single scalar.

Refers to Suite ID: TS-UA-COH-V2-GLBAGG-001.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Literal, cast

from src.coherence.application.dtos.coherence_v2_dtos import (
    CategoryStatus,
    CategoryV2,
    GlobalV2,
)
from src.coherence.domain.v2_constants import (
    DEFAULT_CATEGORY_WEIGHTS,
    MIN_ACTIVE_WEIGHT,
)

_ACTIVE_STATES: frozenset[CategoryStatus] = frozenset(
    {CategoryStatus.SCORED, CategoryStatus.CONFLICTING_EVIDENCE}
)


class GlobalAggregatorV2:
    def aggregate(
        self,
        categories: Iterable[CategoryV2],
        weights: dict[str, float] | None = None,
    ) -> GlobalV2:
        cats = list(categories)
        w = weights or DEFAULT_CATEGORY_WEIGHTS

        applicable = [c for c in cats if c.status is not CategoryStatus.NOT_APPLICABLE]
        active = [c for c in cats if c.status in _ACTIVE_STATES]

        applicable_weight_sum = sum(w.get(c.category, 0.0) for c in applicable)
        active_weight_sum = sum(w.get(c.category, 0.0) for c in active)
        active_weight = (
            active_weight_sum / applicable_weight_sum if applicable_weight_sum > 0 else 0.0
        )

        completeness_score = self._completeness(applicable, w)
        tri = self._technical_reliability_index(active, w)

        if not applicable:
            return GlobalV2(
                coherence_score=None,
                completeness_score=0.0,
                technical_reliability_index=0.0,
                status="pending_documents",
                score_reason="no_applicable_categories",
                active_weight=0.0,
            )

        if not active:
            # All categories are pending_documents / insufficient / error.
            pending_only = all(
                c.status is CategoryStatus.PENDING_DOCUMENTS for c in applicable
            )
            return GlobalV2(
                coherence_score=None,
                completeness_score=completeness_score,
                technical_reliability_index=0.0,
                status="pending_documents" if pending_only else "insufficient_active_weight",
                score_reason="pending_documents" if pending_only
                else "insufficient_active_weight",
                active_weight=0.0,
            )

        if active_weight < MIN_ACTIVE_WEIGHT:
            return GlobalV2(
                coherence_score=None,
                completeness_score=completeness_score,
                technical_reliability_index=tri,
                status="insufficient_active_weight",
                score_reason="insufficient_active_weight",
                active_weight=active_weight,
            )

        coherence = self._weighted_coherence(active, w)
        status = cast(Literal["scored", "partial", "insufficient_active_weight", "pending_documents"], "scored" if len(active) == len(applicable) else "partial")
        return GlobalV2(
            coherence_score=round(coherence, 2),
            completeness_score=round(completeness_score, 4),
            technical_reliability_index=round(tri, 4),
            status=status,
            score_reason="scored_categories_only",
            active_weight=round(active_weight, 4),
        )

    @staticmethod
    def _weighted_coherence(
        active: list[CategoryV2], weights: dict[str, float]
    ) -> float:
        total_w = sum(weights.get(c.category, 0.0) for c in active)
        if total_w <= 0:
            return 0.0
        weighted_sum = sum(
            (c.coherence_score or 0.0) * weights.get(c.category, 0.0) for c in active
        )
        return weighted_sum / total_w

    @staticmethod
    def _completeness(
        applicable: list[CategoryV2], weights: dict[str, float]
    ) -> float:
        if not applicable:
            return 0.0
        total_w = sum(weights.get(c.category, 0.0) for c in applicable)
        if total_w <= 0:
            return 0.0
        weighted = sum(
            c.evidence_coverage * weights.get(c.category, 0.0) for c in applicable
        )
        return weighted / total_w

    @staticmethod
    def _technical_reliability_index(
        active: list[CategoryV2], weights: dict[str, float]
    ) -> float:
        total_w = sum(weights.get(c.category, 0.0) for c in active)
        if total_w <= 0:
            return 0.0
        weighted = sum(
            c.technical_reliability * weights.get(c.category, 0.0) for c in active
        )
        return weighted / total_w


__all__ = ["GlobalAggregatorV2"]
