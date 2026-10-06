"""PC-2a.2 (#896) governed change rules -- pure domain (TS-UT-PC2A2-WBS-DOMAIN-001)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.wbs.domain.governance import CandidateNode, GovernanceRuleError, LineageEdge
from src.wbs.domain.governed_change import (
    Retirement,
    dense_order_violations,
    normalize_evidence_refs,
    validate_governed_submission,
)

A, B, C, D, E = (uuid4() for _ in range(5))
PIN = {"profile_id": "solar-pv-epc", "profile_version": "1.0.0", "profile_digest": "sha256:" + "0" * 64}


def _node(node_id: UUID, sort_order: int, *, parent: UUID | None = None, code: str | None = None,
          origin: str = "existing") -> CandidateNode:
    return CandidateNode(node_id=node_id, parent_id=parent, sort_order=sort_order, code=code or str(node_id)[:8],
                         name="n", decomposition_kind=None, control_level="none", dictionary=None, origin_kind=origin)


def test_dense_sibling_order_is_required() -> None:
    assert dense_order_violations([_node(A, 1), _node(B, 2), _node(C, 1, parent=A)]) == []
    assert dense_order_violations([_node(A, 1), _node(B, 3)])
    assert dense_order_violations([_node(A, 2)])


def test_a_change_of_baseline_must_account_for_every_base_identity() -> None:
    base = frozenset({A, B, C})
    ok = validate_governed_submission([_node(A, 1), _node(B, 2)], [], [Retirement(C, "REMOVED", "baseline")],
                                      base_node_ids=base)
    assert ok == []
    missing = validate_governed_submission([_node(A, 1), _node(B, 2)], [], [], base_node_ids=base)
    assert f"{C}: retired id without disposition" in missing
    stays = validate_governed_submission([_node(A, 1), _node(B, 2), _node(C, 3)], [], [Retirement(C, "REMOVED", "baseline")],
                                         base_node_ids=base)
    assert any("cannot stay in the candidate" in v for v in stays)
    foreign = validate_governed_submission([_node(A, 1), _node(B, 2), _node(C, 3)], [], [Retirement(D, "REMOVED", "baseline")],
                                           base_node_ids=base)
    assert any("only identities of the base baseline" in v for v in foreign)


def test_lineage_sources_leave_with_the_matching_disposition() -> None:
    base = frozenset({A, B})
    split = [LineageEdge("SPLIT", A, D), LineageEdge("SPLIT", A, E)]
    nodes = [_node(B, 1), _node(D, 2, origin="minted"), _node(E, 3, origin="minted")]
    assert validate_governed_submission(nodes, split, [Retirement(A, "SPLIT", "baseline")], base_node_ids=base) == []
    wrong = validate_governed_submission(nodes, split, [Retirement(A, "REMOVED", "baseline")], base_node_ids=base)
    assert any("needs a SPLIT disposition" in v for v in wrong)
    one_target = validate_governed_submission([_node(B, 1), _node(D, 2, origin="minted")], split[:1],
                                              [Retirement(A, "SPLIT", "baseline")], base_node_ids=base)
    assert any("needs at least two targets" in v for v in one_target)
    merge_of_one = validate_governed_submission([_node(B, 1), _node(D, 2, origin="minted")], [LineageEdge("MERGE", A, D)],
                                                [Retirement(A, "MERGED", "baseline")], base_node_ids=base)
    assert any("needs at least two sources" in v for v in merge_of_one)
    orphan = validate_governed_submission([_node(B, 1)], [], [Retirement(A, "SPLIT", "baseline")], base_node_ids=base)
    assert any("needs its lineage" in v for v in orphan)


def test_a_first_baseline_only_adopts_and_retires_legacy_rows_of_the_project() -> None:
    legacy = frozenset({A, B, C})
    nodes = [_node(A, 1, origin="adopted_legacy"), _node(D, 2, origin="minted")]
    assert validate_governed_submission(nodes, [], [Retirement(B, "REMOVED", "legacy")], base_node_ids=None,
                                        legacy_node_ids=legacy) == []
    incomplete = validate_governed_submission(nodes, [], [Retirement(B, "REMOVED", "legacy")], base_node_ids=None,
                                              legacy_node_ids=legacy, legacy_complete=True)
    assert f"{C}: legacy row without disposition" in incomplete
    foreign = validate_governed_submission([_node(E, 1, origin="adopted_legacy")], [], [], base_node_ids=None,
                                           legacy_node_ids=legacy)
    assert any("must be a legacy live row" in v for v in foreign)
    existing = validate_governed_submission([_node(A, 1, origin="existing")], [], [], base_node_ids=None, legacy_node_ids=legacy)
    assert any("a first baseline has no base identities" in v for v in existing)
    not_first = validate_governed_submission([_node(A, 1, origin="adopted_legacy")], [], [], base_node_ids=frozenset({A}))
    assert any("only a first baseline adopts" in v for v in not_first)


def test_cycles_codes_and_profile_pins_are_part_of_submit_validation() -> None:
    cycle = [_node(A, 1, parent=B, origin="minted"), _node(B, 1, parent=A, origin="minted")]
    assert any("parent cycle" in v for v in validate_governed_submission(cycle, [], [], base_node_ids=None))
    dup = [_node(A, 1, code="1", origin="minted"), _node(B, 2, code="1", origin="minted")]
    assert any("duplicate code" in v for v in validate_governed_submission(dup, [], [], base_node_ids=None))
    assert validate_governed_submission([_node(A, 1, origin="minted")], [], [], base_node_ids=None, profile_refs=[PIN]) == []
    unpinned = validate_governed_submission([_node(A, 1, origin="minted")], [], [], base_node_ids=None,
                                            profile_refs=[{"profile_id": "x", "profile_version": "1"}])
    assert any("invalid profile pin" in v for v in unpinned)


def test_evidence_references_are_normalized_strings() -> None:
    assert normalize_evidence_refs([" doc:1 ", "doc:2", "doc:1"]) == ["doc:1", "doc:2"]
    for bad in ([""], ["  "], [1], ["x" * 501]):
        with pytest.raises(GovernanceRuleError):
            normalize_evidence_refs(bad)  # type: ignore[arg-type]
