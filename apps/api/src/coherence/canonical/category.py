"""
Canonical per-category coherence scoring (ADR-009 2026-08-16 amendment §A/§B/§D).

`score_category` is a **pure function of one category's own evidence**. Per the
binding separation of concerns (§C) it NEVER takes `worst_open` or any
project-global severity — the global critical-risk envelope lives in
`global_agg.aggregate_global`.

Interim curve (calibratable): a hard conflict places the category inside its
severity band `[floor, ceiling]` (see `guardrails.py`), positioned by detection
certainty × materiality — higher certainty/materiality ⇒ closer to the floor
(stronger penalty, §D). A critical therefore lands in `[25, 45]`, never ~0 and
never in the "falsehood" zone. Absence of a hard conflict ⇒ score == base.

Refers to Suite ID: TS-UA-COH-CANON-CAT-001.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from src.coherence.canonical.guardrails import (
    BAND_THRESHOLDS,
    CATEGORY_SEVERITY_CEILING,
    CATEGORY_SEVERITY_FLOOR,
    FLOOR_MIN_SCORE,
)

Severity = Literal["low", "medium", "high", "critical"]
Band = Literal["clean", "watch", "poor", "critical"]


@dataclass(frozen=True)
class ConflictInput:
    """A hard conflict detected within a single category."""

    severity: Severity
    certainty: float  # 0..1 detection certainty — scales the PENALTY (§D)
    magnitude: float | None = None  # 0..1 normalized discrepancy materiality (calibration input)
    independent_count: int = 1  # reserved for calibration; unused in the interim curve


@dataclass(frozen=True)
class CategoryScoreInput:
    """Everything the canonical scorer needs about ONE category (no global state)."""

    base: float  # 0..100 clean / rule-signal baseline for THIS category
    conflict: ConflictInput | None = None
    assessed: bool = True  # False ⇒ honest null (never fabricate 100)
    evidence_sufficient: bool = True  # False ⇒ null-not-zero


@dataclass(frozen=True)
class CategoryScore:
    """Result: nullable score (null-not-zero), semantic band, and honest audit trail."""

    score: float | None
    band: Band | None
    penalty_steps: list[dict[str, Any]] = field(default_factory=list)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _band_for(score: float) -> Band:
    for threshold, band in BAND_THRESHOLDS:
        if score >= threshold:
            return band  # type: ignore[return-value]
    return "critical"


def score_category(inp: CategoryScoreInput) -> CategoryScore:
    """Compute one category's canonical coherence score.

    Invariants (ADR-009 §A/§B/§D):
    - null-not-zero: unassessed / insufficient evidence ⇒ score is None.
    - graduated & monotonic: worse severity / higher certainty / higher materiality
      can never IMPROVE the score.
    - conflict != 0: a detected conflict never scores 0 (floor `FLOOR_MIN_SCORE`),
      and a critical lands in its interim band, not the "falsehood" zone.
    """
    if not inp.assessed or not inp.evidence_sufficient:
        return CategoryScore(
            score=None,
            band=None,
            penalty_steps=[{"step": "null", "reason": "insufficient_or_unassessed"}],
        )

    base = _clamp(inp.base, 0.0, 100.0)

    if inp.conflict is None:
        return CategoryScore(
            score=round(base, 2),
            band=_band_for(base),
            penalty_steps=[{"step": "base", "value": base}],
        )

    conflict = inp.conflict
    ceiling = CATEGORY_SEVERITY_CEILING.get(conflict.severity, CATEGORY_SEVERITY_CEILING["high"])
    floor = CATEGORY_SEVERITY_FLOOR.get(conflict.severity, CATEGORY_SEVERITY_FLOOR["high"])

    certainty = _clamp(conflict.certainty, 0.0, 1.0)
    magnitude = _clamp(conflict.magnitude if conflict.magnitude is not None else 1.0, 0.0, 1.0)
    # strength ∈ [0,1]: higher certainty/materiality ⇒ stronger penalty ⇒ nearer the floor.
    strength = _clamp(certainty * magnitude, 0.0, 1.0)

    score = ceiling - (ceiling - floor) * strength
    score = max(score, FLOOR_MIN_SCORE)  # never 0 for a detected conflict (§A)

    return CategoryScore(
        score=round(score, 2),
        band=_band_for(score),
        penalty_steps=[
            {
                "step": "severity_band",
                "severity": conflict.severity,
                "floor": floor,
                "ceiling": ceiling,
            },
            {
                "step": "penalty_strength",
                "certainty": certainty,
                "magnitude": magnitude,
                "value": strength,
            },
            {"step": "score", "value": score},
        ],
    )


__all__ = [
    "Band",
    "CategoryScore",
    "CategoryScoreInput",
    "ConflictInput",
    "Severity",
    "score_category",
]
