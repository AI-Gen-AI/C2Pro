"""
WBS CRUD operations tests (TDD - RED phase).

Refers to Suite ID: TS-UD-PRJ-WBS-004.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.projects.domain.wbs_item_entity import WBS, WBSItem


class TestWBSCRUDOperations:
    """Refers to Suite ID: TS-UD-PRJ-WBS-004"""

    def test_001_create_item_adds_to_aggregate(self) -> None:
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        item = WBSItem(project_id=project_id, code="1", name="Root", level=1)

        wbs.add_item(item)

        assert wbs.get_item(item.id) is not None

    def test_002_read_item_by_id_returns_entity(self) -> None:
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        item = WBSItem(project_id=project_id, code="1", name="Root", level=1)
        wbs.add_item(item)

        found = wbs.get_item(item.id)

        assert found == item

    def test_003_read_missing_item_returns_none(self) -> None:
        wbs = WBS(project_id=uuid4())

        assert wbs.get_item(uuid4()) is None

    def test_004_update_item_name_and_description(self) -> None:
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        item = WBSItem(project_id=project_id, code="1", name="Root", level=1)
        wbs.add_item(item)

        updated = wbs.update_item(item.id, name="Updated Root", description="updated")

        assert updated.name == "Updated Root"
        assert updated.description == "updated"

    def test_005_update_non_existing_item_raises(self) -> None:
        wbs = WBS(project_id=uuid4())

        with pytest.raises(ValueError, match="not found"):
            wbs.update_item(uuid4(), name="x")

    def test_006_delete_leaf_item_removes_from_aggregate(self) -> None:
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        root = WBSItem(project_id=project_id, code="1", name="Root", level=1)
        leaf = WBSItem(project_id=project_id, code="1.1", name="Leaf", level=2, parent_id=root.id)
        wbs.add_item(root)
        wbs.add_item(leaf)

        wbs.delete_item(leaf.id)

        assert wbs.get_item(leaf.id) is None

    def test_007_delete_parent_with_children_rejected(self) -> None:
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        root = WBSItem(project_id=project_id, code="1", name="Root", level=1)
        child = WBSItem(project_id=project_id, code="1.1", name="Child", level=2, parent_id=root.id)
        wbs.add_item(root)
        wbs.add_item(child)

        with pytest.raises(ValueError, match="has children"):
            wbs.delete_item(root.id)

    def test_008_delete_non_existing_item_raises(self) -> None:
        wbs = WBS(project_id=uuid4())

        with pytest.raises(ValueError, match="not found"):
            wbs.delete_item(uuid4())

    def test_009_list_items_by_level_filters_correctly(self) -> None:
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        root = WBSItem(project_id=project_id, code="1", name="Root", level=1)
        c1 = WBSItem(project_id=project_id, code="1.1", name="Child1", level=2, parent_id=root.id)
        c2 = WBSItem(project_id=project_id, code="1.2", name="Child2", level=2, parent_id=root.id)
        wbs.add_item(root)
        wbs.add_item(c1)
        wbs.add_item(c2)

        level_two = wbs.list_items(level=2)

        assert {item.code for item in level_two} == {"1.1", "1.2"}

    def test_010_update_item_code_maintains_uniqueness(self) -> None:
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        a = WBSItem(project_id=project_id, code="1", name="A", level=1)
        b = WBSItem(project_id=project_id, code="2", name="B", level=1)
        wbs.add_item(a)
        wbs.add_item(b)

        with pytest.raises(ValueError, match="already exists"):
            wbs.update_item(a.id, code="2")
