"""
WBS validation rules tests (TDD - RED phase).

Refers to Suite ID: TS-UD-PRJ-WBS-003.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from src.projects.domain.wbs_item_entity import WBSItem
from src.projects.domain.wbs_validation_rules import WBSValidationRules


def _item(
    *,
    project_id: UUID,
    code: str,
    level: int,
    name: str,
    parent_id: UUID | None = None,
) -> WBSItem:
    return WBSItem(
        project_id=project_id,
        code=code,
        level=level,
        name=name,
        parent_id=parent_id,
    )


class TestWBSValidationRules:
    """Refers to Suite ID: TS-UD-PRJ-WBS-003"""

    def test_001_valid_tree_has_no_errors(self) -> None:
        project_id = uuid4()
        root = _item(project_id=project_id, code="1", level=1, name="Root")
        child = _item(project_id=project_id, code="1.1", level=2, name="Child", parent_id=root.id)

        errors = WBSValidationRules().validate([root, child])

        assert errors == []

    def test_002_reject_multiple_roots(self) -> None:
        project_id = uuid4()
        root_a = _item(project_id=project_id, code="1", level=1, name="Root A")
        root_b = _item(project_id=project_id, code="2", level=1, name="Root B")

        errors = WBSValidationRules().validate([root_a, root_b])

        assert any("single root" in error for error in errors)

    def test_003_reject_missing_parent_reference(self) -> None:
        project_id = uuid4()
        orphan = _item(project_id=project_id, code="1.1", level=2, name="Orphan", parent_id=uuid4())

        errors = WBSValidationRules().validate([orphan])

        assert any("missing parent" in error for error in errors)

    def test_004_reject_parent_child_level_gap(self) -> None:
        project_id = uuid4()
        root = _item(project_id=project_id, code="1", level=1, name="Root")
        invalid = _item(project_id=project_id, code="1.1.1", level=3, name="Invalid", parent_id=root.id)

        errors = WBSValidationRules().validate([root, invalid])

        assert any("level gap" in error for error in errors)

    def test_005_reject_child_code_without_parent_prefix(self) -> None:
        project_id = uuid4()
        root = _item(project_id=project_id, code="1", level=1, name="Root")
        invalid = _item(project_id=project_id, code="2.1", level=2, name="Invalid", parent_id=root.id)

        errors = WBSValidationRules().validate([root, invalid])

        assert any("parent prefix" in error for error in errors)

    def test_006_reject_duplicate_codes(self) -> None:
        project_id = uuid4()
        root = _item(project_id=project_id, code="1", level=1, name="Root")
        dup = _item(project_id=project_id, code="1", level=1, name="Duplicate")

        errors = WBSValidationRules().validate([root, dup])

        assert any("duplicate code" in error for error in errors)

    def test_007_reject_duplicate_sibling_names(self) -> None:
        project_id = uuid4()
        root = _item(project_id=project_id, code="1", level=1, name="Root")
        a = _item(project_id=project_id, code="1.1", level=2, name="Task", parent_id=root.id)
        b = _item(project_id=project_id, code="1.2", level=2, name="task", parent_id=root.id)

        errors = WBSValidationRules().validate([root, a, b])

        assert any("duplicate sibling name" in error for error in errors)

    def test_008_reject_too_many_children_for_parent(self) -> None:
        project_id = uuid4()
        root = _item(project_id=project_id, code="1", level=1, name="Root")
        children = [
            _item(project_id=project_id, code=f"1.{index}", level=2, name=f"Task {index}", parent_id=root.id)
            for index in range(1, 5)
        ]

        errors = WBSValidationRules(max_children_per_parent=3).validate([root, *children])

        assert any("too many children" in error for error in errors)

    def test_009_reject_non_contiguous_sibling_sequence(self) -> None:
        project_id = uuid4()
        root = _item(project_id=project_id, code="1", level=1, name="Root")
        a = _item(project_id=project_id, code="1.1", level=2, name="Task 1", parent_id=root.id)
        c = _item(project_id=project_id, code="1.3", level=2, name="Task 3", parent_id=root.id)

        errors = WBSValidationRules().validate([root, a, c])

        assert any("non-contiguous sibling sequence" in error for error in errors)

    def test_010_reject_more_than_one_project_id(self) -> None:
        root_a = _item(project_id=uuid4(), code="1", level=1, name="Root A")
        root_b = _item(project_id=uuid4(), code="2", level=1, name="Root B")

        errors = WBSValidationRules().validate([root_a, root_b])

        assert any("multiple project ids" in error for error in errors)

    def test_011_reject_root_with_parent(self) -> None:
        root = _item(project_id=uuid4(), code="1", level=1, name="Root", parent_id=uuid4())

        errors = WBSValidationRules().validate([root])

        assert any("root cannot have parent" in error for error in errors)

    def test_012_reject_cycle_in_parent_chain(self) -> None:
        project_id = uuid4()
        a = _item(project_id=project_id, code="1", level=1, name="A")
        b = _item(project_id=project_id, code="1.1", level=2, name="B", parent_id=a.id)
        a_cycle = a.model_copy(update={"parent_id": b.id})

        errors = WBSValidationRules().validate([a_cycle, b])

        assert any("cycle" in error for error in errors)
