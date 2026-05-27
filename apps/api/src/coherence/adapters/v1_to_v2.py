"""
Pure adapter: v1 `DashboardSummary`-shaped dict → ECOA v2 `CoherenceV2Payload`.

Used during Shadow Mode so older persisted rows can be projected into the
v2 frontend without recomputing the engine. No DB calls, no I/O.

Refers to Suite ID: TS-UA-COH-V2-ADAPT-001.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from src.coherence.application.dtos.coherence_v2_dtos import (
    CategoryStatus,
    CategoryV2,
    CoherenceV2Payload,
    GlobalV2,
    ScoreExplanation,
)
from src.coherence.domain.v2_constants import (
    DEFAULT_CATEGORY_WEIGHTS,
    MIN_ACTIVE_WEIGHT,
)


def adapt_v1_dashboard(
    v1: dict[str, Any],
    *,
    project_id: UUID,
    generated_at: datetime,
) -> CoherenceV2Payload:
    sub_scores = v1.get("sub_scores") or {}
    coherence_score = v1.get("coherence_score")

    if not sub_scores or coherence_score is None:
        categories = [
            CategoryV2(
                category=cat,
                status=CategoryStatus.INSUFFICIENT_EVIDENCE,
                coherence_score=None,
                evidence_coverage=0.0,
                technical_reliability=0.0,
                evidence_freshness=0.0,
            )
            for cat in DEFAULT_CATEGORY_WEIGHTS
        ]
        return CoherenceV2Payload(
            project_id=project_id,
            generated_at=generated_at,
            **{
                "global": GlobalV2(
                    coherence_score=None,
                    completeness_score=0.0,
                    technical_reliability_index=0.0,
                    status="insufficient_active_weight",
                    score_reason="insufficient_active_weight" if sub_scores else "no_v1_data",
                    active_weight=0.0,
                )
            },
            categories=categories,
        )

    # Phase B fix (ADR-009 §14): iterate over canonical DEFAULT_CATEGORY_WEIGHTS,
    # classify null sub_scores as INSUFFICIENT_EVIDENCE, compute real active_weight.
    # Do NOT echo v1["coherence_score"] — it may carry the buggy mean×coverage_ratio value.
    categories = []
    for cat in DEFAULT_CATEGORY_WEIGHTS:
        score = sub_scores.get(cat)
        if score is None:
            categories.append(
                CategoryV2(
                    category=cat,
                    status=CategoryStatus.INSUFFICIENT_EVIDENCE,
                    coherence_score=None,
                    evidence_coverage=0.0,
                    technical_reliability=0.0,
                    evidence_freshness=0.0,
                )
            )
        else:
            categories.append(
                CategoryV2(
                    category=cat,
                    status=CategoryStatus.SCORED,
                    coherence_score=float(score),
                    evidence_coverage=1.0,
                    technical_reliability=1.0,
                    evidence_freshness=1.0,
                    score_explanation=ScoreExplanation(
                        positive_factors=["adapted_from_v1"],
                        score_path=[{"step": "adapter", "source": "v1_dashboard"}],
                    ),
                )
            )

    # Compute real active_weight from DEFAULT_CATEGORY_WEIGHTS (single SoT)
    total_weight = sum(DEFAULT_CATEGORY_WEIGHTS.values())
    scored_cats = [cat for cat in DEFAULT_CATEGORY_WEIGHTS if sub_scores.get(cat) is not None]
    active_weight = sum(DEFAULT_CATEGORY_WEIGHTS[c] for c in scored_cats) / total_weight

    # §14 guard
    if active_weight < MIN_ACTIVE_WEIGHT:
        return CoherenceV2Payload(
            project_id=project_id,
            generated_at=generated_at,
            **{
                "global": GlobalV2(
                    coherence_score=None,
                    completeness_score=0.0,
                    technical_reliability_index=0.0,
                    status="insufficient_active_weight",
                    score_reason="insufficient_active_weight",
                    active_weight=round(active_weight, 4),
                )
            },
            categories=categories,
        )

    # Weighted mean over scored categories only (no coverage_ratio multiplier)
    scored_weight_sum = sum(DEFAULT_CATEGORY_WEIGHTS[c] for c in scored_cats)
    computed_score = round(
        sum(DEFAULT_CATEGORY_WEIGHTS[c] * sub_scores[c] for c in scored_cats)
        / scored_weight_sum,
        2,
    )
    status = "scored" if len(scored_cats) == len(DEFAULT_CATEGORY_WEIGHTS) else "partial"
    return CoherenceV2Payload(
        project_id=project_id,
        generated_at=generated_at,
        **{
            "global": GlobalV2(
                coherence_score=computed_score,
                completeness_score=1.0,
                technical_reliability_index=1.0,
                status=status,
                score_reason="scored_categories_only",
                active_weight=round(active_weight, 4),
            )
        },
        categories=categories,
    )


__all__ = ["adapt_v1_dashboard"]
