"""
ECOA v2 domain constants.

Source of truth: ADR-009 (Evidence-Oriented Coherence Orchestration v2),
sections §2.2, §13 and §14. Any change here MUST be reflected in the ADR.

Refers to Suite ID: TS-UD-COH-V2-CONST-001.
"""
from __future__ import annotations

from typing import Final

MIN_EVIDENCE_BY_CATEGORY: Final[dict[str, int]] = {
    "SCOPE": 2,
    "BUDGET": 3,
    "QUALITY": 2,
    "TECHNICAL": 2,
    "LEGAL": 1,
    "TIME": 2,
}

SEVERITY_MULTIPLIERS: Final[dict[str, float]] = {
    "low": 0.9,
    "medium": 0.7,
    "high": 0.4,
    "critical": 0.1,
}

MIN_ACTIVE_WEIGHT: Final[float] = 0.35

DEFAULT_CATEGORY_WEIGHTS: Final[dict[str, float]] = {
    cat: 1.0 / len(MIN_EVIDENCE_BY_CATEGORY) for cat in MIN_EVIDENCE_BY_CATEGORY
}

# ---------------------------------------------------------------------------
# Canonical score_version identifiers (Phase F, ADR-009 §F).
# All scoring surfaces MUST use these constants — no inline string literals.
# ---------------------------------------------------------------------------

SCORE_VERSION_V1: Final = "coherence-v1"
SCORE_VERSION_V2: Final = "coherence-v2"
SCORE_VERSION_VALUES: Final[tuple[str, ...]] = (SCORE_VERSION_V1, SCORE_VERSION_V2)

__all__ = [
    "DEFAULT_CATEGORY_WEIGHTS",
    "MIN_ACTIVE_WEIGHT",
    "MIN_EVIDENCE_BY_CATEGORY",
    "SCORE_VERSION_V1",
    "SCORE_VERSION_V2",
    "SCORE_VERSION_VALUES",
    "SEVERITY_MULTIPLIERS",
]
