"""ProjectEvent type registry (ADR-015 / TASK-V3-015-03).

Known core types are data-only. Reserved namespaces are accepted so later
bounded contexts can persist events without this module processing them.
"""

from __future__ import annotations

KNOWN_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "revision.ingested",
        "revision.changed",
        "revision.analyzed",
        "revision.analysis_failed",
        "revision.reinterpreted",
        # Lane C / C3b-2: the CURRENT matcher re-run over an earlier comparison's
        # immutable snapshots; append-only, provenance.recomputed_from_event_id.
        "revision.recomputed",
        # C2PRO P0b crash-safe resume V3: N17 durably persisting an analysis
        # and the graph reaching its terminal state are DIFFERENT facts. N17
        # emits analysis.persisted; only a verified terminal checkpoint emits
        # graph.completed. Conflating them let a mid-graph crash look like a
        # completed run.
        "analysis.persisted",
        "graph.completed",
        "hitl.correction",
        # Lane C / C3b-1: append-only evidence that an approved artifact's
        # canonical state became durable (idempotency lives in the DB, not here).
        "materialization.completed",
        "baseline.changed",
        # PC-2a.2 (#896, ADR-029): governed WBS workflow. One applied event binds the change set
        # AND the resulting baseline (no duplicate change/baseline events).
        "wbs.change.submitted",
        "wbs.change.rejected",
        "wbs.baseline.applied",
        # PC-2b.2 (#921, ADR-030): WBS intelligence audit facts -- never WBS authority. A run reached
        # a terminal state; a human decided one item (an applied item names the DRAFT it went into).
        "wbs.intelligence.run_completed",
        "wbs.intelligence.item_decided",
        # PC-2b.4 (#923): model-call usage of one intelligence run, attributed to tenant, project and
        # run -- counts only, never prompts, evidence or output (offline runs are marked synthetic).
        "wbs.intelligence.run_usage",
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
