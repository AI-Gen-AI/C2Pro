"""
Ranking, dedup, and suppress for ActionItems (ADR-019).

Pure function — no I/O, no state. Score = severity × confidence × |impact_area|.
Ties broken by item.id for deterministic output across re-runs.
"""

from __future__ import annotations

from uuid import UUID

from src.action_review.domain.action_item import ActionItem, ActionStatus, Severity

_SEVERITY_WEIGHT: dict[Severity, int] = {
    Severity.CRITICAL: 5,
    Severity.HIGH: 4,
    Severity.MEDIUM: 3,
    Severity.LOW: 2,
    Severity.INFO: 1,
}


def _score(item: ActionItem) -> float:
    return _SEVERITY_WEIGHT[item.severity] * item.confidence * max(len(item.impact_area), 1)


def rank(
    items: list[ActionItem],
    *,
    prior_run_ids: frozenset[UUID] | None = None,
    pending_co_ids: frozenset[UUID] | None = None,
    top_n: int | None = None,
) -> list[ActionItem]:
    """
    Return ActionItems ranked by severity×confidence×|impact_area|, descending.

    Suppresses:
    - Items with status SUPPRESSED
    - Items whose ID is in prior_run_ids (unchanged across runs → no re-notify)
    - Items whose ID is in pending_co_ids (under a pending change order)
    - Duplicate IDs within the same batch (first occurrence kept)

    Tie-breaking by item.id ensures stable order across re-runs.
    """
    prior = prior_run_ids or frozenset()
    pending = pending_co_ids or frozenset()

    seen: set[UUID] = set()
    eligible: list[ActionItem] = []
    for item in items:
        if item.status == ActionStatus.SUPPRESSED:
            continue
        if item.id in prior or item.id in pending or item.id in seen:
            continue
        seen.add(item.id)
        eligible.append(item)

    eligible.sort(key=lambda i: (-_score(i), str(i.id)))

    if top_n is not None:
        return eligible[:top_n]
    return eligible


__all__ = ["rank"]
