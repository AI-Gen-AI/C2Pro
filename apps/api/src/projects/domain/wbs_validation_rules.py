"""
WBS aggregate-level validation rules.

Test Suite: TS-UD-WBS-003
Phase: REFACTOR (Triangulation complete)

This module provides comprehensive validation for Work Breakdown Structure (WBS)
hierarchies, ensuring data consistency and integrity across WBS items.

Example:
    >>> from uuid import uuid4
    >>> from src.projects.domain.wbs_item_entity import WBSItem
    >>>
    >>> project_id = uuid4()
    >>> root = WBSItem(project_id=project_id, code="1", level=1, name="Project")
    >>> child = WBSItem(
    ...     project_id=project_id,
    ...     code="1.1",
    ...     level=2,
    ...     name="Task",
    ...     parent_id=root.id
    ... )
    >>>
    >>> validator = WBSValidationRules()
    >>> errors = validator.validate([root, child])
    >>> assert errors == []
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Final
from uuid import UUID

from .wbs_item_entity import WBSItem


@dataclass(frozen=True)
class ValidationError:
    """Represents a single validation error with context."""

    code: str
    message: str
    context: dict[str, str] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"[{self.code}] {self.message} ({context_str})"
        return f"[{self.code}] {self.message}"


@dataclass
class ValidationResult:
    """Contains the result of a WBS validation operation."""

    errors: list[ValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Returns True if no validation errors were found."""
        return len(self.errors) == 0

    @property
    def error_messages(self) -> list[str]:
        """Returns a list of human-readable error messages."""
        return [str(error) for error in self.errors]

    def add_error(self, error_code: str, message: str, **context: str) -> None:
        """Add a validation error."""
        self.errors.append(ValidationError(error_code, message, context))


class WBSValidationError(Exception):
    """Base exception for WBS validation errors."""
    pass


