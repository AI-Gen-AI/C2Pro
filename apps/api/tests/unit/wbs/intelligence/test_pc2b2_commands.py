"""PC-2b.2 (#921) -- proposal payload -> PC-2a governed command, and planning over applied items.

An applied item is ALWAYS one of the PC-2a commands (there is no intelligence-side write path);
labels resolve only to ids a governed command already minted; the audit form of a command is
exact and digestible; and a prerequisite a human already applied is satisfied, never re-applied.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.wbs.application.governed_change_service import (
    AddNode,
    MergeNodes,
    MoveNode,
    RecodeNode,
    RemoveNode,
    ReorderNode,
    SplitNode,
    UpdateNode,
)
from src.wbs.intelligence.application.commands import (
    UnresolvedLabelError,
    command_json,
    digest_json,
    minted_labels,
    to_command,
)
from src.wbs.intelligence.contracts.proposal import ProposalItem, ProposalOperation
from src.wbs.intelligence.contracts.run import RunOutcome, RunScope
from src.wbs.intelligence.validation.dependency import (
    SelectionPlan,
    SelectionRefusal,
    plan_selection,
)
from src.wbs.intelligence.validation.simulation import SnapshotNode, TargetSnapshot

OP = ProposalOperation
A, B, C = uuid4(), uuid4(), uuid4()


def test_every_operation_maps_to_its_governed_command() -> None:
    labels = {"mv": C}
    cases: list[tuple[OP, dict[str, Any], type]] = [
        (OP.ADD_NODE, {"creates_label": "x", "spec": {"name": "X"}, "parent": {"label": "mv"}}, AddNode),
        (OP.UPDATE_NODE, {"node": {"node_id": str(A)}, "changes": {"name": "Y"}}, UpdateNode),
        (OP.RECODE_NODE, {"node": {"node_id": str(A)}, "code": "9"}, RecodeNode),
        (OP.MOVE_NODE, {"node": {"node_id": str(A)}, "parent": {"node_id": str(B)}, "position": 2}, MoveNode),
        (OP.REORDER_NODE, {"node": {"node_id": str(A)}, "position": 1}, ReorderNode),
        (OP.REMOVE_NODE, {"node": {"node_id": str(A)}}, RemoveNode),
        (OP.SPLIT_NODE, {"node": {"node_id": str(A)}, "split_targets": [
            {"label": "s1", "spec": {"name": "S1"}}, {"label": "s2", "spec": {"name": "S2"}}],
            "child_targets": {str(B): 1, "label:mv": 0}}, SplitNode),
        (OP.MERGE_NODES, {"sources": [{"node_id": str(A)}, {"node_id": str(B)}], "creates_label": "m",
                          "spec": {"name": "M"}}, MergeNodes),
    ]
    for operation, payload, expected in cases:
        command = to_command(operation, payload, labels)
        assert type(command) is expected
        body = command_json(command)
        assert body["type"] == operation.value
        json.dumps(body)  # auditable as-is
    add = to_command(OP.ADD_NODE, cases[0][1], labels)
    assert isinstance(add, AddNode) and add.parent_id == C  # the label resolved to the minted id
    split = to_command(OP.SPLIT_NODE, cases[6][1], labels)
    assert isinstance(split, SplitNode) and split.child_targets == {B: 1, C: 0}


def test_merge_placement_keeps_the_pc2a_default_unless_explicit() -> None:
    default = to_command(OP.MERGE_NODES, {"sources": [{"node_id": str(A)}, {"node_id": str(B)}],
                                          "creates_label": "m", "spec": {"name": "M"}}, {})
    assert "parent_id" not in command_json(default)  # placed where the first source was
    top = to_command(OP.MERGE_NODES, {"sources": [{"node_id": str(A)}, {"node_id": str(B)}], "creates_label": "m",
                                      "spec": {"name": "M"}, "parent": None}, {})
    assert isinstance(top, MergeNodes) and command_json(top)["parent_id"] is None


def test_an_unminted_label_never_resolves() -> None:
    with pytest.raises(UnresolvedLabelError):
        to_command(OP.ADD_NODE, {"creates_label": "x", "spec": {"name": "X"}, "parent": {"label": "ghost"}}, {})


def test_minted_labels_and_digest_are_exact() -> None:
    split = {"split_targets": [{"label": "s1", "spec": {"name": "S1"}}, {"label": "s2", "spec": {"name": "S2"}}]}
    assert minted_labels(OP.SPLIT_NODE, split, [A, B]) == {"s1": A, "s2": B}
    assert minted_labels(OP.ADD_NODE, {"creates_label": "x"}, [C]) == {"x": C}
    assert minted_labels(OP.RECODE_NODE, {}, [A]) == {}
    commands = [command_json(to_command(OP.RECODE_NODE, {"node": {"node_id": str(A)}, "code": "9"}, {}))]
    assert digest_json(commands) == digest_json(json.loads(json.dumps(commands)))
    assert digest_json(commands).startswith("sha256:")


def _item(ref: str, payload: dict[str, Any], *, depends_on: tuple[UUID, ...] = (), creates: tuple[str, ...] = (),
          op: OP = OP.ADD_NODE) -> ProposalItem:
    return ProposalItem(item_id=uuid4(), ref=ref, operation=op, payload=payload, affected_node_ids=(),
                        target_fingerprints={}, creates_labels=creates, uses_labels=(), depends_on=depends_on,
                        rationale="r", evidence=(), confidence_pct=50, confidence="MEDIUM", assumptions=(),
                        ambiguity_flags=(), profile_rule_refs=(), addresses_finding_ids=(), destructive=False)


def test_an_applied_prerequisite_is_satisfied_and_never_reapplied() -> None:
    root = SnapshotNode(node_id=A, parent_id=None, sort_order=1, code="1", name="Root")
    minted = SnapshotNode(node_id=B, parent_id=A, sort_order=1, code="1.1", name="MV", minted=True)
    parent = _item("p-mv", {"creates_label": "mv", "spec": {"name": "MV", "code": "1.1"}, "parent": {"node_id": str(A)}},
                   creates=("mv",))
    # the dependant, with its label already bound to the id the applied parent minted
    child = _item("p-cables", {"creates_label": "c", "spec": {"name": "Cables", "code": "1.1.1"},
                               "parent": {"node_id": str(B)}}, depends_on=(parent.item_id,), creates=("c",))
    current = TargetSnapshot(project_id=uuid4(), nodes=(root, minted))
    plan = plan_selection(items=[parent, child], selected=[child.item_id], rejected=[], current=current,
                          kind_terms={}, satisfied=[parent.item_id])
    assert isinstance(plan, SelectionPlan) and plan.ordered_item_ids == (child.item_id,)
    again = plan_selection(items=[parent, child], selected=[parent.item_id], rejected=[], current=current,
                           kind_terms={}, satisfied=[parent.item_id])
    assert isinstance(again, SelectionRefusal) and any("already applied" in r for r in again.reasons)
    # without the satisfied set the prerequisite would be required (never auto-selected)
    missing = plan_selection(items=[parent, child], selected=[child.item_id], rejected=[], current=current,
                             kind_terms={})
    assert isinstance(missing, SelectionRefusal) and missing.required_missing == {parent.item_id}


def test_run_contract_keeps_status_and_outcome_apart() -> None:
    from src.wbs.intelligence.contracts.run import REUSABLE_OUTCOMES, TERMINAL_STATUSES, RunStatus

    assert {s.value for s in TERMINAL_STATUSES} == {"COMPLETED", "FAILED", "CANCELLED"}
    assert RunOutcome.FAILED not in REUSABLE_OUTCOMES and RunOutcome.CANCELLED not in REUSABLE_OUTCOMES
    assert RunStatus("REQUESTED") is RunStatus.REQUESTED and RunScope(tenant_id=A, project_id=B).tenant_id == A
