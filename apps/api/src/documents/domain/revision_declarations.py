"""Revision-keyed declarations stored in ``documents.document_metadata`` survive stale writers.

A declaration (for example a budget's total) is a deterministic function of one immutable revision's
bytes, so any writer produces the same entry for the same revision key. The only way to lose data is
to DROP another revision's entry, which is what a whole-blob metadata write from a stale in-memory
copy does. ``union_revision_declarations`` re-adds, under the caller's own entries, whatever the
committed row already holds.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

STATED_TOTAL_BY_REVISION_KEY = "stated_total_by_revision"
REVISION_DECLARATION_KEYS: tuple[str, ...] = (STATED_TOTAL_BY_REVISION_KEY,)


def union_revision_declarations(
    new_metadata: Mapping[str, Any], committed_metadata: Mapping[str, Any] | None
) -> dict[str, Any]:
    """``new_metadata`` plus every committed revision entry it does not mention."""
    merged = dict(new_metadata)
    for key in REVISION_DECLARATION_KEYS:
        committed = (committed_metadata or {}).get(key)
        if not isinstance(committed, Mapping) or not committed:
            continue
        mine = merged.get(key)
        merged[key] = {**committed, **(mine if isinstance(mine, Mapping) else {})}
    return merged
