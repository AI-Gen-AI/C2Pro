"""Deterministic partition of a review target into bounded clusters (one MAP call each).

Top-level branches are taken in sibling order and packed together while they fit
``max_nodes``; a branch larger than that is cut into consecutive windows of its depth-first
order (parents before children, siblings in order). Cluster ids are ``c01``, ``c02``, ... and depend
only on the target structure, never on the model.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from src.wbs.intelligence.validation.simulation import SnapshotNode, TargetSnapshot


@dataclass(frozen=True)
class Cluster:
    cluster_id: str
    node_ids: tuple[UUID, ...]  # depth-first order

    @property
    def members(self) -> frozenset[UUID]:
        return frozenset(self.node_ids)


def _children(snapshot: TargetSnapshot) -> dict[UUID | None, list[SnapshotNode]]:
    children: dict[UUID | None, list[SnapshotNode]] = defaultdict(list)
    for node in snapshot.nodes:
        children[node.parent_id].append(node)
    for siblings in children.values():
        siblings.sort(key=lambda n: (n.sort_order, str(n.node_id)))
    return children


def _depth_first(root: SnapshotNode, children: dict[UUID | None, list[SnapshotNode]]) -> list[UUID]:
    order: list[UUID] = []
    stack = [root]
    while stack:
        node = stack.pop()
        order.append(node.node_id)
        stack.extend(reversed(children.get(node.node_id, [])))
    return order


def partition(snapshot: TargetSnapshot, *, max_nodes: int) -> list[Cluster]:
    if max_nodes < 1:
        raise ValueError("max_nodes must be positive")
    children = _children(snapshot)
    groups: list[list[UUID]] = []
    pack: list[UUID] = []
    for root in children.get(None, []):
        branch = _depth_first(root, children)
        if len(branch) > max_nodes:
            if pack:
                groups.append(pack)
                pack = []
            groups.extend(branch[i:i + max_nodes] for i in range(0, len(branch), max_nodes))
        elif len(pack) + len(branch) > max_nodes:
            groups.append(pack)
            pack = list(branch)
        else:
            pack.extend(branch)
    if pack:
        groups.append(pack)
    return [Cluster(cluster_id=f"c{index:02d}", node_ids=tuple(group)) for index, group in enumerate(groups, start=1)]


__all__ = ["Cluster", "partition"]
