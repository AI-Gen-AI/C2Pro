"""
WBS hierarchy and code rules tests (TDD - RED phase).

Refers to Suite ID: TS-UD-PRJ-WBS-002.
"""

from __future__ import annotations

import pytest

from src.projects.domain.wbs_hierarchy import WBSHierarchy


class TestWBSHierarchyCodes:
    """Refers to Suite ID: TS-UD-PRJ-WBS-002"""

    def test_001_root_code_numeric_is_valid(self) -> None:
        assert WBSHierarchy.validate_code("1") is True

    def test_002_root_code_non_numeric_is_invalid(self) -> None:
        assert WBSHierarchy.validate_code("A") is False

    def test_003_next_child_code_without_siblings(self) -> None:
        code = WBSHierarchy.next_child_code(parent_code="1", existing_codes=[])
        assert code == "1.1"

    def test_004_next_child_code_with_existing_siblings(self) -> None:
        code = WBSHierarchy.next_child_code(parent_code="1", existing_codes=["1.1", "1.2"])
        assert code == "1.3"

    def test_005_next_child_code_handles_multi_digit_suffix(self) -> None:
        code = WBSHierarchy.next_child_code(parent_code="1", existing_codes=["1.9", "1.10"])
        assert code == "1.11"

    def test_006_parent_code_of_level_2(self) -> None:
        assert WBSHierarchy.parent_code("1.1") == "1"

    def test_007_parent_code_of_level_4(self) -> None:
        assert WBSHierarchy.parent_code("1.2.3.4") == "1.2.3"

    def test_008_parent_code_of_root_is_none(self) -> None:
        assert WBSHierarchy.parent_code("1") is None

    def test_009_is_descendant_direct_child(self) -> None:
        assert WBSHierarchy.is_descendant(parent_code="1", candidate_code="1.1") is True

    def test_010_is_descendant_deep_child(self) -> None:
        assert WBSHierarchy.is_descendant(parent_code="1", candidate_code="1.2.3") is True

    def test_011_is_descendant_prefix_trap_is_false(self) -> None:
        assert WBSHierarchy.is_descendant(parent_code="1.1", candidate_code="1.10") is False

    def test_012_sort_codes_uses_numeric_segments(self) -> None:
        sorted_codes = WBSHierarchy.sort_codes(["1.10", "1.2", "1.1"])
        assert sorted_codes == ["1.1", "1.2", "1.10"]

    def test_013_validate_hierarchy_rejects_orphan_child(self) -> None:
        with pytest.raises(ValueError, match="Missing parent code"):
            WBSHierarchy.validate_hierarchy_codes(["1.2"])

    def test_014_validate_hierarchy_accepts_consistent_tree(self) -> None:
        WBSHierarchy.validate_hierarchy_codes(["1", "1.1", "1.1.1", "1.2"])
