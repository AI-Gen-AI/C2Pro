"""WBS governance digests (ADR-029; #688 amendment section 9, frozen).

``wbs-tree-digest/v1`` fingerprints a WBS tree; ``wbs-changeset-digest/v1`` fingerprints
exactly what an approver signs (the candidate tree plus its lineage, base, revision,
profile pins and evidence). Canonical encoding:

* JSON with object keys sorted by Unicode code point, separators ``,`` and ``:``;
* UTF-8, ``ensure_ascii=False``; every string NFC-normalised; UUIDs lowercase;
* integers as JSON integers; floats/NaN/Decimal and any other non-JSON-native value are
  rejected (a future decimal must be a canonical string); explicit ``null``;
* lists of strings keep human order; sets are represented as sorted, de-duplicated lists;
* ``sha256:`` + lowercase hex.

Only identity, ``(parent_id, sort_order)`` and governed content are hashed -- never the
derived ``lft``/``rgt``/``depth`` caches, timestamps, status, dates, cost or metadata.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

TREE_DIGEST_VERSION = "wbs-tree-digest/v1"
CHANGE_SET_DIGEST_VERSION = "wbs-changeset-digest/v1"
DICTIONARY_SCHEMA_VERSION = "wbs-dictionary/v1"
DICTIONARY_LIST_KEYS = (
    "scope_included",
    "scope_excluded",
    "deliverables",
    "acceptance_criteria",
    "assumptions",
    "interface_notes",
)
_DICTIONARY_KEYS = frozenset({"schema_version", "scope_statement", *DICTIONARY_LIST_KEYS})


@dataclass(frozen=True)
class DigestNode:
    """The digest-bound projection of one WBS node (candidate, baseline or live)."""

    node_id: UUID
    parent_id: UUID | None
    sort_order: int
    code: str | None
    name: str
    decomposition_kind: str | None = None
    control_level: str = "none"
    dictionary: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class LineageEdge:
    kind: str
    source_node_id: UUID
    target_node_id: UUID


def _canonical(value: Any) -> Any:
    """Validate and NFC-normalise a JSON-native value; reject anything non-canonical."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"governed digest keys must be strings, got {type(key).__name__}")
            out[unicodedata.normalize("NFC", key)] = _canonical(item)
        return out
    if isinstance(value, list | tuple):
        return [_canonical(item) for item in value]
    # float (incl. NaN/inf), Decimal, bytes, set, datetime, UUID objects, ...: never implicit.
    raise TypeError(f"{type(value).__name__} is not allowed in governed WBS digest content")


