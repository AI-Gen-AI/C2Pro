"""Dependency-safe human selection of proposal items (planning only; applying is PC-2b.2).

A human applies explicitly selected items. A selection is accepted only when:

* every selected item exists in the run and none was rejected by the human;
* a prerequisite already applied by a human (``satisfied``) counts as present: it is never
  re-applied, and its local labels are resolved to the ids it minted before planning;
* its whole prerequisite closure is EXPLICITLY selected -- hidden prerequisites are never
  auto-accepted: a refusal names the required closure so it can be shown before confirmation;
* no prerequisite (direct or transitive) was rejected -- that makes the dependant non-applicable;
* the prerequisite graph is acyclic;
* every item still matches the current candidate (per-node fingerprints, plus the child sets a
  SPLIT or MERGE takes over) -- otherwise CONFLICT;
* the whole selection simulates cleanly on the current candidate, in dependency order.

Anything else refuses the WHOLE selection: application is all-or-nothing.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from uuid import UUID

from src.wbs.intelligence.contracts.proposal import ModelProposalItem, ProposalItem
from src.wbs.intelligence.validation.simulation import (
    SimulatedTree,
    SimulationError,
    TargetSnapshot,
)


@dataclass(frozen=True)
class SelectionPlan:
    ordered_item_ids: tuple[UUID, ...]
    created_labels: tuple[str, ...]
    tree: SimulatedTree | None = field(default=None, compare=False)  # the simulated result (a read model)


@dataclass(frozen=True)
class SelectionRefusal:
    reasons: tuple[str, ...]
    required_missing: frozenset[UUID] = frozenset()
    blocked_by_rejected: frozenset[UUID] = frozenset()
    conflicts: frozenset[UUID] = frozenset()


@dataclass
class _Walk:
    order: list[UUID] = field(default_factory=list)
    cycle: list[UUID] | None = None


def dependency_closure(items: Mapping[UUID, ProposalItem], selected: Collection[UUID]) -> frozenset[UUID]:
    """Every transitive prerequisite of the selected items (the selected items excluded)."""
    found: set[UUID] = set()
    frontier = [dep for item_id in selected if item_id in items for dep in items[item_id].depends_on]
    while frontier:
        current = frontier.pop()
        if current in found:
            continue
        found.add(current)
        if current in items:
            frontier += list(items[current].depends_on)
    return frozenset(found - set(selected))


def _order(items: Mapping[UUID, ProposalItem], selected: Collection[UUID]) -> _Walk:
    walk = _Walk()
    state: dict[UUID, str] = {}

    def visit(item_id: UUID, path: list[UUID]) -> None:
        if walk.cycle is not None or state.get(item_id) == "done":
            return
        if state.get(item_id) == "active":
            walk.cycle = path[path.index(item_id):] + [item_id]
            return
        state[item_id] = "active"
        for dep in sorted(items[item_id].depends_on, key=str):
            if dep in items:
                visit(dep, path + [item_id])
        state[item_id] = "done"
        walk.order.append(item_id)

    for item_id in sorted(selected, key=str):
        visit(item_id, [])
    return walk


def plan_selection(
    *,
    items: Sequence[ProposalItem],
    selected: Collection[UUID],
    rejected: Collection[UUID],
    current: TargetSnapshot | None,
    kind_terms: Mapping[str, frozenset[str]],
    satisfied: Collection[UUID] = (),
) -> SelectionPlan | SelectionRefusal:
    by_id = {item.item_id: item for item in items}
    chosen = set(selected)
    done = set(satisfied)
    unknown = chosen - set(by_id)
    if unknown:
        return SelectionRefusal(reasons=(f"unknown proposal item(s) {sorted(map(str, unknown))}",))
    reasons: list[str] = []
    rejected_set = set(rejected)
    if chosen & done:
        reasons.append("an item already applied cannot be applied again")
    if chosen & rejected_set:
        reasons.append("a rejected item cannot be applied")
    closure = dependency_closure({k: v for k, v in by_id.items() if k not in done}, chosen) - done
    blocked = frozenset(dep for dep in closure | chosen if dep in rejected_set)
    if blocked:
        reasons.append("a prerequisite was rejected: its dependants are not applicable")
    missing = frozenset(closure - chosen - rejected_set)
    if missing:
        reasons.append("select the required prerequisites explicitly (they are never auto-accepted)")
    walk = _order({k: v for k, v in by_id.items() if k not in done}, (chosen | closure) - done)
    if walk.cycle is not None:
        reasons.append("the proposal items form a dependency cycle")
    conflicts = frozenset(
        item_id for item_id in chosen
        if any((current.fingerprint_of(key) if current else None) != digest
               for key, digest in by_id[item_id].target_fingerprints.items())
    )
    if conflicts:
        reasons.append("the candidate changed under these items since the run (CONFLICT): re-run or edit by hand")
    if reasons:
        return SelectionRefusal(reasons=tuple(reasons), required_missing=missing, blocked_by_rejected=blocked,
                                conflicts=conflicts)

    ordered = [item_id for item_id in walk.order if item_id in chosen]
    tree = SimulatedTree.of(current, kind_terms)
    try:
        for item_id in ordered:
            stored = by_id[item_id]
            tree.apply(ModelProposalItem.model_validate({
                **stored.payload, "ref": stored.ref, "operation": stored.operation, "rationale": stored.rationale,
                "confidence_pct": stored.confidence_pct}))
    except SimulationError as exc:
        return SelectionRefusal(reasons=(f"the selection does not apply cleanly: {exc}",))
    labels = tuple(label for item_id in ordered for label in by_id[item_id].creates_labels)
    return SelectionPlan(ordered_item_ids=tuple(ordered), created_labels=labels, tree=tree)


__all__ = ["SelectionPlan", "SelectionRefusal", "dependency_closure", "plan_selection"]
