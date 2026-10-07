"""In-memory simulation of proposal items over an exact target snapshot.

Mirrors the PC-2a governed command semantics (ADD / UPDATE / RECODE / MOVE / REORDER / REMOVE /
SPLIT / MERGE) without touching any database: the validator uses it to reject items whose
application would be structurally invalid, and the selection planner uses it to prove a whole
human selection applies atomically. Snapshot nodes are keyed by their canonical id; nodes a
proposal creates are keyed by ``label:<local label>`` -- the server mints real ids only when a
human applies the item through the governed commands.
"""

from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any
from uuid import UUID

from src.wbs.domain.digest import DigestNode, canonical_json, normalize_dictionary, tree_digest
from src.wbs.domain.governance import (
    CORE_DECOMPOSITION_TERMS,
    DECOMPOSITION_KIND_PATTERN,
    ControlLevel,
)
from src.wbs.intelligence.contracts.proposal import (
    ModelNodeChanges,
    ModelNodeSpec,
    ModelProposalItem,
    ProposalOperation,
    TargetRef,
)

NODE_FINGERPRINT_VERSION = "wbs-node-fingerprint/v1"
_MAX_CODE, _MAX_NAME = 50, 255
_CONTROL_LEVELS = frozenset(level.value for level in ControlLevel)


class SimulationError(ValueError):
    """Applying an item would break a WBS structural rule."""


@dataclass(frozen=True)
class SnapshotNode:
    node_id: UUID
    parent_id: UUID | None
    sort_order: int
    code: str | None
    name: str
    decomposition_kind: str | None = None
    control_level: str = "none"
    dictionary: Mapping[str, Any] | None = None

    def digest_node(self) -> DigestNode:
        return DigestNode(node_id=self.node_id, parent_id=self.parent_id, sort_order=self.sort_order, code=self.code,
                          name=self.name, decomposition_kind=self.decomposition_kind,
                          control_level=self.control_level, dictionary=self.dictionary)


def node_fingerprint(node: SnapshotNode) -> str:
    """The node's governed content and position at run time (stale protection per item)."""
    body = {"version": NODE_FINGERPRINT_VERSION, "node_id": str(node.node_id),
            "parent_id": None if node.parent_id is None else str(node.parent_id), "sort_order": node.sort_order,
            "code": node.code, "name": node.name, "decomposition_kind": node.decomposition_kind,
            "control_level": node.control_level, "dictionary": normalize_dictionary(node.dictionary)}
    return "sha256:" + hashlib.sha256(canonical_json(body)).hexdigest()


@dataclass(frozen=True)
class TargetSnapshot:
    """The exact structure a run looked at (a candidate revision, a baseline or an import)."""

    project_id: UUID
    nodes: tuple[SnapshotNode, ...]

    @property
    def digest(self) -> str:
        return tree_digest(self.project_id, (node.digest_node() for node in self.nodes))

    def ids(self) -> frozenset[UUID]:
        return frozenset(node.node_id for node in self.nodes)

    def fingerprints(self) -> dict[UUID, str]:
        return {node.node_id: node_fingerprint(node) for node in self.nodes}


@dataclass
class _SimNode:
    key: str
    parent: str | None
    sort_order: int
    code: str | None
    name: str
    kind: str | None
    control_level: str
    dictionary: dict[str, Any] | None


def label_key(label: str) -> str:
    return f"label:{label}"


