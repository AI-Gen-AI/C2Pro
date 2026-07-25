"""
Branch coverage tests for WBS hierarchy operations.

Test Suite: TS-UD-WBS-002
"""

from __future__ import annotations

import pytest

from src.projects.domain.wbs_hierarchy import (
    InvalidWBSCodeError,
    WBSHierarchy,
)


class TestValidateCodeFalsy:
    def test_validate_code_empty_string_returns_false(self) -> None:
        assert WBSHierarchy.validate_code("") is False

    def test_validate_code_none_returns_false(self) -> None:
        assert WBSHierarchy.validate_code(None) is False  # type: ignore[arg-type]

    def test_validate_code_leading_zeros(self) -> None:
        assert WBSHierarchy.validate_code("01") is False

    def test_validate_code_leading_zeros_nested(self) -> None:
        assert WBSHierarchy.validate_code("1.01") is False

    def test_validate_code_exceeds_max_depth(self) -> None:
        assert WBSHierarchy.validate_code("1.2.3.4.5.6.7.8.9.10.11") is False

    def test_validate_code_within_custom_depth(self) -> None:
        assert WBSHierarchy.validate_code("1.2.3", max_depth=3) is True
        assert WBSHierarchy.validate_code("1.2.3.4", max_depth=3) is False


class TestValidateHierarchyEmpty:
    def test_validate_hierarchy_empty_codes_returns_none(self) -> None:
        result = WBSHierarchy.validate_hierarchy_codes([])
        assert result is None

    def test_validate_hierarchy_duplicate_codes_raises(self) -> None:
        with pytest.raises(InvalidWBSCodeError, match="Duplicate code: 1"):
            WBSHierarchy.validate_hierarchy_codes(["1", "1"])


class TestGetAncestors:
    def test_get_ancestors_returns_chain(self) -> None:
        assert WBSHierarchy.get_ancestors("1.2.3") == ["1", "1.2"]

    def test_get_ancestors_root_returns_empty(self) -> None:
        assert WBSHierarchy.get_ancestors("1") == []

    def test_get_ancestors_two_levels(self) -> None:
        assert WBSHierarchy.get_ancestors("1.2") == ["1"]
