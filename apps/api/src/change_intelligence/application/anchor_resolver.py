"""Clause anchor resolver for ADR-016 L1 structural diff.

TS-UT-CI-ANCH-001
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from src.documents.domain.models import Clause

_NEEDS_REVIEW_CONFIDENCE = 0.9


@dataclass(frozen=True)
class AnchorMatch:
    old: Clause
    new: Clause
    anchor: str
    match_confidence: float
    needs_review: bool


@dataclass(frozen=True)
class AnchorResolution:
    matched: list[AnchorMatch]
    unmatched_old: list[Clause]
    unmatched_new: list[Clause]


def _normalize_text(text: str | None) -> str:
    return " ".join((text or "").split())


def _ratio(old: Clause, new: Clause) -> float:
    old_text = _normalize_text(old.full_text)
    new_text = _normalize_text(new.full_text)
    if not old_text and not new_text:
        return 0.0
    return SequenceMatcher(a=old_text, b=new_text).ratio()


def resolve_clause_anchors(
    old: list[Clause],
    new: list[Clause],
    *,
    fuzzy_threshold: float = 0.8,
) -> AnchorResolution:
    """Pair clauses by stable clause_code, then by one-to-one fuzzy text match."""

    matched: list[AnchorMatch] = []
    unmatched_old: list[Clause] = []
    unmatched_new_by_index = dict(enumerate(new))

    new_by_code = {clause.clause_code: (index, clause) for index, clause in enumerate(new)}
    for old_clause in old:
        exact = new_by_code.get(old_clause.clause_code)
        if exact is None:
            unmatched_old.append(old_clause)
            continue
        new_index, new_clause = exact
        if new_index in unmatched_new_by_index:
            matched.append(
                AnchorMatch(
                    old=old_clause,
                    new=new_clause,
                    anchor=old_clause.clause_code,
                    match_confidence=1.0,
                    needs_review=False,
                )
            )
            del unmatched_new_by_index[new_index]
        else:
            unmatched_old.append(old_clause)

    candidates: list[tuple[float, int, int, Clause, Clause]] = []
    for old_index, old_clause in enumerate(unmatched_old):
        for new_index, new_clause in unmatched_new_by_index.items():
            confidence = _ratio(old_clause, new_clause)
            if confidence >= fuzzy_threshold:
                candidates.append((confidence, old_index, new_index, old_clause, new_clause))

    used_old: set[int] = set()
    used_new: set[int] = set()
    for confidence, old_index, new_index, old_clause, new_clause in sorted(
        candidates,
        key=lambda item: item[0],
        reverse=True,
    ):
        if old_index in used_old or new_index in used_new:
            continue
        matched.append(
            AnchorMatch(
                old=old_clause,
                new=new_clause,
                anchor=old_clause.clause_code,
                match_confidence=confidence,
                needs_review=confidence < _NEEDS_REVIEW_CONFIDENCE,
            )
        )
        used_old.add(old_index)
        used_new.add(new_index)

    remaining_old = [clause for index, clause in enumerate(unmatched_old) if index not in used_old]
    remaining_new = [
        clause for index, clause in unmatched_new_by_index.items() if index not in used_new
    ]
    return AnchorResolution(
        matched=matched,
        unmatched_old=remaining_old,
        unmatched_new=remaining_new,
    )


__all__ = ["AnchorMatch", "AnchorResolution", "resolve_clause_anchors"]
