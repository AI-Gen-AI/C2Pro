"""TS-UT-PC2A1-DIGEST-001 -- ``wbs-tree-digest/v1`` and ``wbs-changeset-digest/v1``.

The design vectors are frozen in the #688 amendment (2026-10-05, section 9) and must
reproduce EXACTLY: an approver signs a digest, so any drift in canonicalisation would
silently invalidate every recorded approval.
"""

from __future__ import annotations

import math
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from src.wbs.domain.digest import (
    DigestNode,
    LineageEdge,
    canonical_json,
    change_set_digest,
    normalize_dictionary,
    tree_digest,
)

P = UUID("11111111-1111-4111-8111-111111111111")
A = UUID("aaaaaaaa-0000-4000-8000-000000000001")
B = UUID("aaaaaaaa-0000-4000-8000-000000000002")
D = UUID("aaaaaaaa-0000-4000-8000-000000000004")
E = UUID("aaaaaaaa-0000-4000-8000-000000000005")
CS = UUID("cccccccc-0000-4000-8000-000000000001")
BL = UUID("bbbbbbbb-0000-4000-8000-000000000001")

V1 = "sha256:1b807c952a6d1eb8b329e4de228e7e1e47d13d5b582aaf5319f7401b171ffe41"
V2 = "sha256:7b2f5f899a51efb2abb749adf5dc2b7fff813865b46f918b627f20d7f84fe4d0"
V2_SORT_CHANGED = "sha256:c5a674a68525f65d92eb157d26d687e54ec37d0cc8dbed590f821759e04bc46b"
V3_TREE = "sha256:e4cfae0887137d37078a78db6f4b58d42d614cb8d428a95d6b2fd411901f95bb"
V3_CHANGE_SET = "sha256:adadde7664c5304d589d2d1fa5a647d6316b9066e3c1aa3eac22f67067b5d25d"
V3_LINEAGE_DROPPED = "sha256:d862241f60648355f3b5bc451af0d822aaafd76bb6a97ea856f9a3b42804cf16"
V3_REVISION_4 = "sha256:0c20bc81f13ce59d0b58118bf5bc90587ce122fc3e8ca12126d7315e9ae70521"

ELECTRICAL = DigestNode(
    node_id=A, parent_id=None, sort_order=1, code="1", name="Electrical",
    decomposition_kind="core:discipline", control_level="control_account",
)
SUBSTATION = DigestNode(
    node_id=B, parent_id=A, sort_order=1, code="1.1", name="Subestación",
    decomposition_kind="pv:substation", control_level="work_package",
    dictionary={"scope_statement": "MV/HV substation", "deliverables": ["SLD", "Energisation"]},
)
V3_NODES = (
    ELECTRICAL,
    DigestNode(node_id=D, parent_id=A, sort_order=1, code="1.1", name="HV substation",
               decomposition_kind="pv:substation", control_level="work_package"),
    DigestNode(node_id=E, parent_id=A, sort_order=2, code="1.2", name="MV switchgear",
               decomposition_kind="pv:substation", control_level="work_package"),
)
V3_LINEAGE = (LineageEdge("SPLIT", B, E), LineageEdge("SPLIT", B, D))
V3_PROFILES = ({"profile_id": "solar-pv-epc", "profile_version": "1.0.0", "profile_digest": "sha256:" + "0" * 64},)
V3_EVIDENCE = (
    "document_revision:dddddddd-0000-4000-8000-000000000001",
    "artifact:eeeeeeee-0000-4000-8000-000000000001@v2#sha256:" + "a" * 64,
)


def _v3(**overrides: object) -> str:
    kwargs: dict[str, object] = {
        "project_id": P, "change_set_id": CS, "base_baseline_id": BL, "submitted_revision": 3,
        "nodes": V3_NODES, "lineage": V3_LINEAGE, "profile_refs": V3_PROFILES, "evidence_refs": V3_EVIDENCE,
    }
    kwargs.update(overrides)
    return change_set_digest(**kwargs)  # type: ignore[arg-type]


def test_v1_exact_tree_digest() -> None:
    node = DigestNode(node_id=A, parent_id=None, sort_order=1, code="1", name="Civil",
                      decomposition_kind="core:discipline")
    assert tree_digest(P, [node]) == V1


def test_v2_exact_tree_digest() -> None:
    assert tree_digest(P, [SUBSTATION, ELECTRICAL]) == V2


