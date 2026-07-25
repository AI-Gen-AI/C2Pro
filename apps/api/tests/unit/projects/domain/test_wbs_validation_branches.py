"""
Branch coverage tests for WBS validation rules.

Test Suite: TS-UD-WBS-003
"""

from __future__ import annotations

from uuid import uuid4

from src.projects.domain.wbs_item_entity import WBSItem
from src.projects.domain.wbs_validation_rules import (
    ValidationError,
    ValidationResult,
    WBSValidationRules,
)


def _item(*, project_id, code, level, name, parent_id=None):
    return WBSItem(
        project_id=project_id,
        code=code,
        level=level,
        name=name,
        parent_id=parent_id,
    )


class TestDuplicateCodes:
    def test_duplicate_wbs_code_returns_error(self) -> None:
        project_id = uuid4()
        a = _item(project_id=project_id, code="1", level=1, name="Root A")
        b = _item(project_id=project_id, code="1", level=1, name="Root B")

        result = WBSValidationRules().validate_with_result([a, b])

        assert not result.is_valid
        errors = result.error_messages
        assert any("duplicate code" in e for e in errors)

    def test_duplicate_wbs_code_error_detail(self) -> None:
        project_id = uuid4()
        a = _item(project_id=project_id, code="1", level=1, name="Root A")
        b = _item(project_id=project_id, code="1", level=1, name="Root B")

        result = WBSValidationRules().validate_with_result([a, b])

        duplicate_errors = [
            e for e in result.errors if e.code == "DUPLICATE_CODE"
        ]
        assert len(duplicate_errors) == 1
        assert duplicate_errors[0].context["count"] == "2"


class TestMaxDepthLeafValidation:
    def test_max_depth_leaf_validates_correctly(self) -> None:
        project_id = uuid4()
        root = _item(project_id=project_id, code="1", level=1, name="Root")
        child = _item(project_id=project_id, code="1.1", level=2, name="L2", parent_id=root.id)
        grandchild = _item(project_id=project_id, code="1.1.1", level=3, name="L3", parent_id=child.id)
        leaf = _item(project_id=project_id, code="1.1.1.1", level=4, name="Leaf", parent_id=grandchild.id)

        errors = WBSValidationRules().validate([root, child, grandchild, leaf])

        assert errors == []

    def test_max_depth_with_custom_limit(self) -> None:
        project_id = uuid4()
        root = _item(project_id=project_id, code="1", level=1, name="Root")
        child = _item(project_id=project_id, code="1.1", level=2, name="L2", parent_id=root.id)
        l3 = _item(project_id=project_id, code="1.1.1", level=3, name="L3", parent_id=child.id)

        result = WBSValidationRules(max_depth=2).validate_with_result([root, child, l3])

        assert not result.is_valid
        assert any("exceeds maximum depth" in e for e in result.error_messages)


class TestValidationResult:
    def test_result_is_valid_when_empty(self) -> None:
        result = ValidationResult()
        assert result.is_valid is True
        assert result.error_messages == []

    def test_result_add_error_populates_errors(self) -> None:
        result = ValidationResult()
        result.add_error("TEST_CODE", "Test message", key="value")
        assert result.is_valid is False
        assert len(result.errors) == 1
        error = result.errors[0]
        assert error.code == "TEST_CODE"
        assert error.message == "Test message"
        assert error.context == {"key": "value"}

    def test_validation_error_str_formatting(self) -> None:
        error = ValidationError("CODE", "Message", {"a": "1"})
        output = str(error)
        assert "[CODE] Message" in output
        assert "a=1" in output
