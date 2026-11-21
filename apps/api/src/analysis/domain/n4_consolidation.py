"""N4 candidate consolidation (JV1-A7): dedup across overlapping source windows.

Merge only when two candidates are in the same category AND either cite the same
clause or their source spans overlap by >= 50% of the shorter span. Candidates
carrying different figures are distinct facts and are never merged. Every merged
candidate keeps all ``source_keys`` and ``source_refs`` plus a trace of why.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_OVERLAP_THRESHOLD = 0.5
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def _spans(item: Mapping[str, Any]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for ref in item.get("source_refs") or []:
        span = ref.get("analysis_span") if isinstance(ref, Mapping) else None
        if isinstance(span, (list, tuple)) and len(span) == 2:
            try:
                start, end = int(span[0]), int(span[1])
            except (TypeError, ValueError):
                continue
            if end > start:
                out.append((start, end))
    return out


def _overlaps(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    for s1, e1 in _spans(a):
        for s2, e2 in _spans(b):
            inter = min(e1, e2) - max(s1, s2)
            if inter > 0 and inter / min(e1 - s1, e2 - s2) >= _OVERLAP_THRESHOLD:
                return True
    return False


def _clause(item: Mapping[str, Any]) -> str:
    return str(item.get("clause_ref") or "").strip().lower()


def _figures(item: Mapping[str, Any]) -> frozenset[str]:
    return frozenset(_NUMBER.findall(str(item.get("source_quote") or "")))


def _contradicts(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    fa, fb = _figures(a), _figures(b)
    return bool(fa and fb and fa != fb)


def _rule(a: Mapping[str, Any], b: Mapping[str, Any]) -> str | None:
    if str(a.get("category")) != str(b.get("category")):
        return None
    if _clause(a) and _clause(a) == _clause(b):
        return "same_clause"
    if _overlaps(a, b):
        return "span_overlap"
    return None


def consolidate_candidates(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return consolidated candidates in first-seen order (inputs not mutated)."""
    clusters: list[list[Mapping[str, Any]]] = []
    traces: list[list[dict[str, Any]]] = []
    for item in items:
        placed = False
        for members, trace in zip(clusters, traces, strict=True):
            if any(_contradicts(item, m) for m in members):
                continue
            rule = next((r for m in members if (r := _rule(m, item))), None)
            if rule:
                members.append(item)
                trace.append({
                    "rule": rule, "merged_key": item.get("finding_key"),
                    "into_key": members[0].get("finding_key"),
                })
                placed = True
                break
        if not placed:
            clusters.append([item])
            traces.append([])
    result: list[dict[str, Any]] = []
    for members, trace in zip(clusters, traces, strict=True):
        merged = dict(members[0])
        merged["source_keys"] = [m.get("finding_key") for m in members]
        merged["source_refs"] = [
            ref for m in members for ref in (m.get("source_refs") or [])
        ]
        merged["consolidation_trace"] = trace
        result.append(merged)
    return result
