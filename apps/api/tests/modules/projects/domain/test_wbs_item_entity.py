
import pytest
from uuid import uuid4, UUID
from pydantic import ValidationError

# This import will fail as the modules do not exist yet.
from apps.api.src.projects.domain.wbs_item_entity import WBSItem, WBS

# --- Test Data and Fixtures ---
@pytest.fixture
def minimal_wbs_item_data():
    return {
        "project_id": uuid4(),
        "code": "1",
        "name": "Phase 1",
        "level": 1,
    }

# --- Test Cases for the WBSItem Entity ---
class TestWBSItemEntity:
    """Refers to Suite ID: TS-UD-PRJ-WBS-001 (Entity-Level)"""

    def test_001_wbs_item_creation_all_fields(self, minimal_wbs_item_data):
        """Tests successful creation with all fields."""
        item_id = uuid4()
        parent_id = uuid4()
        item = WBSItem(
            **minimal_wbs_item_data, 
            id=item_id, 
            parent_id=parent_id,
            description="An optional description."
        )
        assert item.id == item_id
        assert item.parent_id == parent_id
        assert item.code == "1"
        assert item.name == "Phase 1"
        assert item.level == 1
        assert item.description == "An optional description."

    def test_002_wbs_item_creation_minimum_fields(self, minimal_wbs_item_data):
        """Tests successful creation with only required fields."""
        item = WBSItem(**minimal_wbs_item_data)
        assert isinstance(item.id, UUID)
        assert item.parent_id is None
        assert item.description is None

    @pytest.mark.parametrize("missing_field", ["code", "name", "level", "project_id"])
    def test_003_to_005_fails_without_required_fields(self, minimal_wbs_item_data, missing_field):
        data = minimal_wbs_item_data.copy()
        del data[missing_field]
        with pytest.raises(ValidationError):
            WBSItem(**data)

    def test_006_wbs_item_immutability(self, minimal_wbs_item_data):
        """Tests that a WBSItem instance is immutable."""
        item = WBSItem(**minimal_wbs_item_data)
        with pytest.raises(ValidationError, match="Instance is frozen"):
            item.name = "New Name"

    @pytest.mark.parametrize("valid_code", ["1", "1.1", "1.1.1", "1.1.1.1", "10.2.3"])
    def test_007_to_010_wbs_code_valid_format(self, minimal_wbs_item_data, valid_code):
        """Tests that valid WBS code formats are accepted."""
        level = len(valid_code.split('.'))
        item = WBSItem(**minimal_wbs_item_data, code=valid_code, level=level)
        assert item.code == valid_code

    @pytest.mark.parametrize("invalid_code", ["1.", "1.1.", ".1", "1..1", "a.1", "1.a"])
    def test_011_wbs_code_invalid_format_rejected(self, minimal_wbs_item_data, invalid_code):
        """Tests that invalid WBS code formats are rejected."""
        with pytest.raises(ValidationError, match="Invalid WBS code format"):
            WBSItem(**minimal_wbs_item_data, code=invalid_code)

    @pytest.mark.parametrize("valid_level", [1, 2, 3, 4])
    def test_013_014_wbs_level_valid(self, minimal_wbs_item_data, valid_level):
        code = ".".join(["1"] * valid_level)
        item = WBSItem(**minimal_wbs_item_data, level=valid_level, code=code)
        assert item.level == valid_level

    @pytest.mark.parametrize("invalid_level", [0, 5, -1])
    def test_015_016_wbs_level_invalid(self, minimal_wbs_item_data, invalid_level):
        """Tests that levels outside the 1-4 range are rejected."""
        with pytest.raises(ValidationError, match="WBS level must be between 1 and 4"):
            WBSItem(**minimal_wbs_item_data, level=invalid_level)

    def test_017_wbs_level_matches_code_depth(self, minimal_wbs_item_data):
        """Tests that the level must match the depth of the code."""
        with pytest.raises(ValidationError, match="WBS level must match the depth of the code"):
            # Code '1.1' has depth 2, but level is 3
            WBSItem(**minimal_wbs_item_data, code="1.1", level=3)
        # Should pass
        item = WBSItem(**minimal_wbs_item_data, code="1.1.1", level=3)
        assert item.level == 3


# --- Test Cases for the WBS Aggregate ---
class TestWBSAggregate:
    """Refers to Suite ID: TS-UD-PRJ-WBS-001 (Aggregate-Level)"""

    def test_012_wbs_code_uniqueness_per_project(self):
        """Tests that WBS codes must be unique within a WBS aggregate."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        item1 = WBSItem(project_id=project_id, code="1.1", name="Task 1.1", level=2)
        item2_same_code = WBSItem(project_id=project_id, code="1.1", name="Duplicate Task", level=2)
        
        wbs.add_item(item1) # Should succeed
        with pytest.raises(ValueError, match="WBS code '1.1' already exists in this project"):
            wbs.add_item(item2_same_code)

    def test_018_wbs_level_parent_child_validation(self):
        """Tests the parent-child relationship validation within the WBS."""
        project_id = uuid4()
        wbs = WBS(project_id=project_id)
        
        parent = WBSItem(project_id=project_id, code="1", name="Phase 1", level=1)
        wbs.add_item(parent)

        # Valid child
        child = WBSItem(project_id=project_id, code="1.1", name="Task 1.1", level=2, parent_id=parent.id)
        wbs.add_item(child)
        assert wbs.get_item(child.id) is not None

        # Invalid: child level does not match parent level
        invalid_child_level = WBSItem(project_id=project_id, code="1.2", name="Task 1.2", level=3, parent_id=parent.id)
        with pytest.raises(ValueError, match="Child WBS level must be one greater than parent level"):
            wbs.add_item(invalid_child_level)

        # Invalid: parent_id does not exist
        non_existent_parent_id = uuid4()
        invalid_child_parent = WBSItem(project_id=project_id, code="2.1", name="Task 2.1", level=2, parent_id=non_existent_parent_id)
        with pytest.raises(ValueError, match=f"Parent WBS item with ID '{non_existent_parent_id}' not found"):
            wbs.add_item(invalid_child_parent)
