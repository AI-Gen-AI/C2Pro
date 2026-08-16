"""
Canonical coherence scoring (ADR-009 2026-08-16 governing amendment).

ONE authoritative, graduated, monotonic, calibratable semantic (§F), split into
two independently-testable pure layers with a strict separation of concerns (§C):

- `category.score_category`  — per-category score from THAT category's own evidence
  only. NEVER sees `worst_open` or any project-global severity.
- `global_agg.aggregate_global` — weighted mean + the global critical-risk envelope.
  The ONLY place `worst_open` lives.

Interim production guardrails (45/60, critical band floor 25, …) live in
`guardrails.py` and are explicitly NOT final calibrated thresholds — they are
replaced once the multi-metric calibration gate passes. Nothing here touches the
live `/evaluate` path; wiring happens behind shadow + calibration.
"""
from __future__ import annotations

from src.coherence.canonical.category import (
    CategoryScore,
    CategoryScoreInput,
    ConflictInput,
    score_category,
)
from src.coherence.canonical.global_agg import (
    GlobalScore,
    GlobalScoreInput,
    aggregate_global,
)

__all__ = [
    "CategoryScore",
    "CategoryScoreInput",
    "ConflictInput",
    "GlobalScore",
    "GlobalScoreInput",
    "aggregate_global",
    "score_category",
]
