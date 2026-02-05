"""
WBS domain entities and aggregate.

Refers to Suite ID: TS-UD-PRJ-WBS-001.
"""

from __future__ import annotations

import re
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WBSItem(BaseModel):
    """Refers to Suite ID: TS-UD-PRJ-WBS-001."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    parent_id: UUID | None = None
    code: str
    name: str
    level: int
    description: str | None = None

    @field_validator("code")
    @classmethod
    def validate_code_format(cls, value: str) -> str:
        if not re.match(r"^\d+(\.\d+)*$", value):
            raise ValueError("Invalid WBS code format")
        return value

    @field_validator("level")
    @classmethod
    def validate_level_range(cls, value: int) -> int:
        if not 1 <= value <= 4:
            raise ValueError("WBS level must be between 1 and 4")
        return value

    @model_validator(mode="after")
    def validate_level_matches_code_depth(self) -> WBSItem:
        if self.level != len(self.code.split(".")):
            raise ValueError("WBS level must match the depth of the code")
        return self


class WBS:
    """Refers to Suite ID: TS-UD-PRJ-WBS-001."""

    def __init__(self, project_id: UUID) -> None:
        self.project_id = project_id
        self._items: dict[UUID, WBSItem] = {}
        self._codes: dict[str, UUID] = {}

    def add_item(self, item: WBSItem) -> None:
        if item.project_id != self.project_id:
            raise ValueError("WBSItem's project_id does not match the WBS project_id")

        if item.code in self._codes:
            raise ValueError(f"WBS code '{item.code}' already exists in this project")

        if item.parent_id is not None:
            parent = self._items.get(item.parent_id)
            if parent is None:
                raise ValueError(f"Parent WBS item with ID '{item.parent_id}' not found")
            if item.level != parent.level + 1:
                raise ValueError("Child WBS level must be one greater than parent level")
            if not item.code.startswith(f"{parent.code}."):
                raise ValueError("Child WBS code must start with parent code")

        self._items[item.id] = item
        self._codes[item.code] = item.id

    def get_item(self, item_id: UUID) -> WBSItem | None:
        return self._items.get(item_id)

    def get_all_items(self) -> list[WBSItem]:
        return list(self._items.values())

    def list_items(self, level: int | None = None) -> list[WBSItem]:
        items = self.get_all_items()
        if level is None:
            return items
        return [item for item in items if item.level == level]

    def update_item(
        self,
        item_id: UUID,
        *,
        code: str | None = None,
        name: str | None = None,
        description: str | None = None,
    ) -> WBSItem:
        item = self._items.get(item_id)
        if item is None:
            raise ValueError(f"WBS item '{item_id}' not found")

        update_payload: dict[str, object] = {}
        if code is not None:
            current_owner = self._codes.get(code)
            if current_owner is not None and current_owner != item_id:
                raise ValueError(f"WBS code '{code}' already exists in this project")
            update_payload["code"] = code
            update_payload["level"] = len(code.split("."))
        if name is not None:
            update_payload["name"] = name
        if description is not None:
            update_payload["description"] = description

        updated = item.model_copy(update=update_payload)

        if updated.parent_id is not None:
            parent = self._items.get(updated.parent_id)
            if parent is None:
                raise ValueError(f"Parent WBS item with ID '{updated.parent_id}' not found")
            if updated.level != parent.level + 1:
                raise ValueError("Child WBS level must be one greater than parent level")
            if not updated.code.startswith(f"{parent.code}."):
                raise ValueError("Child WBS code must start with parent code")

        if item.code != updated.code:
            self._codes.pop(item.code, None)
            self._codes[updated.code] = updated.id

        self._items[item_id] = updated
        return updated

    def delete_item(self, item_id: UUID) -> None:
        item = self._items.get(item_id)
        if item is None:
            raise ValueError(f"WBS item '{item_id}' not found")

        has_children = any(candidate.parent_id == item_id for candidate in self._items.values())
        if has_children:
            raise ValueError(f"WBS item '{item_id}' has children")

        self._items.pop(item_id, None)
        self._codes.pop(item.code, None)