def test_v2_input_order_and_nfd_spelling_do_not_change_the_digest() -> None:
    nfd = DigestNode(**{**SUBSTATION.__dict__, "name": unicodedata.normalize("NFD", "Subestación")})
    assert nfd.name != SUBSTATION.name
    assert tree_digest(P, [ELECTRICAL, nfd]) == V2


def test_v2_changed_sort_order_changes_the_digest() -> None:
    moved = DigestNode(**{**SUBSTATION.__dict__, "sort_order": 2})
    assert tree_digest(P, [moved, ELECTRICAL]) == V2_SORT_CHANGED != V2


def test_v3_exact_tree_and_change_set_digests() -> None:
    assert tree_digest(P, V3_NODES) == V3_TREE
    assert _v3() == V3_CHANGE_SET


def test_v3_reordered_lineage_and_evidence_give_the_same_digest() -> None:
    assert _v3(lineage=tuple(reversed(V3_LINEAGE)), evidence_refs=tuple(reversed(V3_EVIDENCE))) == V3_CHANGE_SET
    # Duplicated evidence references are one reference.
    assert _v3(evidence_refs=V3_EVIDENCE + V3_EVIDENCE[:1]) == V3_CHANGE_SET


def test_v3_dropping_a_lineage_edge_changes_the_digest() -> None:
    assert _v3(lineage=V3_LINEAGE[:1]) == V3_LINEAGE_DROPPED != V3_CHANGE_SET


def test_v3_changed_submitted_revision_changes_the_digest() -> None:
    assert _v3(submitted_revision=4) == V3_REVISION_4 != V3_CHANGE_SET


def test_tree_digest_ignores_derived_hierarchy_caches() -> None:
    # DigestNode has no lft/rgt/depth/timestamps/status fields to feed in: the digest is
    # defined only over identity, (parent_id, sort_order) and governed content.
    assert not {"lft", "rgt", "depth", "created_at", "updated_at", "status"} & set(DigestNode.__dataclass_fields__)


@pytest.mark.parametrize(
    "value",
    [1.5, math.nan, math.inf, Decimal("1.5"), b"bytes", {1, 2}, datetime.now(UTC), object()],
    ids=["float", "nan", "inf", "decimal", "bytes", "set", "datetime", "object"],
)
def test_canonical_json_rejects_non_canonical_values(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        canonical_json({"value": value})


def test_canonical_json_rejects_non_string_keys() -> None:
    with pytest.raises(TypeError):
        canonical_json({1: "x"})


def test_dictionary_with_unknown_keys_or_floats_is_rejected() -> None:
    with pytest.raises(ValueError):
        tree_digest(P, [DigestNode(**{**SUBSTATION.__dict__, "dictionary": {"risk_ids": ["r1"]}}), ELECTRICAL])
    with pytest.raises((TypeError, ValueError)):
        tree_digest(P, [DigestNode(**{**SUBSTATION.__dict__, "dictionary": {"deliverables": [1.5]}}), ELECTRICAL])


def test_profile_refs_must_be_string_maps() -> None:
    with pytest.raises((TypeError, ValueError)):
        _v3(profile_refs=({"profile_id": "x", "profile_version": 1.0},))


@pytest.mark.parametrize("value", [False, 0, "", {}, "deliverable"])
def test_dictionary_list_fields_reject_falsey_and_other_non_lists(value: object) -> None:
    with pytest.raises(TypeError, match="must be a list of strings"):
        normalize_dictionary({"deliverables": value})


def test_dictionary_list_fields_default_only_when_absent_or_null() -> None:
    assert normalize_dictionary({"deliverables": None})["deliverables"] == []
    assert normalize_dictionary({})["deliverables"] == []


@pytest.mark.parametrize(
    "ref",
    [
        {"profile_id": "solar-pv-epc", "profile_version": "1.0.0"},
        {"profile_id": "solar-pv-epc", "profile_version": "1.0.0", "profile_digest": ""},
        {"profile_id": "solar-pv-epc", "profile_version": "1.0.0", "profile_digest": "sha256:" + "A" * 64},
        {"profile_id": "solar-pv-epc", "profile_version": "1.0.0", "profile_digest": "0" * 64},
    ],
)
def test_profile_refs_pin_a_sha256_profile_digest(ref: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="profile_digest"):
        _v3(profile_refs=(ref,))
