"""
WBS item entity tests (TDD - RED phase).

Refers to Suite ID: TS-UD-PRJ-WBS-001.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.projects.domain.wbs_item_entity import WBS, WBSItem


@pytest.fixture
def base_data() -> dict[str, object]:
    return {
        "project_id": uuid4(),
        "name": "Root",
    }


class TestWBSItemEntity:
    """Refers to Suite ID: TS-UD-PRJ-WBS-001"""

    def test_001_wbs_item_creation_all_fields(self, base_data: dict[str, object]) -> None:
        item_id = uuid4()
        parent_id = uuid4()
        item = WBSItem(
            **base_data,
            code="1",
            level=1,
            id=item_id,
            parent_id=parent_id,
            description="optional",
        )
        assert item.id == item_id
        assert item.parent_id == parent_id
        assert item.description == "optional"

    def test_002_wbs_item_creation_minimum_fields(self, base_data: dict[str, object]) -> None:
        item = WBSItem(**base_data, code="1", level=1)
        assert isinstance(item.id, UUID)
        assert item.parent_id is None
        assert item.description is None

    def test_003_wbs_item_fails_without_code(self, base_data: dict[str, object]) -> None:
        with pytest.raises(ValidationError):
            WBSItem(**base_data, level=1)

    def test_004_wbs_item_fails_without_name(self, base_data: dict[str, object]) -> None:
        data = dict(base_data)
        data.pop("name")
        with pytest.raises(ValidationError):
            WBSItem(**data, code="1", level=1)

    def test_005_wbs_item_fails_invalid_level(self, base_data: dict[str, object]) -> None:
        with pytest.raises(ValidationError, match="between 1 and 4"):
            WBSItem(**base_data, code="1", level=0)

    def test_006_wbs_item_immutability(self, base_data: dict[str, object]) -> None:
        item = WBSItem(**base_data, code="1", level=1)
        with pytest.raises(ValidationError, match="Instance is frozen"):
            item.name = "Updated"

    def test_007_wbs_code_format_1(self, base_data: dict[str, object]) -> None:
        item = WBSItem(**base_data, code="1", level=1)
        assert item.code == "1"

    def test_008_wbs_code_format_1_1(self, base_data: dict[str, object]) -> None:
        item = WBSItem(**base_data, code="1.1", level=2)
        assert item.code == "1.1"

    def test_009_wbs_code_format_1_1_1(self, base_data: dict[str, object]) -> None:
        item = WBSItem(**base_data, code="1.1.1", level=3)
        assert item.code == "1.1.1"

    def test_010_wbs_code_format_1_1_1_1(self, base_data: dict[str, object]) -> None:
        item = WBSItem(**base_data, code="1.1.1.1", level=4)
        assert item.code == "1.1.1.1"

    def test_011_wbs_code_invalid_format_rejected(self, base_data: dict[str, object]) -> None:
        with pytest.raises(ValidationError, match="Invalid WBS code format"):
            WBSItem(**base_data, code="1..1", level=3)

    def test_012_wbs_code_uniqueness_per_project(self) -> None:
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        item_a = WBSItem(project_id=project_id, code="1.1", name="Task A", level=2)
        item_b = WBSItem(project_id=project_id, code="1.1", name="Task B", level=2)

        wbs.add_item(item_a)
        with pytest.raises(ValueError, match="already exists"):
            wbs.add_item(item_b)

    def test_013_wbs_level_1_valid(self, base_data: dict[str, object]) -> None:
        item = WBSItem(**base_data, code="1", level=1)
        assert item.level == 1

    def test_014_wbs_level_4_valid(self, base_data: dict[str, object]) -> None:
        item = WBSItem(**base_data, code="1.1.1.1", level=4)
        assert item.level == 4

    def test_015_wbs_level_0_invalid(self, base_data: dict[str, object]) -> None:
        with pytest.raises(ValidationError, match="between 1 and 4"):
            WBSItem(**base_data, code="1", level=0)

    def test_016_wbs_level_5_invalid(self, base_data: dict[str, object]) -> None:
        with pytest.raises(ValidationError, match="between 1 and 4"):
            WBSItem(**base_data, code="1.1.1.1.1", level=5)

    def test_017_wbs_level_matches_code_depth(self, base_data: dict[str, object]) -> None:
        with pytest.raises(ValidationError, match="match the depth of the code"):
            WBSItem(**base_data, code="1.1", level=3)

    def test_018_wbs_level_parent_child_validation(self) -> None:
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        parent = WBSItem(project_id=project_id, code="1", name="Parent", level=1)
        wbs.add_item(parent)

        valid_child = WBSItem(
            project_id=project_id,
            code="1.1",
            name="Valid Child",
            level=2,
            parent_id=parent.id,
        )
        wbs.add_item(valid_child)

        invalid_child = WBSItem(
            project_id=project_id,
            code="2.1",
            name="Wrong Branch",
            level=2,
            parent_id=parent.id,
        )
        with pytest.raises(ValueError, match="must start with parent code"):
            wbs.add_item(invalid_child)

    def test_019_wbs_reject_wrong_project_id(self) -> None:
        """WBS rejects items with different project_id."""
        project_a = uuid4()
        project_b = uuid4()
        wbs = WBS(project_id=project_a)
        item = WBSItem(project_id=project_b, code="1", name="Task", level=1)

        with pytest.raises(ValueError, match="project_id does not match"):
            wbs.add_item(item)

    def test_020_wbs_reject_parent_not_found(self) -> None:
        """WBS rejects items referencing non-existent parent."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        missing_parent_id = uuid4()
        item = WBSItem(
            project_id=project_id,
            code="1.1",
            name="Orphan",
            level=2,
            parent_id=missing_parent_id,
        )

        with pytest.raises(ValueError, match="Parent WBS item.*not found"):
            wbs.add_item(item)

    def test_021_wbs_reject_wrong_child_level(self) -> None:
        """WBS rejects child with non-sequential level."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        parent = WBSItem(project_id=project_id, code="1", name="Parent", level=1)
        wbs.add_item(parent)

        # Code 1.1.1 has depth 3, but parent level is 1, so child should be level 2
        wrong_level_child = WBSItem(
            project_id=project_id,
            code="1.1.1",
            name="Wrong Level",
            level=3,
            parent_id=parent.id,
        )

        with pytest.raises(ValueError, match="one greater than parent level"):
            wbs.add_item(wrong_level_child)

    def test_022_wbs_get_item_found(self) -> None:
        """WBS.get_item returns item when found."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        item = WBSItem(project_id=project_id, code="1", name="Task", level=1)
        wbs.add_item(item)

        found = wbs.get_item(item.id)
        assert found == item

    def test_023_wbs_get_item_not_found(self) -> None:
        """WBS.get_item returns None when not found."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)

        missing_id = uuid4()
        found = wbs.get_item(missing_id)
        assert found is None

    def test_024_wbs_get_all_items(self) -> None:
        """WBS.get_all_items returns all items."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        item1 = WBSItem(project_id=project_id, code="1", name="Task 1", level=1)
        item2 = WBSItem(project_id=project_id, code="2", name="Task 2", level=1)
        wbs.add_item(item1)
        wbs.add_item(item2)

        all_items = wbs.get_all_items()
        assert len(all_items) == 2
        assert item1 in all_items
        assert item2 in all_items

    def test_025_wbs_list_items_no_filter(self) -> None:
        """WBS.list_items without level filter returns all."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        item1 = WBSItem(project_id=project_id, code="1", name="Level 1", level=1)
        wbs.add_item(item1)
        item2 = WBSItem(
            project_id=project_id, code="1.1", name="Level 2", level=2, parent_id=item1.id
        )
        wbs.add_item(item2)

        items = wbs.list_items()
        assert len(items) == 2

    def test_026_wbs_list_items_filtered_by_level(self) -> None:
        """WBS.list_items with level filter returns matching items."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        item1 = WBSItem(project_id=project_id, code="1", name="Level 1", level=1)
        wbs.add_item(item1)
        item2 = WBSItem(
            project_id=project_id, code="1.1", name="Level 2", level=2, parent_id=item1.id
        )
        wbs.add_item(item2)

        level2_items = wbs.list_items(level=2)
        assert len(level2_items) == 1
        assert level2_items[0].level == 2

    def test_027_wbs_update_item_name(self) -> None:
        """WBS.update_item changes item name."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        item = WBSItem(project_id=project_id, code="1", name="Old Name", level=1)
        wbs.add_item(item)

        updated = wbs.update_item(item.id, name="New Name")
        assert updated.name == "New Name"
        assert updated.code == "1"

    def test_028_wbs_update_item_description(self) -> None:
        """WBS.update_item changes item description."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        item = WBSItem(project_id=project_id, code="1", name="Task", level=1)
        wbs.add_item(item)

        updated = wbs.update_item(item.id, description="New desc")
        assert updated.description == "New desc"

    def test_029_wbs_update_item_code(self) -> None:
        """WBS.update_item changes item code."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        item = WBSItem(project_id=project_id, code="1", name="Task", level=1)
        wbs.add_item(item)

        updated = wbs.update_item(item.id, code="2")
        assert updated.code == "2"

    def test_030_wbs_update_item_not_found(self) -> None:
        """WBS.update_item raises when item not found."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        missing_id = uuid4()

        with pytest.raises(ValueError, match="not found"):
            wbs.update_item(missing_id, name="New")

    def test_031_wbs_update_item_duplicate_code(self) -> None:
        """WBS.update_item rejects duplicate code."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        item1 = WBSItem(project_id=project_id, code="1", name="Task 1", level=1)
        item2 = WBSItem(project_id=project_id, code="2", name="Task 2", level=1)
        wbs.add_item(item1)
        wbs.add_item(item2)

        with pytest.raises(ValueError, match="already exists"):
            wbs.update_item(item2.id, code="1")

    def test_032_wbs_delete_item(self) -> None:
        """WBS.delete_item removes item."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        item = WBSItem(project_id=project_id, code="1", name="Task", level=1)
        wbs.add_item(item)

        wbs.delete_item(item.id)
        assert wbs.get_item(item.id) is None

    def test_033_wbs_delete_item_not_found(self) -> None:
        """WBS.delete_item raises when item not found."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        missing_id = uuid4()

        with pytest.raises(ValueError, match="not found"):
            wbs.delete_item(missing_id)

    def test_034_wbs_delete_item_with_children_rejected(self) -> None:
        """WBS.delete_item rejects items with children."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        parent = WBSItem(project_id=project_id, code="1", name="Parent", level=1)
        wbs.add_item(parent)
        child = WBSItem(
            project_id=project_id, code="1.1", name="Child", level=2, parent_id=parent.id
        )
        wbs.add_item(child)

        with pytest.raises(ValueError, match="has children"):
            wbs.delete_item(parent.id)

    def test_035_wbs_update_item_with_parent_validates_hierarchy(self) -> None:
        """WBS.update_item validates parent hierarchy when updating child code."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        parent = WBSItem(project_id=project_id, code="1", name="Parent", level=1)
        wbs.add_item(parent)
        child = WBSItem(
            project_id=project_id, code="1.1", name="Child", level=2, parent_id=parent.id
        )
        wbs.add_item(child)

        # Valid update: change code to 1.2 (still under parent 1)
        updated = wbs.update_item(child.id, code="1.2")
        assert updated.code == "1.2"

    def test_036_wbs_update_item_invalid_parent_code_prefix(self) -> None:
        """WBS.update_item rejects code not starting with parent code."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        parent = WBSItem(project_id=project_id, code="1", name="Parent", level=1)
        wbs.add_item(parent)
        child = WBSItem(
            project_id=project_id, code="1.1", name="Child", level=2, parent_id=parent.id
        )
        wbs.add_item(child)

        # Invalid: changing code to 2.1 doesn't start with parent code "1"
        with pytest.raises(ValueError, match="must start with parent code"):
            wbs.update_item(child.id, code="2.1")
