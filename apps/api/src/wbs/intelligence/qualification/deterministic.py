"""Deterministic ``wbs-qualification/v1`` qualification of a WBS tree (PC-2b.2 #921; no LLM).

Runs over the exact nodes of a DRAFT candidate, an approved baseline or an in-memory import
snapshot. Every dimension is reported exactly once:

* the availability matrix decides first -- alignment dimensions are NOT_EVALUATED with their reason
  ("Governed Schedule evidence unavailable" for the schedule mapping), AI-only dimensions are
  NOT_EVALUATED(``AI_QUALIFICATION_NOT_RUN``), an empty target is NOT_EVALUATED(``EMPTY_TARGET``);
* the structural dimensions are evaluated from the tree itself. A result is SUPPORTED only when
  the deterministic check actually ran over the nodes and found nothing -- never because an input
  is missing (no PASS-by-absence); what the check cannot see is stated in its summary;
* a semantic dimension this engine cannot judge (overlap) and per-node evidence coverage stay
  NOT_EVALUATED(``AI_QUALIFICATION_NOT_RUN``), even when the target carries evidence references;
* pinned Domain Profile heuristics are PROFILE_HEURISTIC findings (WARNING / AMBIGUOUS at most,
  attributed to their exact rule, never evidence and never documentary fact).

Findings aggregate one rule over all the nodes it hits (not one finding per node). Nothing here
edits a tree, proposes a change or decides anything.
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from src.wbs.intelligence.contracts.evidence import ProfileRuleRef
from src.wbs.intelligence.contracts.qualification import (
    NOT_EVALUATED_SUMMARY,
    AvailabilityContext,
    DimensionResult,
    NodeFinding,
    NotEvaluatedReason,
    QualificationDimension,
    QualificationMethod,
    QualificationReport,
    QualificationStatus,
    availability,
)
from src.wbs.intelligence.profiles.catalog import ResolvedProfileSet
from src.wbs.intelligence.profiles.heuristics import HeuristicNode, evaluate_heuristics
from src.wbs.intelligence.profiles.schema import (
    ControlLevelNesting,
    FanoutBounds,
    ForbiddenParentChildKinds,
    Heuristic,
    MaxDepth,
    RequiredDictionaryFields,
    SiblingKindHomogeneity,
)

DETERMINISTIC_ENGINE_VERSION = "wbs-deterministic-qualifier/v1"

D = QualificationDimension
S = QualificationStatus

# Dimensions with no deterministic part in v1: semantic judgement needs the evidence cross-check.
_SEMANTIC_ONLY = frozenset({D.OVERLAPPING_SCOPE, D.EVIDENCE_COVERAGE})
_HEURISTIC_DIMENSION: Mapping[type[Heuristic], QualificationDimension] = {
    MaxDepth: D.GRANULARITY,
    FanoutBounds: D.GRANULARITY,
    RequiredDictionaryFields: D.WORK_PACKAGE_READINESS,
    SiblingKindHomogeneity: D.DECOMPOSITION_CONSISTENCY,
    ForbiddenParentChildKinds: D.DECOMPOSITION_CONSISTENCY,
    ControlLevelNesting: D.CONTROLLABILITY,
}
_SEVERITY = {S.SUPPORTED: 0, S.WARNING: 1, S.AMBIGUOUS: 2, S.GAP: 3}


@dataclass(frozen=True)
class QualifierNode:
    node_id: UUID
    parent_id: UUID | None
    sort_order: int
    code: str | None
    name: str
    decomposition_kind: str | None = None
    control_level: str = "none"
    dictionary: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class DeterministicQualification:
    report: QualificationReport
    findings: tuple[NodeFinding, ...]


@dataclass(frozen=True)
class _Hit:
    status: QualificationStatus
    summary: str
    node_ids: tuple[UUID, ...]


class _Tree:
    def __init__(self, nodes: Sequence[QualifierNode]) -> None:
        self.nodes = list(nodes)
        self.by_id = {node.node_id: node for node in nodes}
        self.children: dict[UUID | None, list[QualifierNode]] = defaultdict(list)
        for node in nodes:
            self.children[node.parent_id].append(node)
        self.leaves = [node for node in nodes if not self.children.get(node.node_id)]

    def ancestors(self, node: QualifierNode) -> list[QualifierNode]:
        found, current, seen = [], node, {node.node_id}
        while current.parent_id is not None and current.parent_id in self.by_id and current.parent_id not in seen:
            current = self.by_id[current.parent_id]
            seen.add(current.node_id)
            found.append(current)
        return found


def _field(node: QualifierNode, key: str) -> Any:
    return (node.dictionary or {}).get(key)


def _ids(nodes: Sequence[QualifierNode]) -> tuple[UUID, ...]:
    return tuple(node.node_id for node in nodes)


def _normal(name: str) -> str:
    return " ".join(unicodedata.normalize("NFC", name).split()).casefold()


# ---------------------------------------------------------------------------- structural checks
def _duplicate_scope(tree: _Tree) -> tuple[list[_Hit], str]:
    hits = []
    codes: dict[str, list[QualifierNode]] = defaultdict(list)
    for node in tree.nodes:
        if node.code:
            codes[node.code].append(node)
    dup_codes = [n for group in codes.values() if len(group) > 1 for n in group]
    if dup_codes:
        hits.append(_Hit(S.GAP, "Duplicate WBS codes", _ids(dup_codes)))
    dup_names = []
    for siblings in tree.children.values():
        by_name: dict[str, list[QualifierNode]] = defaultdict(list)
        for node in siblings:
            by_name[_normal(node.name)].append(node)
        dup_names += [n for group in by_name.values() if len(group) > 1 for n in group]
    if dup_names:
        hits.append(_Hit(S.WARNING, "Sibling elements with the same name", _ids(dup_names)))
    return hits, (f"No duplicate codes or sibling names among {len(tree.nodes)} element(s) "
                  "(structural check; semantic duplication not evaluated)")


def _decomposition(tree: _Tree) -> tuple[list[_Hit], str]:
    missing = [node for node in tree.nodes if not node.decomposition_kind]
    hits = [_Hit(S.WARNING, "Decomposition kind not declared", _ids(missing))] if missing else []
    return hits, f"Every element of {len(tree.nodes)} declares its decomposition kind"


def _granularity(tree: _Tree) -> tuple[list[_Hit], str]:
    single = [node for node in tree.nodes if len(tree.children.get(node.node_id, [])) == 1]
    hits = [_Hit(S.WARNING, "An element with a single child adds no decomposition", _ids(single))] if single else []
    return hits, "No single-child decomposition"


def _controllability(tree: _Tree) -> tuple[list[_Hit], str]:
    accounts = [n for n in tree.nodes if n.control_level == "control_account"]
    hits = []
    if not accounts:
        hits.append(_Hit(S.WARNING, "No control account is designated", ()))
    orphan_packages = [n for n in tree.nodes if n.control_level == "work_package"
                       and not any(a.control_level == "control_account" for a in tree.ancestors(n))]
    if orphan_packages:
        hits.append(_Hit(S.GAP, "Work packages outside any control account", _ids(orphan_packages)))
    nested = [n for n in accounts if any(a.control_level == "control_account" for a in tree.ancestors(n))]
    if nested:
        hits.append(_Hit(S.WARNING, "Control accounts nested in control accounts", _ids(nested)))
    return hits, f"{len(accounts)} control account(s); every work package sits in exactly one control account"


def _leaf_check(key: str, status: QualificationStatus, missing_label: str, ok_label: str) -> Callable[
        [_Tree], tuple[list[_Hit], str]]:
    def check(tree: _Tree) -> tuple[list[_Hit], str]:
        missing = [leaf for leaf in tree.leaves if not _field(leaf, key)]
        hits = [_Hit(status, missing_label, _ids(missing))] if missing else []
        return hits, f"All {len(tree.leaves)} work package(s) (leaf elements) {ok_label}"
    return check


def _readiness(tree: _Tree) -> tuple[list[_Hit], str]:
    not_ready = [leaf for leaf in tree.leaves if not leaf.code or not _field(leaf, "scope_statement")]
    hits = [_Hit(S.GAP, "Work packages without a code or a scope statement", _ids(not_ready))] if not_ready else []
    return hits, f"All {len(tree.leaves)} work package(s) (leaf elements) have a code and a scope statement"


def _boundary(tree: _Tree) -> tuple[list[_Hit], str]:
    unclear = [leaf for leaf in tree.leaves if not _field(leaf, "scope_included") and not _field(leaf, "scope_excluded")]
    hits = [_Hit(S.WARNING, "Work packages without included or excluded scope", _ids(unclear))] if unclear else []
    return hits, f"All {len(tree.leaves)} work package(s) (leaf elements) state included or excluded scope"


def _presence(key: str, label: str) -> Callable[[_Tree], tuple[list[_Hit], str]]:
    def check(tree: _Tree) -> tuple[list[_Hit], str]:
        present = [node for node in tree.nodes if _field(node, key)]
        hits = [] if present else [_Hit(S.WARNING, f"No {label} recorded", ())]
        return hits, f"{label.capitalize()} recorded on {len(present)} element(s) (presence and structure only)"
    return check


_CHECKS: Mapping[QualificationDimension, Callable[[_Tree], tuple[list[_Hit], str]]] = {
    D.DUPLICATE_SCOPE: _duplicate_scope,
    D.DECOMPOSITION_CONSISTENCY: _decomposition,
    D.GRANULARITY: _granularity,
    D.CONTROLLABILITY: _controllability,
    D.WORK_PACKAGE_READINESS: _readiness,
    D.DELIVERABLE_DEFINITION: _leaf_check("deliverables", S.WARNING, "Work packages without deliverables",
                                          "name their deliverables"),
    D.ACCEPTANCE_CRITERIA: _leaf_check("acceptance_criteria", S.WARNING, "Work packages without acceptance criteria",
                                       "state acceptance criteria"),
    D.SCOPE_BOUNDARY_CLARITY: _boundary,
    D.INTERFACES: _presence("interface_notes", "interface notes"),
    D.ASSUMPTIONS: _presence("assumptions", "assumptions"),
}


# ---------------------------------------------------------------------------- report
def _not_evaluated(dimension: QualificationDimension, reason: NotEvaluatedReason, summary: str | None = None
                   ) -> DimensionResult:
    return DimensionResult(dimension=dimension, status=S.NOT_EVALUATED, method=QualificationMethod.DETERMINISTIC,
                           summary=summary or NOT_EVALUATED_SUMMARY[reason], reason_code=reason)


def qualify(
    nodes: Sequence[QualifierNode],
    *,
    profiles: ResolvedProfileSet,
    evidence_ref_count: int,
    mint: Callable[[], UUID] = uuid4,
) -> DeterministicQualification:
    """Qualify ``nodes`` deterministically: the complete report plus its node findings."""
    tree = _Tree(nodes)
    matrix = availability(AvailabilityContext(
        has_trusted_contract=False, has_trusted_scope_evidence=False, ai_qualification_run=False,
        target_is_empty=not nodes))
    heuristic_hits: dict[QualificationDimension, list[tuple[_Hit, ProfileRuleRef]]] = defaultdict(list)
    if nodes:
        rules = dict(profiles.heuristics())
        heuristic_nodes = [HeuristicNode(n.node_id, n.parent_id, n.decomposition_kind, n.control_level, n.dictionary)
                           for n in nodes]
        for result in evaluate_heuristics(heuristic_nodes, profiles):
            if result.status == "INFO":
                continue  # advisory information never becomes a finding
            ref = ProfileRuleRef(profile_id=result.rule.profile_id, profile_version=result.rule.profile_version,
                                 profile_digest=result.rule.profile_digest, rule_id=result.rule.rule_id)
            dimension = _HEURISTIC_DIMENSION[type(rules[result.rule])]
            heuristic_hits[dimension].append((_Hit(S(result.status), result.message, result.node_ids), ref))

    results: list[DimensionResult] = []
    findings: list[NodeFinding] = []
    for dimension in QualificationDimension:
        reason = matrix[dimension]
        if reason is not None:
            results.append(_not_evaluated(dimension, reason))
            continue
        if dimension in _SEMANTIC_ONLY:
            summary = None
            if dimension is D.EVIDENCE_COVERAGE:
                summary = (f"{evidence_ref_count} evidence reference(s) attached to the target; "
                           "per-element evidence cross-check not run")
            results.append(_not_evaluated(dimension, NotEvaluatedReason.AI_QUALIFICATION_NOT_RUN, summary))
            continue
        hits, ok_summary = _CHECKS[dimension](tree)
        for hit in hits:
            findings.append(NodeFinding(finding_id=mint(), dimension=dimension, status=hit.status,
                                        method=QualificationMethod.DETERMINISTIC, summary=hit.summary,
                                        node_ids=hit.node_ids))
        for hit, ref in heuristic_hits.get(dimension, []):
            findings.append(NodeFinding(finding_id=mint(), dimension=dimension, status=hit.status,
                                        method=QualificationMethod.PROFILE_HEURISTIC, summary=hit.summary,
                                        node_ids=hit.node_ids, profile_rule_refs=(ref,)))
        results.append(_dimension_result(dimension, hits, heuristic_hits.get(dimension, []), ok_summary))
    return DeterministicQualification(report=QualificationReport(results=tuple(results)), findings=tuple(findings))


def _dimension_result(dimension: QualificationDimension, hits: list[_Hit],
                      heuristics: list[tuple[_Hit, ProfileRuleRef]], ok_summary: str) -> DimensionResult:
    worst_det = max((h.status for h in hits), key=_SEVERITY.__getitem__, default=S.SUPPORTED)
    worst_heur = max((h.status for h, _ in heuristics), key=_SEVERITY.__getitem__, default=S.SUPPORTED)
    node_ids = tuple(dict.fromkeys(node_id for h in hits for node_id in h.node_ids)
                     ) + tuple(dict.fromkeys(node_id for h, _ in heuristics for node_id in h.node_ids))
    node_ids = tuple(dict.fromkeys(node_ids))
    if _SEVERITY[worst_heur] > _SEVERITY[worst_det]:
        rules = tuple(dict.fromkeys(ref for _, ref in heuristics))
        summary = "; ".join(dict.fromkeys(h.summary for h, _ in heuristics))
        return DimensionResult(dimension=dimension, status=worst_heur, method=QualificationMethod.PROFILE_HEURISTIC,
                               summary=_clip(f"Profile heuristic: {summary}"), profile_rule_refs=rules,
                               node_ids=node_ids)
    summary = ok_summary if worst_det is S.SUPPORTED else "; ".join(dict.fromkeys(h.summary for h in hits))
    return DimensionResult(dimension=dimension, status=worst_det, method=QualificationMethod.DETERMINISTIC,
                           summary=_clip(summary), node_ids=node_ids)


def _clip(text: str) -> str:
    return text if len(text) <= 1000 else text[:997] + "..."


__all__ = ["DETERMINISTIC_ENGINE_VERSION", "DeterministicQualification", "QualifierNode", "qualify"]
