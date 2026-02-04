"""
Coherence categories and default category weights.

Refers to Suite ID: TS-UD-COH-CAT-001.
"""

from __future__ import annotations

from enum import Enum


class CoherenceCategory(str, Enum):
    """Canonical coherence categories used by score calculators."""

    SCOPE = "SCOPE"
    BUDGET = "BUDGET"
    QUALITY = "QUALITY"
    TECHNICAL = "TECHNICAL"
    LEGAL = "LEGAL"
    TIME = "TIME"


DEFAULT_CATEGORY_WEIGHTS: dict[CoherenceCategory, float] = {
    CoherenceCategory.SCOPE: 0.20,
    CoherenceCategory.BUDGET: 0.20,
    CoherenceCategory.QUALITY: 0.15,
    CoherenceCategory.TECHNICAL: 0.15,
    CoherenceCategory.LEGAL: 0.15,
    CoherenceCategory.TIME: 0.15,
}


def get_default_category_weights() -> dict[CoherenceCategory, float]:
    """Returns a copy so callers can customize without mutating defaults."""
    return dict(DEFAULT_CATEGORY_WEIGHTS)


def validate_category_weights(weights: dict[CoherenceCategory, float]) -> None:
    """Validates full category coverage and normalized weight sum."""
    missing = set(CoherenceCategory) - set(weights.keys())
    if missing:
        missing_values = ", ".join(sorted(category.value for category in missing))
        raise ValueError(f"Missing category weights: {missing_values}")

    total = sum(weights.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError("Category weights must sum to 1.0")
