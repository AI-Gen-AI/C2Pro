"""Proposal payload -> PC-2a governed command, and the auditable JSON form of a command.

A stored ``wbs-proposal/v1`` payload names nodes either by a canonical id of the target or by a
local label of a node another item creates. When a human applies an item, labels are resolved
to the ids the governed commands minted for them (in this batch or in an earlier applied
decision); an unresolved label is refused. The result is ALWAYS one of the PC-2a commands --
there is no intelligence-side write path.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from src.wbs.application.governed_change_service import (
    AddNode,
    EditCommand,
    MergeNodes,
    MoveNode,
    NodeSpec,
    RecodeNode,
    RemoveNode,
    ReorderNode,
    SplitNode,
    UpdateNode,
)
from src.wbs.domain.digest import canonical_json
from src.wbs.intelligence.contracts.proposal import ProposalOperation


class UnresolvedLabelError(ValueError):
    """A payload names a local label that no applied item has minted."""


def _node(ref: Mapping[str, Any] | None, labels: Mapping[str, UUID]) -> UUID | None:
    if ref is None:
        return None
    if ref.get("node_id") is not None:
        return UUID(str(ref["node_id"]))
    label = str(ref.get("label"))
    if label not in labels:
        raise UnresolvedLabelError(f"label {label!r} has not been minted yet")
    return labels[label]


def _required(ref: Mapping[str, Any] | None, labels: Mapping[str, UUID]) -> UUID:
    node_id = _node(ref, labels)
    if node_id is None:
        raise ValueError("the command names no node")
    return node_id


def _spec(spec: Mapping[str, Any]) -> NodeSpec:
    return NodeSpec(name=spec["name"], code=spec.get("code"), control_level=spec.get("control_level", "none"),
                    decomposition_kind=spec.get("decomposition_kind"), dictionary=spec.get("dictionary"))


def to_command(operation: ProposalOperation, payload: Mapping[str, Any], labels: Mapping[str, UUID]) -> EditCommand:
    """The governed command a human applies for ``payload`` (labels resolved through ``labels``)."""
    op = ProposalOperation(operation)
    if op is ProposalOperation.ADD_NODE:
        return AddNode(spec=_spec(payload["spec"]), parent_id=_node(payload.get("parent"), labels),
                       position=payload.get("position"))
    if op is ProposalOperation.UPDATE_NODE:
        changes = {k: v for k, v in (payload.get("changes") or {}).items() if v is not None}
        return UpdateNode(node_id=_required(payload.get("node"), labels), changes=changes)
    if op is ProposalOperation.RECODE_NODE:
        return RecodeNode(node_id=_required(payload.get("node"), labels), code=payload["code"])
    if op is ProposalOperation.MOVE_NODE:
        return MoveNode(node_id=_required(payload.get("node"), labels), parent_id=_node(payload.get("parent"), labels),
                        position=payload.get("position"))
    if op is ProposalOperation.REORDER_NODE:
        return ReorderNode(node_id=_required(payload.get("node"), labels), position=payload["position"])
    if op is ProposalOperation.REMOVE_NODE:
        return RemoveNode(node_id=_required(payload.get("node"), labels))
    if op is ProposalOperation.SPLIT_NODE:
        child_targets: dict[UUID, int] = {}
        for key, index in (payload.get("child_targets") or {}).items():
            child = _node({"label": key.removeprefix("label:")} if key.startswith("label:") else {"node_id": key}, labels)
            assert child is not None
            child_targets[child] = int(index)
        return SplitNode(source_id=_required(payload.get("node"), labels),
                         targets=[_spec(target["spec"]) for target in payload["split_targets"]],
                         child_targets=child_targets)
    sources = [_required(ref, labels) for ref in payload["sources"]]
    if "parent" in payload:  # an explicit placement; absent = where the first source was (PC-2a default)
        return MergeNodes(source_ids=sources, target=_spec(payload["spec"]),
                          parent_id=_node(payload.get("parent"), labels), position=payload.get("position"))
    return MergeNodes(source_ids=sources, target=_spec(payload["spec"]), position=payload.get("position"))


def minted_labels(operation: ProposalOperation, payload: Mapping[str, Any], node_ids: list[UUID]) -> dict[str, UUID]:
    """Map the labels a payload creates to the ids the governed command minted for them."""
    op = ProposalOperation(operation)
    if op in (ProposalOperation.ADD_NODE, ProposalOperation.MERGE_NODES):
        return {payload["creates_label"]: node_ids[0]}
    if op is ProposalOperation.SPLIT_NODE:
        return {target["label"]: node_id for target, node_id in zip(payload["split_targets"], node_ids, strict=True)}
    return {}


def _jsonable(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, NodeSpec):
        return {"name": value.name, "code": value.code, "control_level": value.control_level,
                "decomposition_kind": value.decomposition_kind,
                "dictionary": None if value.dictionary is None else dict(value.dictionary)}
    if isinstance(value, Mapping):
        return {str(_jsonable(k)): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return value


_TYPES: Mapping[type, str] = {
    AddNode: "ADD_NODE", UpdateNode: "UPDATE_NODE", RecodeNode: "RECODE_NODE", MoveNode: "MOVE_NODE",
    ReorderNode: "REORDER_NODE", RemoveNode: "REMOVE_NODE", SplitNode: "SPLIT_NODE", MergeNodes: "MERGE_NODES",
}


def command_json(command: EditCommand) -> dict[str, Any]:
    """The exact governed command, as recorded in the decision audit payload."""
    body: dict[str, Any] = {"type": _TYPES[type(command)]}
    for name in command.__dataclass_fields__:
        value = getattr(command, name)
        if isinstance(command, MergeNodes) and name == "parent_id" and not isinstance(value, UUID | type(None)):
            continue  # unset: placed where the first source was
        body[name] = _jsonable(value)
    return body


def digest_json(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


__all__ = ["UnresolvedLabelError", "command_json", "digest_json", "minted_labels", "to_command"]
