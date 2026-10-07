"""Governed WBS change rules for edit / submit / approve = apply (PC-2a.2 #896, ADR-029).

Pure domain rules on top of the PC-2a.1 contracts (``governance.py``): the dispositions of
identities that leave the WBS, the dense sibling order the live tree is written in, and the
complete submit validation. No I/O here; the application service enforces them inside one
transaction and the database guards re-check the critical ones.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from src.wbs.domain.digest import normalize_profile_ref
from src.wbs.domain.governance import (
    CandidateNode,
    CandidateOriginKind,
    GovernanceRuleError,
    LineageEdge,
    LineageKind,
    validate_for_submit,
)

MAX_EVIDENCE_REF_LENGTH = 500


class RetirementDisposition(StrEnum):
    """Why an identity leaves the WBS. Retired ids are never reused."""

    REMOVED = "REMOVED"
    SPLIT = "SPLIT"
    MERGED = "MERGED"
    SUPERSEDED = "SUPERSEDED"
    # First baseline only: a legacy live row the reviewed candidate does not adopt.
    RETIRED_ON_BASELINE = "RETIRED_ON_BASELINE"


class RetirementSource(StrEnum):
    BASELINE = "baseline"
    LEGACY = "legacy"


LINEAGE_DISPOSITION: Mapping[LineageKind, RetirementDisposition] = {
    LineageKind.SPLIT: RetirementDisposition.SPLIT,
    LineageKind.MERGE: RetirementDisposition.MERGED,
    LineageKind.SUPERSEDES: RetirementDisposition.SUPERSEDED,
}


@dataclass(frozen=True)
class Retirement:
    node_id: UUID
    disposition: RetirementDisposition | str
    source: RetirementSource | str


def dense_order_violations(nodes: Sequence[CandidateNode]) -> list[str]:
    """Siblings must be ordered 1..n with no gaps: the live tree is written exactly as approved."""
    siblings: dict[UUID | None, list[int]] = defaultdict(list)
    for node in nodes:
        siblings[node.parent_id].append(node.sort_order)
    violations = []
    for parent, orders in siblings.items():
        if sorted(orders) != list(range(1, len(orders) + 1)):
            where = "top level" if parent is None else f"children of {parent}"
            violations.append(f"sibling sort_order of the {where} must be 1..{len(orders)}, got {sorted(orders)}")
    return violations


def normalize_evidence_refs(refs: Iterable[str]) -> list[str]:
    """Evidence references are opaque, non-empty strings; order and duplicates do not matter."""
    normalized: set[str] = set()
    for ref in refs:
        if not isinstance(ref, str) or not ref.strip():
            raise GovernanceRuleError("evidence references must be non-empty strings")
        if len(ref) > MAX_EVIDENCE_REF_LENGTH:
            raise GovernanceRuleError(f"an evidence reference is longer than {MAX_EVIDENCE_REF_LENGTH} characters")
        normalized.add(ref.strip())
    return sorted(normalized)


def validate_governed_submission(
    nodes: Sequence[CandidateNode],
    lineage: Sequence[LineageEdge],
    retirements: Sequence[Retirement],
    *,
    base_node_ids: frozenset[UUID] | None,
    legacy_node_ids: frozenset[UUID] = frozenset(),
    legacy_complete: bool = False,
    profile_refs: Sequence[Mapping[str, object]] = (),
    profile_terms: Mapping[str, frozenset[str]] | None = None,
) -> list[str]:
    """Every reason a candidate cannot be submitted or applied (empty list = valid).

    ``base_node_ids`` is the base baseline (``None`` for a first baseline, which may adopt and
    retire ``legacy_node_ids`` instead). ``legacy_complete`` requires every legacy live row to
    be adopted or retired -- true once submit has recorded the RETIRED_ON_BASELINE set.
    ``profile_terms`` maps each namespace of a pinned, resolved Domain Profile to the terms its
    exact pinned version declares (ADR-029: a non-core ``decomposition_kind`` must come from one).
    """
    violations = validate_for_submit(nodes, lineage)
    violations += dense_order_violations(nodes)
    candidate = {node.node_id: node for node in nodes}
    retired = {retirement.node_id: retirement for retirement in retirements}
    if len(retired) != len(retirements):
        violations.append("a WBS identity is retired more than once")
    for node_id in sorted(set(candidate) & set(retired), key=str):
        violations.append(f"{node_id}: a retired identity cannot stay in the candidate")

    # Lineage: every source leaves the candidate with the matching disposition.
    kinds_by_source: dict[UUID, set[str]] = defaultdict(set)
    targets_by_source: dict[UUID, set[UUID]] = defaultdict(set)
    sources_by_merge_target: dict[UUID, set[UUID]] = defaultdict(set)
    for edge in lineage:
        kind = LineageKind(edge.kind)
        kinds_by_source[edge.source_node_id].add(kind.value)
        targets_by_source[edge.source_node_id].add(edge.target_node_id)
        if kind is LineageKind.MERGE:
            sources_by_merge_target[edge.target_node_id].add(edge.source_node_id)
        if edge.source_node_id in candidate:
            violations.append(f"lineage source {edge.source_node_id} must leave the candidate")
        source_retirement = retired.get(edge.source_node_id)
        if (source_retirement is None
                or RetirementDisposition(source_retirement.disposition) is not LINEAGE_DISPOSITION[kind]):
            violations.append(
                f"lineage source {edge.source_node_id} needs a {LINEAGE_DISPOSITION[kind].value} disposition")
    for source, kinds in kinds_by_source.items():
        if len(kinds) > 1:
            violations.append(f"lineage source {source} cannot be both {' and '.join(sorted(kinds))}")
        if kinds == {LineageKind.SPLIT.value} and len(targets_by_source[source]) < 2:
            violations.append(f"a split of {source} needs at least two targets")
    for target, sources in sources_by_merge_target.items():
        if len(sources) < 2:
            violations.append(f"a merge into {target} needs at least two sources")
    lineage_sources = set(kinds_by_source)
    for node_id, retirement in retired.items():
        disposition = RetirementDisposition(retirement.disposition)
        if disposition in LINEAGE_DISPOSITION.values() and node_id not in lineage_sources:
            violations.append(f"{node_id}: a {disposition.value} disposition needs its lineage")

    # Identity sources: a change of Baseline #N, or a first baseline over legacy rows.
    if base_node_ids is not None:
        for node in nodes:
            if node.origin_kind == CandidateOriginKind.ADOPTED_LEGACY:
                violations.append(f"{node.node_id}: only a first baseline adopts legacy rows")
            if node.origin_kind == CandidateOriginKind.EXISTING and node.node_id not in base_node_ids:
                violations.append(f"{node.node_id}: an existing identity must come from the base baseline")
        for node_id, retirement in retired.items():
            if RetirementSource(retirement.source) is not RetirementSource.BASELINE or node_id not in base_node_ids:
                violations.append(f"{node_id}: only identities of the base baseline can be retired")
        for node_id in sorted(base_node_ids - set(candidate) - set(retired), key=str):
            violations.append(f"{node_id}: retired id without disposition")
    else:
        for node in nodes:
            if node.origin_kind == CandidateOriginKind.EXISTING:
                violations.append(f"{node.node_id}: a first baseline has no base identities")
            if node.origin_kind == CandidateOriginKind.ADOPTED_LEGACY and node.node_id not in legacy_node_ids:
                violations.append(f"{node.node_id}: an adopted identity must be a legacy live row of the project")
        for node_id, retirement in retired.items():
            if RetirementSource(retirement.source) is not RetirementSource.LEGACY or node_id not in legacy_node_ids:
                violations.append(f"{node_id}: a first baseline only retires legacy live rows of the project")
        if legacy_complete:
            for node_id in sorted(legacy_node_ids - set(candidate) - set(retired), key=str):
                violations.append(f"{node_id}: legacy row without disposition")

    for ref in profile_refs:
        try:
            normalize_profile_ref(ref)
        except (TypeError, ValueError) as exc:
            violations.append(f"invalid profile pin: {exc}")
    terms = profile_terms or {}
    for node in nodes:
        if node.decomposition_kind is None or node.decomposition_kind.startswith("core:"):
            continue
        namespace, _, term = node.decomposition_kind.partition(":")
        if namespace not in terms:
            violations.append(f"{node.node_id}: {node.decomposition_kind!r} needs a pinned profile owning "
                              f"the {namespace!r} namespace")
        elif term not in terms[namespace]:
            violations.append(f"{node.node_id}: the pinned {namespace} profile does not declare {term!r}")
    return violations


__all__ = [
    "LINEAGE_DISPOSITION",
    "MAX_EVIDENCE_REF_LENGTH",
    "Retirement",
    "RetirementDisposition",
    "RetirementSource",
    "dense_order_violations",
    "normalize_evidence_refs",
    "validate_governed_submission",
]
