"""Treat related contract/budget detectors as one financial score impact.

The event/alert ledger retains two rule codes. Only the numeric penalty
collapses when the same original budget source row and both totals match.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable

from src.coherence.models import FindingSignal

_RULES = frozenset({"DET-CRS-CONBUD", "DET-CRS-NEGMARGIN"})


def _key(s: FindingSignal) -> tuple[float, float, str, str, str] | None:
    if s.rule_id not in _RULES:
        return None
    data = s.raw_data
    a, b = data.get("contract_total"), data.get("budget_total")
    if any(
        isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v)
        for v in (a, b)
    ):
        return None
    evidence = data.get("evidence")
    refs = evidence.get("sources") if isinstance(evidence, dict) else None
    if not isinstance(refs, list) or len(refs) != 1:
        return None
    ref = refs[0]
    if not isinstance(ref, dict) or ref.get("family") != "budget":
        return None
    parts = [ref.get(name) for name in ("document_id", "revision_id", "source_locator")]
    if not all(isinstance(v, str) and v.strip() for v in parts):
        return None
    return (float(a), float(b), parts[0], parts[1], parts[2])


def economic_discrepancy_key(signal: FindingSignal) -> str | None:
    """Stable, non-authoritative grouping ID for two views of one economic fact."""
    key = _key(signal)
    if key is None:
        return None
    canonical = json.dumps(key, separators=(",", ":"))
    return "CONTRACT_BUDGET:" + hashlib.sha256(canonical.encode()).hexdigest()


def distinct_economic_impacts(
    signals: list[FindingSignal],
    contribution: Callable[[FindingSignal], float],
) -> list[FindingSignal]:
    """Suppress one penalty per matching rule pair, never hide the two alerts."""
    groups: dict[tuple[float, float, str, str, str], dict[str, list[int]]] = {}
    for i, signal in enumerate(signals):
        key = _key(signal)
        if key is not None:
            groups.setdefault(key, {}).setdefault(signal.rule_id, []).append(i)
    skip: set[int] = set()
    for group in groups.values():
        for a, b in zip(
            group.get("DET-CRS-CONBUD", []), group.get("DET-CRS-NEGMARGIN", []), strict=False
        ):
            skip.add(a if contribution(signals[a]) <= contribution(signals[b]) else b)
    return [signal for i, signal in enumerate(signals) if i not in skip]
