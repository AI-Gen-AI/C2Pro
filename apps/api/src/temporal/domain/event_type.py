"""ProjectEvent type registry (ADR-015 / TASK-V3-015-03).

Known core types are data-only. Reserved namespaces are accepted so later
bounded contexts can persist events without this module processing them.
"""

from __future__ import annotations

KNOWN_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "revision.ingested",
        "graph.completed",
        "hitl.correction",
        "baseline.changed",
    }
)
RESERVED_EVENT_PREFIXES: tuple[str, ...] = ("procurement.", "stakeholder.")


def validate_event_type(value: str) -> str:
    if value in KNOWN_EVENT_TYPES:
        return value
    if any(value.startswith(prefix) for prefix in RESERVED_EVENT_PREFIXES):
        return value
    raise ValueError(f"Unknown ProjectEvent event_type: {value}")


__all__ = ["KNOWN_EVENT_TYPES", "RESERVED_EVENT_PREFIXES", "validate_event_type"]