@dataclass
class SimulatedTree:
    kind_terms: Mapping[str, frozenset[str]]
    nodes: dict[str, _SimNode] = field(default_factory=dict)

    @classmethod
    def of(cls, snapshot: TargetSnapshot | None, kind_terms: Mapping[str, frozenset[str]]) -> SimulatedTree:
        tree = cls(kind_terms=kind_terms)
        for node in snapshot.nodes if snapshot else ():
            tree.nodes[str(node.node_id)] = _SimNode(
                key=str(node.node_id), parent=None if node.parent_id is None else str(node.parent_id),
                sort_order=node.sort_order, code=node.code, name=node.name, kind=node.decomposition_kind,
                control_level=node.control_level,
                dictionary=None if node.dictionary is None else dict(node.dictionary))
        return tree

    def copy(self) -> SimulatedTree:
        return SimulatedTree(kind_terms=self.kind_terms, nodes={k: replace(v) for k, v in self.nodes.items()})

    # ------------------------------------------------------------------ helpers
    def resolve(self, ref: TargetRef | None) -> str | None:
        if ref is None:
            return None
        key = str(ref.node_id) if ref.node_id is not None else label_key(ref.label or "")
        if key not in self.nodes:
            raise SimulationError(f"{'node ' + str(ref.node_id) if ref.node_id else 'label ' + str(ref.label)} "
                                  "is not in the target")
        return key

    def _children(self, key: str | None) -> list[_SimNode]:
        return sorted((n for n in self.nodes.values() if n.parent == key), key=lambda n: n.sort_order)

    def _subtree(self, key: str) -> set[str]:
        found, frontier = {key}, [key]
        while frontier:
            current = frontier.pop()
            for child in self._children(current):
                if child.key not in found:
                    found.add(child.key)
                    frontier.append(child.key)
        return found

    def _place(self, key: str, parent: str | None, position: int | None) -> None:
        siblings = [n for n in self._children(parent) if n.key != key]
        index = len(siblings) if position is None else min(max(position, 1), len(siblings) + 1) - 1
        siblings.insert(index, self.nodes[key])
        self.nodes[key].parent = parent
        for order, node in enumerate(siblings, start=1):
            node.sort_order = order

    def _renumber(self, parent: str | None) -> None:
        for order, node in enumerate(self._children(parent), start=1):
            node.sort_order = order

    def check_kind(self, kind: str | None) -> str | None:
        if kind is None:
            return None
        if not DECOMPOSITION_KIND_PATTERN.fullmatch(kind):
            raise SimulationError(f"decomposition_kind {kind!r} is not 'namespace:term'")
        namespace, term = kind.split(":", 1)
        if namespace == "core":
            if term not in CORE_DECOMPOSITION_TERMS:
                raise SimulationError(f"{kind!r} is not in the core vocabulary")
            return kind
        if namespace not in self.kind_terms:
            raise SimulationError(f"{kind!r} uses namespace {namespace!r} of no pinned profile")
        if term not in self.kind_terms[namespace]:
            raise SimulationError(f"{kind!r} is not declared by the pinned {namespace} profile")
        return kind

    @staticmethod
    def check_code(code: str | None) -> str | None:
        if code is None:
            return None
        code = unicodedata.normalize("NFC", code.strip())
        if not code or len(code) > _MAX_CODE:
            raise SimulationError(f"a WBS code is 1..{_MAX_CODE} characters")
        return code

    @staticmethod
    def check_name(name: str) -> str:
        name = unicodedata.normalize("NFC", name.strip())
        if not name or len(name) > _MAX_NAME:
            raise SimulationError(f"a WBS name is 1..{_MAX_NAME} characters")
        return name

    @staticmethod
    def check_control_level(level: str) -> str:
        if level not in _CONTROL_LEVELS:
            raise SimulationError(f"unknown control_level {level!r}")
        return level

    @staticmethod
    def check_dictionary(dictionary: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if dictionary is None:
            return None
        try:
            return normalize_dictionary(dictionary)
        except (TypeError, ValueError) as exc:
            raise SimulationError(f"invalid wbs-dictionary/v1: {exc}") from exc

    def _new(self, label: str | None, spec: ModelNodeSpec | None, parent: str | None, position: int | None) -> str:
        if label is None or spec is None:
            raise SimulationError("a created node needs a local label and a spec")
        key = label_key(label)
        if key in self.nodes:
            raise SimulationError(f"label {label!r} is created twice")
        self.nodes[key] = _SimNode(
            key=key, parent=parent, sort_order=0, code=self.check_code(spec.code), name=self.check_name(spec.name),
            kind=self.check_kind(spec.decomposition_kind), control_level=self.check_control_level(spec.control_level),
            dictionary=self.check_dictionary(spec.dictionary))
        self._place(key, parent, position)
        return key

    def _check_codes(self) -> None:
        seen: dict[str, str] = {}
        for node in self.nodes.values():
            if node.code is not None:
                if node.code in seen:
                    raise SimulationError(f"duplicate code {node.code!r}")
                seen[node.code] = node.key

    # ------------------------------------------------------------------ apply
    def apply(self, item: ModelProposalItem) -> None:  # noqa: C901 - one branch per governed command
        op = item.operation
        if op is ProposalOperation.ADD_NODE:
            self._new(item.creates_label, item.spec, self.resolve(item.parent), item.position)
        elif op is ProposalOperation.UPDATE_NODE:
            key = self.resolve(item.node)
            changes: ModelNodeChanges | None = item.changes
            if key is None or changes is None or not changes.model_dump(exclude_none=True):
                raise SimulationError("UPDATE_NODE names a node and at least one change")
            node = self.nodes[key]
            if changes.name is not None:
                node.name = self.check_name(changes.name)
            if changes.control_level is not None:
                node.control_level = self.check_control_level(changes.control_level)
            if changes.decomposition_kind is not None:
                node.kind = self.check_kind(changes.decomposition_kind)
            if changes.dictionary is not None:
                node.dictionary = self.check_dictionary(changes.dictionary)
        elif op is ProposalOperation.RECODE_NODE:
            key = self.resolve(item.node)
            if key is None or item.code is None:
                raise SimulationError("RECODE_NODE names a node and a code")
            self.nodes[key].code = self.check_code(item.code)
        elif op is ProposalOperation.MOVE_NODE:
            key = self.resolve(item.node)
            if key is None:
                raise SimulationError("MOVE_NODE names a node")
            parent = self.resolve(item.parent)
            if parent is not None and parent in self._subtree(key):
                raise SimulationError("a node cannot move under itself or its descendants")
            old = self.nodes[key].parent
            self._place(key, parent, item.position)
            if old != parent:
                self._renumber(old)
        elif op is ProposalOperation.REORDER_NODE:
            key = self.resolve(item.node)
            if key is None or item.position is None:
                raise SimulationError("REORDER_NODE names a node and a position")
            self._place(key, self.nodes[key].parent, item.position)
        elif op is ProposalOperation.REMOVE_NODE:
            key = self.resolve(item.node)
            if key is None:
                raise SimulationError("REMOVE_NODE names a node")
            if self._children(key):
                raise SimulationError("remove or move the children of a node before removing it")
            parent = self.nodes.pop(key).parent
            self._renumber(parent)
        elif op is ProposalOperation.SPLIT_NODE:
            self._split(item)
        elif op is ProposalOperation.MERGE_NODES:
            self._merge(item)
        else:  # pragma: no cover - exhaustive over ProposalOperation
            raise SimulationError(f"unknown operation {op}")
        self._check_codes()

    def _split(self, item: ModelProposalItem) -> None:
        source = self.resolve(item.node)
        if source is None or len(item.split_targets) < 2:
            raise SimulationError("SPLIT_NODE names a source and at least two targets")
        children = self._children(source)
        assigned = dict(item.child_targets)
        if {c.key for c in children} != set(assigned):
            raise SimulationError("every child of a split node is assigned to exactly one target")
        if any(not 0 <= index < len(item.split_targets) for index in assigned.values()):
            raise SimulationError("a child is assigned to a target that does not exist")
        parent, position = self.nodes[source].parent, self.nodes[source].sort_order
        targets = [self._new(t.label, t.spec, parent, position + i) for i, t in enumerate(item.split_targets)]
        for child in children:
            self._place(child.key, targets[assigned[child.key]], None)
        del self.nodes[source]
        self._renumber(parent)

    def _merge(self, item: ModelProposalItem) -> None:
        sources = [self.resolve(ref) for ref in item.sources]
        if len(sources) < 2 or len(set(sources)) != len(sources):
            raise SimulationError("MERGE_NODES names at least two distinct sources")
        keys = [key for key in sources if key is not None]
        parent = self.resolve(item.parent) if item.parent is not None else self.nodes[keys[0]].parent
        if parent is not None and any(parent in self._subtree(key) for key in keys):
            raise SimulationError("a merge target cannot sit under one of its sources")
        target = self._new(item.creates_label, item.spec, parent, item.position)
        for key in keys:
            for child in self._children(key):
                self._place(child.key, target, None)
        old_parents = {self.nodes[key].parent for key in keys}
        for key in keys:
            del self.nodes[key]
        for old in old_parents:
            self._renumber(old)

    def structural_violations(self) -> list[str]:
        problems = []
        for node in self.nodes.values():
            seen, current = {node.key}, node
            while current.parent is not None:
                if current.parent not in self.nodes:
                    problems.append(f"{node.key}: parent outside the tree")
                    break
                if current.parent in seen:
                    problems.append(f"{node.key}: parent cycle")
                    break
                seen.add(current.parent)
                current = self.nodes[current.parent]
        try:
            self._check_codes()
        except SimulationError as exc:
            problems.append(str(exc))
        return problems

    def names(self) -> list[str]:
        return [node.name for node in self.nodes.values()]


def apply_all(tree: SimulatedTree, items: Sequence[ModelProposalItem]) -> SimulatedTree:
    """Apply items in order on a copy; any failure raises (all-or-nothing)."""
    result = tree.copy()
    for item in items:
        result.apply(item)
    return result


__all__ = [
    "SimulatedTree",
    "SimulationError",
    "SnapshotNode",
    "TargetSnapshot",
    "apply_all",
    "label_key",
    "node_fingerprint",
]