class WBSValidationRules:
    """
    Validates consistency rules across a list of WBS items.

    This validator ensures WBS hierarchies follow these rules:
    - Single root: Exactly one item at level 1
    - Consistent project: All items belong to same project
    - Unique codes: No duplicate WBS codes
    - Valid parent-child relationships
    - Contiguous sibling numbering
    - No cycles in parent chains

    Attributes:
        max_children_per_parent: Maximum allowed children per parent (default: 9)
        max_depth: Maximum allowed hierarchy depth (default: 10)

    Example:
        >>> validator = WBSValidationRules(max_children_per_parent=5)
        >>> result = validator.validate_with_result(wbs_items)
        >>> if not result.is_valid:
        ...     for error in result.errors:
        ...         print(error)
    """

    # Configuration constants
    DEFAULT_MAX_CHILDREN: Final[int] = 9
    DEFAULT_MAX_DEPTH: Final[int] = 10
    ROOT_LEVEL: Final[int] = 1

    def __init__(
        self,
        max_children_per_parent: int = DEFAULT_MAX_CHILDREN,
        max_depth: int = DEFAULT_MAX_DEPTH
    ) -> None:
        """
        Initialize validation rules with configurable limits.

        Args:
            max_children_per_parent: Maximum children allowed per parent
            max_depth: Maximum hierarchy depth allowed
        """
        self.max_children_per_parent = max_children_per_parent
        self.max_depth = max_depth

    def validate(self, items: list[WBSItem]) -> list[str]:
        """
        Validate a list of WBS items and return error messages.

        This is the main validation entry point. It performs all validation
        checks and returns a list of error messages.

        Args:
            items: List of WBS items to validate

        Returns:
            List of error message strings (empty if valid)

        Example:
            >>> errors = validator.validate(wbs_items)
            >>> if errors:
            ...     print(f"Found {len(errors)} validation errors")
        """
        result = self.validate_with_result(items)
        return result.error_messages

    def validate_with_result(self, items: list[WBSItem]) -> ValidationResult:
        """
        Validate a list of WBS items and return detailed result.

        This method provides more detailed error information than validate(),
        including error codes and context.

        Args:
            items: List of WBS items to validate

        Returns:
            ValidationResult containing errors with codes and context
        """
        result = ValidationResult()

        if not items:
            return result

        # Build lookup tables
        by_id: dict[UUID, WBSItem] = {item.id: item for item in items}
        {item.code: item for item in items}

        # Run all validation checks
        self._validate_single_project(items, result)
        self._validate_duplicate_codes(items, result)
        self._validate_root_rules(items, result)
        self._validate_parent_relationships(items, by_id, result)
        self._validate_sibling_rules(items, by_id, result)
        self._validate_cycles(items, by_id, result)
        self._validate_depth_limits(items, result)

        return result

    def _validate_single_project(self, items: list[WBSItem], result: ValidationResult) -> None:
        """Validate all items belong to the same project."""
        project_ids = {item.project_id for item in items}
        if len(project_ids) > 1:
            result.add_error(
                "MULTIPLE_PROJECTS",
                "multiple project ids detected",
                project_ids=str(len(project_ids))
            )

    def _validate_duplicate_codes(self, items: list[WBSItem], result: ValidationResult) -> None:
        """Validate no duplicate WBS codes exist."""
        code_counts = Counter(item.code for item in items)
        for code, count in code_counts.items():
            if count > 1:
                result.add_error(
                    "DUPLICATE_CODE",
                    f"duplicate code: {code}",
                    item_code=code,
                    count=str(count)
                )

    def _validate_root_rules(self, items: list[WBSItem], result: ValidationResult) -> None:
        """Validate root item rules (single root, no parent)."""
        roots = [item for item in items if item.level == self.ROOT_LEVEL]

        if len(roots) != 1:
            result.add_error(
                "SINGLE_ROOT_REQUIRED",
                "single root required",
                root_count=str(len(roots))
            )

        for root in roots:
            if root.parent_id is not None:
                result.add_error(
                    "ROOT_WITH_PARENT",
                    "root cannot have parent",
                    code=root.code
                )

    def _validate_parent_relationships(
        self,
        items: list[WBSItem],
        by_id: dict[UUID, WBSItem],
        result: ValidationResult
    ) -> None:
        """Validate parent-child relationships."""
        for item in items:
            if item.parent_id is None:
                continue

            parent = by_id.get(item.parent_id)

            # Check parent exists
            if parent is None:
                result.add_error(
                    "MISSING_PARENT",
                    f"missing parent for item {item.code}",
                    item_code=item.code,
                    parent_id=str(item.parent_id)
                )
                continue

            # Check level consistency
            expected_level = parent.level + 1
            if item.level != expected_level:
                result.add_error(
                    "LEVEL_GAP",
                    f"level gap for item {item.code}",
                    item_code=item.code,
                    actual_level=str(item.level),
                    expected_level=str(expected_level)
                )

            # Check code prefix
            expected_prefix = f"{parent.code}."
            if not item.code.startswith(expected_prefix):
                result.add_error(
                    "PREFIX_MISMATCH",
                    f"parent prefix mismatch for item {item.code}",
                    item_code=item.code,
                    parent_code=parent.code
                )

    def _validate_sibling_rules(
        self,
        items: list[WBSItem],
        by_id: dict[UUID, WBSItem],
        result: ValidationResult
    ) -> None:
        """Validate sibling rules (unique names, max count, contiguous)."""
        children_by_parent: dict[UUID, list[WBSItem]] = defaultdict(list)

        for item in items:
            if item.parent_id is not None and item.parent_id in by_id:
                children_by_parent[item.parent_id].append(item)

        for parent_id, children in children_by_parent.items():
            parent = by_id[parent_id]

            # Check max children
            if len(children) > self.max_children_per_parent:
                result.add_error(
                    "TOO_MANY_CHILDREN",
                    f"too many children for parent {parent_id}",
                    parent_code=parent.code,
                    child_count=str(len(children)),
                    max_allowed=str(self.max_children_per_parent)
                )

            # Check duplicate names (case-insensitive)
            name_counts = Counter(child.name.strip().lower() for child in children)
            for name, count in name_counts.items():
                if count > 1:
                    result.add_error(
                        "DUPLICATE_SIBLING_NAME",
                        f"duplicate sibling name: {name}",
                        parent_code=parent.code,
                        sibling_name=name,
                        count=str(count)
                    )

            # Check contiguous sequence
            self._validate_contiguous_sequence(parent, children, result)

    def _validate_contiguous_sequence(
        self,
        parent: WBSItem,
        children: list[WBSItem],
        result: ValidationResult
    ) -> None:
        """Validate sibling codes form a contiguous sequence (1, 2, 3...)."""
        suffixes: list[int] = []

        for child in children:
            try:
                suffix = int(child.code.split(".")[-1])
                suffixes.append(suffix)
            except (ValueError, IndexError):
                result.add_error(
                    "INVALID_SUFFIX",
                    f"Item '{child.code}' has non-numeric suffix",
                    code=child.code
                )

        if suffixes:
            unique_sorted = sorted(set(suffixes))
            expected = list(range(1, len(unique_sorted) + 1))

            if unique_sorted != expected:
                result.add_error(
                    "NON_CONTIGUOUS_SEQUENCE",
                    f"non-contiguous sibling sequence under parent {parent.id}",
                    parent_code=parent.code,
                    expected_sequence=str(expected),
                    actual_sequence=str(unique_sorted)
                )

    def _validate_cycles(
        self,
        items: list[WBSItem],
        by_id: dict[UUID, WBSItem],
        result: ValidationResult
    ) -> None:
        """Validate no cycles exist in parent chains."""
        for item in items:
            if item.parent_id is None:
                continue

            if self._has_cycle(item, by_id):
                result.add_error(
                    "CYCLE_DETECTED",
                    f"cycle detected at item {item.code}",
                    item_code=item.code
                )

    def _validate_depth_limits(self, items: list[WBSItem], result: ValidationResult) -> None:
        """Validate hierarchy depth does not exceed maximum."""
        for item in items:
            if item.level > self.max_depth:
                result.add_error(
                    "MAX_DEPTH_EXCEEDED",
                    f"Item '{item.code}' exceeds maximum depth of {self.max_depth}",
                    code=item.code,
                    level=str(item.level),
                    max_depth=str(self.max_depth)
                )

    def _has_cycle(self, item: WBSItem, by_id: dict[UUID, WBSItem]) -> bool:
        """
        Check if following parent chain from item leads to a cycle.

        Args:
            item: Starting item to check
            by_id: Lookup dictionary of items by ID

        Returns:
            True if a cycle is detected
        """
        seen: set[UUID] = set()
        current: WBSItem | None = item

        while current is not None:
            if current.id in seen:
                return True
            seen.add(current.id)

            if current.parent_id is None:
                return False
            current = by_id.get(current.parent_id)

        return False

    def _get_cycle_path(self, item: WBSItem, by_id: dict[UUID, WBSItem]) -> list[str]:
        """
        Get the cycle path as a list of item codes.

        Args:
            item: Item in the cycle
            by_id: Lookup dictionary of items by ID

        Returns:
            List of codes showing the cycle path
        """
        path: list[str] = []
        seen: set[UUID] = set()
        current: WBSItem | None = item

        while current is not None and current.id not in seen:
            path.append(current.code)
            seen.add(current.id)

            if current.parent_id is None:
                break
            current = by_id.get(current.parent_id)

        if current is not None and current.id in seen:
            # Found cycle, show path back to start
            cycle_start = path.index(current.code)
            cycle_path = path[cycle_start:] + [current.code]
            return cycle_path

        return path
