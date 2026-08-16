"""
Canonical global aggregation + critical-risk envelope (ADR-009 §C/§14).

This is the ONLY layer that sees `worst_open` (the worst open finding anywhere in
the project). It combines the per-category scores into a headline and applies the
global critical-risk envelope so a project with an open critical can never display
a headline that reads "healthy". It contains NO per-category scoring logic.

- Weighted mean over ASSESSED categories only — no `mean × coverage_ratio` collapse
  (§14 / the ADR-009 §1 P1 violation).
- `active_weight < MIN_ACTIVE_WEIGHT` ⇒ null headline (null-not-zero), explicit reason.
- Envelope only ever LOWERS the headline (interim `OVERALL_SEVERITY_CEILING`).

Refers to Suite ID: TS-UA-COH-CANON-GLOBAL-001.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.coherence.canonical.category import CategoryScore, Severity
from src.coherence.canonical.guardrails import OVERALL_SEVERITY_CEILING
from src.coherence.domain.v2_constants import MIN_ACTIVE_WEIGHT


@dataclass(frozen=True)
class GlobalScoreInput:
    category_scores: dict[str, CategoryScore]  # per-category (some score may be None)
    category_weights: dict[str, float]
    worst_open_severity: Severity | None  # worst open finding ANYWHERE — lives here only


@dataclass(frozen=True)
class GlobalScore:
    score: float | None  # None when active weight is insufficient (null-not-zero)
    active_weight: float
    envelope_applied: Severity | None  # which critical-risk cap fired, if any
    reason: str | None = None


def aggregate_global(inp: GlobalScoreInput) -> GlobalScore:
    """Combine category scores into the headline and apply the critical-risk envelope."""
    assessed = {
        category: cs.score
        for category, cs in inp.category_scores.items()
        if cs.score is not None
    }

    total_weight = sum(inp.category_weights.values())
    if total_weight <= 0.0:
        return GlobalScore(
            score=None, active_weight=0.0, envelope_applied=None, reason="no_weights"
        )

    active_weight = sum(inp.category_weights.get(c, 0.0) for c in assessed) / total_weight

    if not assessed or active_weight < MIN_ACTIVE_WEIGHT:
        return GlobalScore(
            score=None,
            active_weight=round(active_weight, 4),
            envelope_applied=None,
            reason="insufficient_active_weight",
        )

    assessed_weight_sum = sum(inp.category_weights.get(c, 0.0) for c in assessed)
    mean = (
        sum(inp.category_weights.get(c, 0.0) * score for c, score in assessed.items())
        / assessed_weight_sum
    )

    envelope_applied: Severity | None = None
    score = mean
    if inp.worst_open_severity is not None:
        cap = OVERALL_SEVERITY_CEILING.get(inp.worst_open_severity)
        if cap is not None and mean > cap:
            score = cap
            envelope_applied = inp.worst_open_severity

    return GlobalScore(
        score=round(score, 2),
        active_weight=round(active_weight, 4),
        envelope_applied=envelope_applied,
        reason=None,
    )


__all__ = ["GlobalScore", "GlobalScoreInput", "aggregate_global"]
