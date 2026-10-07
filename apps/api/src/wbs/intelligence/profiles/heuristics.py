"""Deterministic evaluation of Domain Profile heuristics over a WBS tree (advisory only).

A violated heuristic is a WARNING (or INFO), attributed to its exact profile rule; a heuristic
that contradicts another pinned rule is AMBIGUOUS. A heuristic never yields a GAP, never edits
the tree and never blocks submission.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from src.wbs.intelligence.profiles.catalog import HeuristicRuleRef, ResolvedProfileSet
from src.wbs.intelligence.profiles.schema import (
    ControlLevelNesting,
    FanoutBounds,
    ForbiddenParentChildKinds,
    Heuristic,
    MaxDepth,
    RequiredDictionaryFields,
    SiblingKindHomogeneity,
)


@dataclass(frozen=True)
class HeuristicNode:
    node_id: UUID
    parent_id: UUID | None
    kind: str | None
    control_level: str
    dictionary: Mapping[str, Any] | None


@dataclass(frozen=True)
class HeuristicResult:
    rule: HeuristicRuleRef
    status: Literal["INFO", "WARNING", "AMBIGUOUS"]
    node_ids: tuple[UUID, ...]
    message: str


def _depths(nodes: Sequence[HeuristicNode]) -> dict[UUID, int]:
    by_id = {node.node_id: node for node in nodes}
    depths: dict[UUID, int] = {}
    for node in nodes:
        depth, current, seen = 1, node, {node.node_id}
        while current.parent_id is not None and current.parent_id in by_id and current.parent_id not in seen:
            current = by_id[current.parent_id]
            seen.add(current.node_id)
            depth += 1
        depths[node.node_id] = depth
    return depths


def _ancestors(nodes: Sequence[HeuristicNode], node: HeuristicNode) -> list[HeuristicNode]:
    by_id = {n.node_id: n for n in nodes}
    found, current, seen = [], node, {node.node_id}
    while current.parent_id is not None and current.parent_id in by_id and current.parent_id not in seen:
        current = by_id[current.parent_id]
        seen.add(current.node_id)
        found.append(current)
    return found


def _missing_fields(dictionary: Mapping[str, Any] | None, fields: Sequence[str]) -> bool:
    dictionary = dictionary or {}
    return any(not dictionary.get(field) for field in fields)


def _violations(rule: Heuristic, nodes: Sequence[HeuristicNode]) -> list[UUID]:
    children: dict[UUID | None, list[HeuristicNode]] = defaultdict(list)
    for node in nodes:
        children[node.parent_id].append(node)
    if isinstance(rule, MaxDepth):
        return [node_id for node_id, depth in _depths(nodes).items() if depth > rule.max]
    if isinstance(rule, FanoutBounds):
        hits = []
        for node in nodes:
            if rule.applies_to_kind and node.kind != rule.applies_to_kind:
                continue
            count = len(children.get(node.node_id, []))
            if count and ((rule.min is not None and count < rule.min) or (rule.max is not None and count > rule.max)):
                hits.append(node.node_id)
        return hits
    if isinstance(rule, RequiredDictionaryFields):
        return [n.node_id for n in nodes if n.control_level == rule.control_level and _missing_fields(n.dictionary, rule.fields)]
    if isinstance(rule, SiblingKindHomogeneity):
        hits = []
        for siblings in children.values():
            if len({s.kind for s in siblings if s.kind}) > 1:
                hits += [s.node_id for s in siblings]
        return hits
    if isinstance(rule, ForbiddenParentChildKinds):
        by_id = {n.node_id: n for n in nodes}
        return [n.node_id for n in nodes if n.kind == rule.child_kind and n.parent_id in by_id
                and by_id[n.parent_id].kind == rule.parent_kind]
    if isinstance(rule, ControlLevelNesting):
        if rule.allowed:
            return []  # a permission is never violated; it only matters as a contradiction
        return [n.node_id for n in nodes if n.control_level == rule.descendant
                and any(a.control_level == rule.ancestor for a in _ancestors(nodes, n))]
    raise TypeError(f"unknown heuristic predicate {type(rule).__name__}")  # pragma: no cover


def evaluate_heuristics(nodes: Sequence[HeuristicNode], profiles: ResolvedProfileSet) -> list[HeuristicResult]:
    contradicted = {ref for pair in profiles.contradictions() for ref in pair}
    results = []
    for ref, rule in profiles.heuristics():
        node_ids = _violations(rule, nodes)
        if not node_ids:
            continue
        status: Literal["INFO", "WARNING", "AMBIGUOUS"] = (
            "AMBIGUOUS" if ref in contradicted else ("WARNING" if rule.severity == "WARNING" else "INFO"))
        results.append(HeuristicResult(rule=ref, status=status, node_ids=tuple(node_ids), message=rule.message))
    return results


__all__ = ["HeuristicNode", "HeuristicResult", "evaluate_heuristics"]
