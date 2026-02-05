"""
WBS aggregate-level validation rules.

Refers to Suite ID: TS-UD-PRJ-WBS-003.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from uuid import UUID

from .wbs_item_entity import WBSItem


class WBSValidationRules:
    """Validates consistency rules across a list of WBS items."""

    def __init__(self, max_children_per_parent: int = 9) -> None:
        self.max_children_per_parent = max_children_per_parent

    def validate(self, items: list[WBSItem]) -> list[str]:
        if not items:
            return []

        errors: list[str] = []
        by_id: dict[UUID, WBSItem] = {item.id: item for item in items}

        project_ids = {item.project_id for item in items}
        if len(project_ids) > 1:
            errors.append("multiple project ids detected")

        codes = [item.code for item in items]
        duplicate_codes = [code for code, count in Counter(codes).items() if count > 1]
        for code in duplicate_codes:
            errors.append(f"duplicate code: {code}")

        roots = [item for item in items if item.level == 1]
        if len(roots) != 1:
            errors.append("single root required")

        for root in roots:
            if root.parent_id is not None:
                errors.append("root cannot have parent")

        children_by_parent: dict[UUID, list[WBSItem]] = defaultdict(list)
        for item in items:
            if item.parent_id is None:
                continue
            parent = by_id.get(item.parent_id)
            if parent is None:
                errors.append(f"missing parent for item {item.code}")
                continue
            children_by_parent[parent.id].append(item)

            if item.level != parent.level + 1:
                errors.append(f"level gap for item {item.code}")
            if not item.code.startswith(f"{parent.code}."):
                errors.append(f"parent prefix mismatch for item {item.code}")

        for parent_id, children in children_by_parent.items():
            if len(children) > self.max_children_per_parent:
                errors.append(f"too many children for parent {parent_id}")

            names = [child.name.strip().lower() for child in children]
            duplicate_names = [name for name, count in Counter(names).items() if count > 1]
            for dup_name in duplicate_names:
                errors.append(f"duplicate sibling name: {dup_name}")

            suffixes: list[int] = []
            for child in children:
                suffix = child.code.split(".")[-1]
                if suffix.isdigit():
                    suffixes.append(int(suffix))
            if suffixes:
                ordered = sorted(set(suffixes))
                expected = list(range(1, len(ordered) + 1))
                if ordered != expected:
                    errors.append(f"non-contiguous sibling sequence under parent {parent_id}")

        for item in items:
            if item.parent_id is None:
                continue
            if self._has_cycle(item=item, by_id=by_id):
                errors.append(f"cycle detected at item {item.code}")

        return errors

    def _has_cycle(self, item: WBSItem, by_id: dict[UUID, WBSItem]) -> bool:
        seen: set[UUID] = set()
        current = item
        while current.parent_id is not None:
            if current.id in seen:
                return True
            seen.add(current.id)
            parent = by_id.get(current.parent_id)
            if parent is None:
                return False
            current = parent
        return False
