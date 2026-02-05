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