def canonical_json(value: Any) -> bytes:
    """The canonical UTF-8 encoding that every governed digest hashes."""
    return json.dumps(
        _canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def normalize_dictionary(dictionary: Mapping[str, Any] | None) -> dict[str, Any]:
    """``wbs-dictionary/v1`` with every key present (lists default to ``[]``).

    Descriptive only: unknown keys -- in particular relational links such as risk,
    obligation, schedule or BOM ids -- are rejected, never silently dropped.
    """
    raw = dict(dictionary or {})
    unknown = set(raw) - _DICTIONARY_KEYS
    if unknown:
        raise ValueError(f"unsupported WBS dictionary keys: {sorted(unknown)}")
    version = raw.get("schema_version", DICTIONARY_SCHEMA_VERSION)
    if version != DICTIONARY_SCHEMA_VERSION:
        raise ValueError(f"unsupported WBS dictionary schema_version {version!r}")
    statement = raw.get("scope_statement")
    if statement is not None and not isinstance(statement, str):
        raise TypeError("scope_statement must be a string or null")
    out: dict[str, Any] = {"schema_version": DICTIONARY_SCHEMA_VERSION, "scope_statement": statement}
    for key in DICTIONARY_LIST_KEYS:
        items = raw.get(key) or []
        if not isinstance(items, list | tuple) or not all(isinstance(item, str) for item in items):
            raise TypeError(f"dictionary.{key} must be a list of strings")
        out[key] = list(items)
    return out


def _uuid(value: UUID | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, UUID):
        raise TypeError(f"expected a UUID, got {type(value).__name__}")
    return str(value)  # canonical lowercase hyphenated form


def _node(node: DigestNode) -> dict[str, Any]:
    if isinstance(node.sort_order, bool) or not isinstance(node.sort_order, int) or node.sort_order < 1:
        raise ValueError("sort_order must be an integer >= 1")
    if not isinstance(node.name, str):
        raise TypeError("name must be a string")
    return {
        "node_id": _uuid(node.node_id),
        "parent_id": _uuid(node.parent_id),
        "sort_order": node.sort_order,
        "code": node.code,
        "name": node.name,
        "decomposition_kind": node.decomposition_kind,
        "control_level": node.control_level,
        "dictionary": normalize_dictionary(node.dictionary),
    }


def tree_envelope(project_id: UUID, nodes: Iterable[DigestNode]) -> dict[str, Any]:
    canonical_nodes = sorted((_node(node) for node in nodes), key=lambda item: item["node_id"])
    return {
        "digest_version": TREE_DIGEST_VERSION,
        "scope": "tree",
        "project_id": _uuid(project_id),
        "nodes": canonical_nodes,
    }


def tree_digest(project_id: UUID, nodes: Iterable[DigestNode]) -> str:
    """``wbs-tree-digest/v1`` of a whole tree (input order is irrelevant)."""
    return _sha256(tree_envelope(project_id, nodes))


def _profile_ref(ref: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(ref, Mapping) or not all(isinstance(value, str) for value in ref.values()):
        raise TypeError("profile refs must map strings to strings")
    if "profile_id" not in ref or "profile_version" not in ref:
        raise ValueError("profile refs require profile_id and profile_version")
    return {str(key): value for key, value in ref.items()}


def change_set_digest(
    *,
    project_id: UUID,
    change_set_id: UUID,
    base_baseline_id: UUID | None,
    submitted_revision: int,
    nodes: Iterable[DigestNode],
    lineage: Iterable[LineageEdge] = (),
    profile_refs: Sequence[Mapping[str, Any]] = (),
    evidence_refs: Iterable[str] = (),
) -> str:
    """``wbs-changeset-digest/v1``: what the approver signs.

    Lineage, profile pins and evidence references are order-insensitive (sorted; evidence
    de-duplicated); everything else is bound exactly, including ``submitted_revision``.
    """
    if isinstance(submitted_revision, bool) or not isinstance(submitted_revision, int) or submitted_revision < 1:
        raise ValueError("submitted_revision must be an integer >= 1")
    edges = sorted(
        (
            {"kind": edge.kind, "source_node_id": _uuid(edge.source_node_id), "target_node_id": _uuid(edge.target_node_id)}
            for edge in lineage
        ),
        key=lambda item: (item["kind"], item["source_node_id"], item["target_node_id"]),
    )
    evidence = sorted({unicodedata.normalize("NFC", ref) for ref in _strings(evidence_refs)})
    profiles = sorted((_profile_ref(ref) for ref in profile_refs), key=lambda p: (p["profile_id"], p["profile_version"]))
    return _sha256(
        {
            "digest_version": CHANGE_SET_DIGEST_VERSION,
            "scope": "change_set",
            "project_id": _uuid(project_id),
            "change_set_id": _uuid(change_set_id),
            "base_baseline_id": _uuid(base_baseline_id),
            "submitted_revision": submitted_revision,
            "tree_digest": tree_digest(project_id, nodes),
            "lineage": edges,
            "profile_refs": profiles,
            "evidence_refs": evidence,
        }
    )


def _strings(values: Iterable[str]) -> list[str]:
    out = list(values)
    if not all(isinstance(value, str) for value in out):
        raise TypeError("evidence refs must be strings")
    return out


__all__ = [
    "CHANGE_SET_DIGEST_VERSION",
    "DICTIONARY_LIST_KEYS",
    "DICTIONARY_SCHEMA_VERSION",
    "TREE_DIGEST_VERSION",
    "DigestNode",
    "LineageEdge",
    "canonical_json",
    "change_set_digest",
    "normalize_dictionary",
    "tree_digest",
    "tree_envelope",
]
