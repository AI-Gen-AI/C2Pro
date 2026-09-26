"""
INTERIM production safety guardrails for the canonical coherence scorer.

**These are NOT final calibrated thresholds** (ADR-009 2026-08-16 amendment §B).
They are named, single-sourced constants that keep production honest while the
unified model is validated; the multi-metric calibration gate (§G) replaces them
with empirically-calibrated values. Do not treat any number here as canonical
truth — treat it as a documented interim.

Provenance:
- Per-category CEILINGS carried from PR #532 (`category critical ≤ 45`, etc.).
- OVERALL (global-envelope) ceilings RE-CALIBRATED 2026-08-18 against expert ground
  truth (ADR-009 §G.1, VP-approved): the #532 `overall critical ≤ 60` over-penalized
  vs experts — see the OVERALL_SEVERITY_CEILING note below.
- Per-severity FLOORS: each severity's floor is the next-worse severity's ceiling,
  so the bands tile without overlap; the **critical floor (25)** was pinned by the
  VP on 2026-08-16 to replace the rejected `≈8` (which read as "false/invalid").
"""
from __future__ import annotations

from typing import Final

# A category with an open finding may not SCORE ABOVE its severity ceiling.
CATEGORY_SEVERITY_CEILING: Final[dict[str, float]] = {
    "low": 95.0,
    "medium": 80.0,
    "high": 65.0,
    "critical": 45.0,
}

# Where a fully-certain, fully-material conflict of each severity LANDS (band floor).
# Anchored on the next-worse ceiling; critical floor VP-pinned (2026-08-16) = 25.
CATEGORY_SEVERITY_FLOOR: Final[dict[str, float]] = {
    "low": 80.0,      # next-worse = medium ceiling
    "medium": 65.0,   # next-worse = high ceiling
    "high": 45.0,     # next-worse = critical ceiling
    "critical": 25.0,  # VP-pinned interim floor (materially-poor-but-explainable, NOT ~8)
}

# The global headline may not exceed this ceiling while an open finding of the given
# worst severity exists anywhere in the project (global critical-risk envelope, §C).
# CALIBRATED 2026-08-18 (VP-approved, data-driven, ADR-009 §G.1): the interim #532 caps
# (critical 60 / high 75) over-penalized by ~25 pts vs expert ground truth — on 14
# single-critical golden projects experts scored 80-91 (mean 88.7) while the engine
# slammed them to 60 (scorer-direct MAE 28 on findings-bearing projects). Raised so the
# envelope stops over-penalizing while still capping below a clean headline; residual MAE
# 5.5 is the category model, not the envelope. Ranking was already correct (Pearson 0.946).
OVERALL_SEVERITY_CEILING: Final[dict[str, float]] = {
    "low": 100.0,
    "medium": 95.0,
    "high": 90.0,
    "critical": 85.0,
}

# A detected conflict is never scored to exactly 0 (§A — incoherence != falsehood).
FLOOR_MIN_SCORE: Final[float] = 5.0

# Interim semantic bands for display/audit (calibratable). Ordered high→low.
BAND_THRESHOLDS: Final[tuple[tuple[float, str], ...]] = (
    (80.0, "clean"),
    (60.0, "watch"),
    (40.0, "poor"),
    (0.0, "critical"),
)

__all__ = [
    "BAND_THRESHOLDS",
    "CATEGORY_SEVERITY_CEILING",
    "CATEGORY_SEVERITY_FLOOR",
    "FLOOR_MIN_SCORE",
    "OVERALL_SEVERITY_CEILING",
]
