"""PC-2b.3 (#922) -- IMPORTED vs CANDIDATE comparison covers every governed field (TS-INT-PC2B3-CMP-001).

A human edit of ``control_level``, ``decomposition_kind``, the WBS Dictionary or the sibling order of
an imported node must never be reported ``UNCHANGED``. Correspondence is the import ``source_ref``
(never the code or the name), the dictionary is compared in its canonical ``wbs-dictionary/v1`` form
(the tree digest's semantics), sibling order is sibling-relative, and anything that cannot be
compared reliably is reported NOT_COMPARABLE with an explicit limitation. Every case is a pure read.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.wbs.adapters.persistence.governance_models import WBSChangeSetNodeORM
from src.wbs.adapters.persistence.import_models import WBSImportSourceORM
from src.wbs.application.governed_change_service import (
    AddNode,
    EditCommand,
    MoveNode,
    NodeSpec,
    RecodeNode,
    ReorderNode,
    UpdateNode,
    WBSGovernedChangeService,
)
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import Scope, _scope
from tests.modules.integration.test_pc2b3_wbs_import import (
    Cand,
    Imp,
    _candidate,
    _import,
    _svc,
    _wbs_document,
)

pytestmark = pytest.mark.asyncio

RICH_CSV = (
    b"code,name,parent_code,control_level,decomposition_kind,scope_statement\n"
    b"1,Plant,,none,core:area,The plant\n"
    b"1.1,Civil,1,control_account,core:discipline,Civil works\n"
    b"1.2,Electrical,1,control_account,core:discipline,Electrical works\n"
    b"1.3,Mechanical,1,control_account,core:discipline,Mechanical works\n"
    b"1.2.1,Cabling,1.2,work_package,core:component,LV cabling\n"
)
PLANT, CIVIL, ELECTRICAL, MECHANICAL, CABLING = "row:2", "row:3", "row:4", "row:5", "row:6"


async def _rich(db: AsyncSession) -> tuple[Scope, Imp, Cand]:
    s = await _scope(db)
    document_id, _ = await _wbs_document(db, s, RICH_CSV)
    source = await _import(db, s, document_id)
    assert source.status == "READY", source
    return s, source, await _candidate(db, s, source.id)


async def _edit(db: AsyncSession, s: Scope, cand: Cand, *commands: EditCommand) -> None:
    governed = WBSGovernedChangeService(db)
    revision = int(await db.scalar(text("SELECT revision FROM wbs_change_sets WHERE id = :c"),
                                   {"c": cand.change_set_id}))
    for command in commands:
        revision = (await governed.execute(project_id=s.project, change_set_id=cand.change_set_id, tenant_id=s.tenant,
                                           actor=s.author, expected_revision=revision, command=command)).revision
    await db.commit()


async def _compare(db: AsyncSession, s: Scope, source: Imp, cand: Cand) -> dict[str, Any]:
    return await _svc(db).comparison(project_id=s.project, tenant_id=s.tenant, import_id=source.id,
                                     change_set_id=cand.change_set_id)


def _rows(view: dict[str, Any]) -> dict[str, tuple[str, list[str]]]:
    return {r["source_ref"]: (r["status"], r["changes"]) for r in view["rows"]}


async def _state(db: AsyncSession, source: Imp, cand: Cand) -> tuple[Any, ...]:
    """Everything a comparison could mutate: the frozen import row and every candidate node."""
    imported = (await db.execute(select(WBSImportSourceORM.snapshot, WBSImportSourceORM.snapshot_digest,
                                        WBSImportSourceORM.diagnostics, WBSImportSourceORM.status)
                                 .where(WBSImportSourceORM.id == source.id)
                                 .execution_options(populate_existing=True))).one()
    nodes = (await db.execute(select(
        WBSChangeSetNodeORM.node_id, WBSChangeSetNodeORM.parent_id, WBSChangeSetNodeORM.sort_order,
        WBSChangeSetNodeORM.code, WBSChangeSetNodeORM.name, WBSChangeSetNodeORM.control_level,
        WBSChangeSetNodeORM.decomposition_kind, WBSChangeSetNodeORM.dictionary, WBSChangeSetNodeORM.provenance)
        .where(WBSChangeSetNodeORM.change_set_id == cand.change_set_id)
        .order_by(WBSChangeSetNodeORM.node_id).execution_options(populate_existing=True))).all()
    revision = await db.scalar(text("SELECT revision FROM wbs_change_sets WHERE id = :c"), {"c": cand.change_set_id})
    return tuple(imported), tuple(tuple(n) for n in nodes), revision


# --------------------------------------------------------------------------- F. unchanged stays unchanged
async def test_f_an_untouched_candidate_is_unchanged_in_every_field(db: AsyncSession) -> None:
    s, source, cand = await _rich(db)
    view = await _compare(db, s, source, cand)
    assert _rows(view) == {ref: ("UNCHANGED", []) for ref in (PLANT, CIVIL, ELECTRICAL, MECHANICAL, CABLING)}
    assert view["added_node_ids"] == [] and view["limitations"] == []
    assert set(view["compared_fields"]) == {"name", "code", "control_level", "decomposition_kind", "dictionary",
                                            "parent", "sibling_order"}
    civil = next(r for r in view["imported"] if r["source_ref"] == CIVIL)
    assert (civil["control_level"], civil["decomposition_kind"], civil["dictionary"]["scope_statement"]) == (
        "control_account", "core:discipline", "Civil works")


# --------------------------------------------------------------------------- A / B / C. governed fields
async def test_a_control_level_only_is_changed(db: AsyncSession) -> None:
    s, source, cand = await _rich(db)
    await _edit(db, s, cand, UpdateNode(node_id=cand.node_ids_by_source_ref[CIVIL],
                                        changes={"control_level": "work_package"}))
    rows = _rows(await _compare(db, s, source, cand))
    assert rows[CIVIL] == ("CHANGED", ["control_level"])
    assert {ref for ref, (status, _) in rows.items() if status != "UNCHANGED"} == {CIVIL}


async def test_b_decomposition_kind_only_is_changed(db: AsyncSession) -> None:
    s, source, cand = await _rich(db)
    await _edit(db, s, cand, UpdateNode(node_id=cand.node_ids_by_source_ref[CABLING],
                                        changes={"decomposition_kind": "core:package"}))
    rows = _rows(await _compare(db, s, source, cand))
    assert rows[CABLING] == ("CHANGED", ["decomposition_kind"])
    assert {ref for ref, (status, _) in rows.items() if status != "UNCHANGED"} == {CABLING}


async def test_c_a_meaningful_dictionary_field_is_changed_and_an_equivalent_one_is_not(db: AsyncSession) -> None:
    s, source, cand = await _rich(db)
    electrical, civil = cand.node_ids_by_source_ref[ELECTRICAL], cand.node_ids_by_source_ref[CIVIL]
    await _edit(db, s, cand,
                UpdateNode(node_id=electrical, changes={"dictionary": {"scope_statement": "Electrical works",
                                                                        "deliverables": ["Single-line diagram"]}}),
                # canonically identical to the imported dictionary (null lists == [] in wbs-dictionary/v1)
                UpdateNode(node_id=civil, changes={"dictionary": {"schema_version": "wbs-dictionary/v1",
                                                                   "scope_statement": "Civil works",
                                                                   "assumptions": None}}))
    rows = _rows(await _compare(db, s, source, cand))
    assert rows[ELECTRICAL] == ("CHANGED", ["dictionary"])
    assert rows[CIVIL] == ("UNCHANGED", [])


# --------------------------------------------------------------------------- D. sibling order
async def test_d_reordering_two_imported_siblings_is_an_order_difference(db: AsyncSession) -> None:
    s, source, cand = await _rich(db)
    await _edit(db, s, cand, ReorderNode(node_id=cand.node_ids_by_source_ref[ELECTRICAL], position=1))
    view = await _compare(db, s, source, cand)
    rows = _rows(view)
    assert rows[ELECTRICAL] == ("CHANGED", ["sibling_order"]) and rows[CIVIL] == ("CHANGED", ["sibling_order"])
    assert rows[MECHANICAL] == ("UNCHANGED", []) and rows[PLANT] == ("UNCHANGED", [])
    assert rows[CABLING] == ("UNCHANGED", [])
    by_ref = {r["source_ref"]: r for r in view["rows"]}
    assert (by_ref[ELECTRICAL]["imported_sibling_position"], by_ref[ELECTRICAL]["candidate_sibling_position"]) == (2, 1)


async def test_d_inserting_or_removing_a_sibling_does_not_fake_an_order_change(db: AsyncSession) -> None:
    """Order is SIBLING-RELATIVE among the imported nodes still under the same parent, not a global index."""
    s, source, cand = await _rich(db)
    plant = cand.node_ids_by_source_ref[PLANT]
    await _edit(db, s, cand, AddNode(spec=NodeSpec(name="Site preparation"), parent_id=plant, position=1),
                MoveNode(node_id=cand.node_ids_by_source_ref[CIVIL], parent_id=cand.node_ids_by_source_ref[ELECTRICAL]))
    rows = _rows(await _compare(db, s, source, cand))
    assert rows[CIVIL] == ("CHANGED", ["parent"])  # moved: a parent change, not also an order change
    assert rows[ELECTRICAL] == ("UNCHANGED", []) and rows[MECHANICAL] == ("UNCHANGED", [])
    assert rows[CABLING] == ("UNCHANGED", [])  # a new sibling under Electrical does not reorder it


# --------------------------------------------------------------------------- E. added nodes stay visible
async def test_e_an_added_node_is_distinguishable_from_imported_nodes(db: AsyncSession) -> None:
    s, source, cand = await _rich(db)
    await _edit(db, s, cand, AddNode(spec=NodeSpec(name="Electrical", code="1.2"),  # same name AND code
                                     parent_id=cand.node_ids_by_source_ref[PLANT]))
    view = await _compare(db, s, source, cand)
    added = [c for c in view["candidate"] if c["origin"] == "ADDED"]
    assert len(added) == 1 and added[0]["source_ref"] is None
    assert view["added_node_ids"] == [added[0]["node_id"]]
    assert {c["source_ref"] for c in view["candidate"] if c["origin"] == "IMPORTED"} == {
        PLANT, CIVIL, ELECTRICAL, MECHANICAL, CABLING}
    assert _rows(view)[ELECTRICAL] == ("UNCHANGED", [])  # matched by source_ref, never by code or name
    assert all(r["node_id"] != added[0]["node_id"] for r in view["rows"])


async def test_identity_is_the_source_ref_not_the_code_or_the_name(db: AsyncSession) -> None:
    s, source, cand = await _rich(db)
    civil = cand.node_ids_by_source_ref[CIVIL]
    await _edit(db, s, cand, RecodeNode(node_id=civil, code="9"), UpdateNode(node_id=civil, changes={"name": "Works"}))
    by_ref = {r["source_ref"]: r for r in (await _compare(db, s, source, cand))["rows"]}
    assert (by_ref[CIVIL]["status"], by_ref[CIVIL]["changes"], by_ref[CIVIL]["node_id"]) == (
        "CHANGED", ["name", "code"], str(civil))


async def test_an_unreliable_correspondence_is_not_comparable_never_unchanged(db: AsyncSession) -> None:
    """Two candidate nodes claiming the same source_ref cannot be compared: say so explicitly."""
    s, source, cand = await _rich(db)
    await _edit(db, s, cand, AddNode(spec=NodeSpec(name="Copy"), parent_id=cand.node_ids_by_source_ref[PLANT]))
    added = await db.scalar(select(WBSChangeSetNodeORM).where(
        WBSChangeSetNodeORM.change_set_id == cand.change_set_id,
        WBSChangeSetNodeORM.node_id.not_in(list(cand.node_ids_by_source_ref.values()))))
    assert added is not None
    original = await db.scalar(select(WBSChangeSetNodeORM).where(
        WBSChangeSetNodeORM.node_id == cand.node_ids_by_source_ref[CIVIL]))
    assert original is not None
    added.provenance = {**(added.provenance or {}), "import": dict(original.provenance["import"])}
    await db.commit()
    view = await _compare(db, s, source, cand)
    by_ref = {r["source_ref"]: r for r in view["rows"]}
    assert by_ref[CIVIL]["status"] == "NOT_COMPARABLE" and by_ref[CIVIL]["changes"] == []
    assert by_ref[CIVIL]["limitations"] == ["DUPLICATE_SOURCE_REF"]
    assert "DUPLICATE_SOURCE_REF" in view["limitations"]


async def test_a_claim_on_a_ref_the_snapshot_lacks_stays_visible_as_added(db: AsyncSession) -> None:
    s, source, cand = await _rich(db)
    await _edit(db, s, cand, AddNode(spec=NodeSpec(name="Stray"), parent_id=cand.node_ids_by_source_ref[PLANT]))
    stray = await db.scalar(select(WBSChangeSetNodeORM).where(
        WBSChangeSetNodeORM.change_set_id == cand.change_set_id,
        WBSChangeSetNodeORM.node_id.not_in(list(cand.node_ids_by_source_ref.values()))))
    assert stray is not None
    stray_id = stray.node_id
    stray.provenance = {"import": {"import_source_id": str(source.id), "source_ref": "row:999"}}
    await db.commit()
    view = await _compare(db, s, source, cand)
    assert view["added_node_ids"] == [str(stray_id)]
    assert next(c for c in view["candidate"] if c["node_id"] == str(stray_id))["origin"] == "ADDED"
    assert {r["status"] for r in view["rows"]} == {"UNCHANGED"}


# --------------------------------------------------------------------------- G. read only
async def test_g_comparison_mutates_neither_the_import_nor_the_candidate(db: AsyncSession) -> None:
    s, source, cand = await _rich(db)
    await _edit(db, s, cand,
                UpdateNode(node_id=cand.node_ids_by_source_ref[CIVIL], changes={"control_level": "work_package"}),
                ReorderNode(node_id=cand.node_ids_by_source_ref[MECHANICAL], position=1),
                AddNode(spec=NodeSpec(name="Commissioning"), parent_id=cand.node_ids_by_source_ref[PLANT]))
    before = await _state(db, source, cand)
    for _ in range(2):
        await _compare(db, s, source, cand)
        assert not db.new and not db.dirty and not db.deleted
    await db.commit()
    assert await _state(db, source, cand) == before
    assert before[0][1] == source.snapshot_digest

