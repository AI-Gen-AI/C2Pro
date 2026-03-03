"""
WBS domain entities.

Refers to Suite ID: TS-CT-WBS-API-001 (GREEN phase)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID, uuid4


@dataclass(frozen=True)
class Money:
    """Value object for monetary amounts."""

    amount: float
    currency: str = "EUR"

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")
        if len(self.currency) != 3:
            raise ValueError("Currency must be 3-letter ISO code")


@dataclass(frozen=True)
class WBSItem:
    """
    WBS Item domain entity.

    Refers to Suite ID: TS-CT-WBS-API-001
    """

    id: UUID
    project_id: str
    tenant_id: str
    code: str
    name: str
    level: int
    description: str | None = None
    parent_id: UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget: Money | None = None
    completion: int = 0
    children: list[UUID] = field(default_factory=list)

    # Validation patterns
    CODE_PATTERN = re.compile(r"^\d+(\.\d+){0,3}$")
    MAX_LEVEL = 4

    def __post_init__(self) -> None:
        # Validate code format (1, 1.1, 1.1.1, 1.1.1.1)
        if not self.CODE_PATTERN.match(self.code):
            raise ValueError(f"Invalid WBS code format: {self.code}")

        # Validate level range (1-4)
        if not 1 <= self.level <= self.MAX_LEVEL:
            raise ValueError(f"WBS level must be between 1 and {self.MAX_LEVEL}")

        # Validate level matches code depth
        expected_level = len(self.code.split("."))
        if self.level != expected_level:
            raise ValueError(f"WBS level {self.level} does not match code depth {expected_level}")

        # Validate completion range
        if not 0 <= self.completion <= 100:
            raise ValueError("Completion must be between 0 and 100")

    @classmethod
    def create(
        cls,
        project_id: str,
        tenant_id: str,
        name: str,
        code: str | None = None,
        parent_id: UUID | None = None,
        description: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        budget_amount: float | None = None,
        budget_currency: str = "EUR",
        completion: int = 0,
    ) -> WBSItem:
        """Factory method to create a new WBS item."""
        if not name:
            raise ValueError("WBS item name is required")

        # Auto-generate code if not provided
        if code is None:
            # This is a placeholder - actual code generation happens in use case
            code = "1"

        # Calculate level from code
        level = len(code.split("."))

        budget = None
        if budget_amount is not None:
            budget = Money(amount=budget_amount, currency=budget_currency)

        return cls(
            id=uuid4(),
            project_id=project_id,
            tenant_id=tenant_id,
            code=code,
            name=name,
            level=level,
            description=description,
            parent_id=parent_id,
            start_date=start_date,
            end_date=end_date,
            budget=budget,
            completion=completion,
        )

    def is_ancestor_of(self, other: WBSItem) -> bool:
        """Check if this item is an ancestor of another item."""
        if other.parent_id is None:
            return False
        return other.code.startswith(f"{self.code}.")

    def can_be_moved_to(self, new_parent_id: UUID | None, all_items: dict[UUID, WBSItem]) -> bool:
        """Check if this item can be moved to the specified parent."""
        # Cannot move to self
        if new_parent_id == self.id:
            return False

        # Check for circular reference
        if new_parent_id is not None:
            new_parent = all_items.get(new_parent_id)
            if new_parent is None:
                return False

            # Cannot move to own descendant
            if new_parent.code.startswith(f"{self.code}."):
                return False

            # Check max depth constraint
            new_level = new_parent.level + 1
            if new_level > self.MAX_LEVEL:
                return False

        return True

    def with_updated_fields(
        self,
        name: str | None = None,
        description: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        budget_amount: float | None = None,
        budget_currency: str | None = None,
        completion: int | None = None,
        parent_id: UUID | None = None,
        code: str | None = None,
        children: list[UUID] | None = None,
    ) -> WBSItem:
        """Create a new instance with updated fields (immutable update)."""
        current_budget = self.budget

        if budget_amount is not None or budget_currency is not None:
            amount = budget_amount if budget_amount is not None else (current_budget.amount if current_budget else 0.0)
            currency = budget_currency if budget_currency is not None else (current_budget.currency if current_budget else "EUR")
            current_budget = Money(amount=amount, currency=currency)

        return WBSItem(
            id=self.id,
            project_id=self.project_id,
            tenant_id=self.tenant_id,
            code=code if code is not None else self.code,
            name=name if name is not None else self.name,
            level=len((code if code is not None else self.code).split(".")),
            description=description if description is not None else self.description,
            parent_id=parent_id if parent_id is not None else self.parent_id,
            start_date=start_date if start_date is not None else self.start_date,
            end_date=end_date if end_date is not None else self.end_date,
            budget=current_budget,
            completion=completion if completion is not None else self.completion,
            children=children if children is not None else self.children,
        )

    def add_child(self, child_id: UUID) -> WBSItem:
        """Add a child to this item."""
        new_children = list(self.children)
        if child_id not in new_children:
            new_children.append(child_id)
        return self.with_updated_fields(children=new_children)

    def remove_child(self, child_id: UUID) -> WBSItem:
        """Remove a child from this item."""
        new_children = [c for c in self.children if c != child_id]
        return self.with_updated_fields(children=new_children)
