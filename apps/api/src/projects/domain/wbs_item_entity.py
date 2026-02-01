
import re
from uuid import UUID, uuid4
from typing import List, Optional, Dict

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

class WBSItem(BaseModel):
    """
    Represents a single item in a Work Breakdown Structure.
    This is an immutable domain entity. Its validity is self-contained,
    but its relationships are validated by the WBS aggregate.
    """
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    parent_id: Optional[UUID] = None
    
    code: str
    name: str
    level: int
    description: Optional[str] = None

    @field_validator('code')
    @classmethod
    def validate_code_format(cls, value: str) -> str:
        """Validates that the WBS code follows the dot-separated numeric format."""
        if not re.match(r'^\d+(\.\d+)*$', value):
            raise ValueError("Invalid WBS code format")
        return value

    @field_validator('level')
    @classmethod
    def validate_level_range(cls, value: int) -> int:
        """Validates that the level is within the allowed range."""
        if not 1 <= value <= 4:
            raise ValueError("WBS level must be between 1 and 4")
        return value

    @model_validator(mode='after')
    def validate_level_matches_code_depth(self) -> 'WBSItem':
        """Validates that the item's level matches the depth of its code."""
        code_depth = len(self.code.split('.'))
        if self.level != code_depth:
            raise ValueError("WBS level must match the depth of the code")
        return self


class WBS(BaseModel):
    """
    Represents the complete Work Breakdown Structure for a project.
    This class acts as an Aggregate Root, ensuring the consistency
    and validity of the entire WBS tree.
    """
    project_id: UUID
    _items: Dict[UUID, WBSItem] = Field(default_factory=dict, private=True)
    _codes: Dict[str, UUID] = Field(default_factory=dict, private=True)

    def add_item(self, item: WBSItem):
        """
        Adds a new WBSItem to the structure, enforcing aggregate-level rules.

        Raises:
            ValueError: If the item violates uniqueness or parent-child relationship rules.
        """
        if item.project_id != self.project_id:
            raise ValueError("WBSItem's project_id does not match the WBS project_id")

        # Rule: Uniqueness of code within the project
        if item.code in self._codes:
            raise ValueError(f"WBS code '{item.code}' already exists in this project")

        # Rule: Parent-child relationship validation
        if item.parent_id:
            if item.parent_id not in self._items:
                raise ValueError(f"Parent WBS item with ID '{item.parent_id}' not found")
            
            parent = self._items[item.parent_id]
            if item.level != parent.level + 1:
                raise ValueError("Child WBS level must be one greater than parent level")

        # If all rules pass, add the item
        self._items[item.id] = item
        self._codes[item.code] = item.id

    def get_item(self, item_id: UUID) -> Optional[WBSItem]:
        """Retrieves a WBSItem from the aggregate by its ID."""
        return self._items.get(item_id)

    def get_all_items(self) -> List[WBSItem]:
        """Returns a list of all WBSItems in the aggregate."""
        return list(self._items.values())
