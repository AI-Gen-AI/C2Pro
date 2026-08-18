"""
Live canonical re-score (ADR-017 canary).

The canary flips only the SCORER, not detection (ADR-009 §F/§G.1): a canary-cohort
evaluation keeps v1's findings/alerts but re-derives the headline through the canonical
scorer + expert-calibrated envelope. This adapter turns a result's per-category
breakdown into that canonical headline.

Refers to Suite ID: TS-UA-COH-CANON-LIVE-RESCORE-001.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.coherence.canonical import (
    CategoryScore,
    CategoryScoreInput,
    ConflictInput,
    GlobalScoreInput,
    aggregate_global,
    score_category,
)
from src.coherence.canonical.category import Severity
from src.coherence.domain.v2_constants import DEFAULT_CATEGORY_WEIGHTS
from src.coherence.models import CategoryBreakdown, SeverityCount

# Clean baseline: a category starts coherent and is depressed only by its findings
# (matches the scorer-direct calibration; §G.1).
CLEAN_BASE = 100.0

# CategoryBreakdown.category uses the alert vocabulary; the canonical weights use the
# 6-dimension names. Normalise so aggregation lines up.
_CATEGORY_ALIAS = {"SCHEDULE": "TIME", "FINANCIAL": "BUDGET", "GENERAL": "SCOPE"}
_SEVERITY_RANK: dict[Severity, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass(frozen=True)
class CanonicalRescore:
    """The canonical headline for an existing result's findings."""

    score: float | None
    reason: str | None
    category_scores: dict[str, float | None]


def canonical_category_name(raw: str) -> str:
    """Normalise an alert-vocabulary category to a canonical 6-dimension name."""
    up = raw.upper()
    return _CATEGORY_ALIAS.get(up, up)


def _worst_severity(counts: SeverityCount) -> Severity | None:
    """Worst severity present in a category (info is advisory, not a scoring conflict)."""
    if counts.critical > 0:
        return "critical"
    if counts.high > 0:
        return "high"
    if counts.medium > 0:
        return "medium"
    if counts.low > 0:
        return "low"
    return None


def canonical_rescore(breakdowns: list[CategoryBreakdown]) -> CanonicalRescore:
    """Re-derive the headline from per-category findings via the canonical scorer + envelope.

    - `unassessed` categories stay null (null-not-zero); they do not fabricate a 100.
    - A category's worst finding drives its graduated score (base minus severity penalty).
    - The global critical-risk envelope caps the headline by the worst open finding.
    """
    category_scores: dict[str, CategoryScore] = {}
    worst_open: Severity | None = None
    for breakdown in breakdowns:
        category = canonical_category_name(str(breakdown.category))
        if breakdown.state == "unassessed":
            scored = score_category(CategoryScoreInput(base=CLEAN_BASE, assessed=False))
        else:
            severity = _worst_severity(breakdown.severity_breakdown)
            conflict = ConflictInput(severity=severity, certainty=1.0) if severity else None
            scored = score_category(CategoryScoreInput(base=CLEAN_BASE, conflict=conflict))
            if severity is not None and (
                worst_open is None or _SEVERITY_RANK[severity] > _SEVERITY_RANK[worst_open]
            ):
                worst_open = severity
        prior = category_scores.get(category)
        if _prefer(scored, prior):  # keep the worst on alias collision (e.g. financial+BUDGET)
            category_scores[category] = scored

    global_result = aggregate_global(
        GlobalScoreInput(
            category_scores=category_scores,
            category_weights=dict(DEFAULT_CATEGORY_WEIGHTS),
            worst_open_severity=worst_open,
        )
    )
    return CanonicalRescore(
        score=global_result.score,
        reason=global_result.reason,
        category_scores={cat: cs.score for cat, cs in category_scores.items()},
    )


def _prefer(candidate: CategoryScore, prior: CategoryScore | None) -> bool:
    """Prefer the lower (worse) assessed score when a canonical category appears twice."""
    if prior is None:
        return True
    if candidate.score is None:
        return False
    if prior.score is None:
        return True
    return candidate.score < prior.score


__all__ = ["CLEAN_BASE", "CanonicalRescore", "canonical_category_name", "canonical_rescore"]
