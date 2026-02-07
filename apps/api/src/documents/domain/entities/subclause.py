"""
TS-UD-DOC-CLS-003: SubClause hierarchy domain entity.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from uuid import UUID, uuid4


_CODE_PATTERN = re.compile(r"^\d+(?:\.(?:\d+|[a-z]))*$")


def _normalize_code(code: str) -> str:
    normalized = code.strip().lower()
    if not normalized or not _CODE_PATTERN.match(normalized):
        raise ValueError("Invalid subclause code")
    return normalized


def _calculate_level(code: str) -> int:
    return len(code.split("."))


@dataclass(frozen=True)
class SubClause:
    """
    Represents a hierarchical subclause within a clause.
    """

    id: UUID
    clause_id: UUID
    code: str
    level: int
    parent_id: UUID | None = None

    @classmethod
    def create(cls, clause_id: UUID, code: str, parent_id: UUID | None = None) -> "SubClause":
        """Refers to Suite ID: TS-UD-DOC-CLS-003."""
        normalized = _normalize_code(code)
        level = _calculate_level(normalized)
        if level == 1 and parent_id is not None:
            raise ValueError("Root subclause cannot have a parent")
        return cls(
            id=uuid4(),
            clause_id=clause_id,
            code=normalized,
            level=level,
            parent_id=parent_id,
        )

    def can_be_child_of(self, parent: "SubClause") -> bool:
        """Checks if the given parent is valid for this subclause."""
        if self.clause_id != parent.clause_id:
            return False
        if self.level != parent.level + 1:
            return False
        return self.code.startswith(f"{parent.code}.")

    def validate_parent(self, parent: "SubClause") -> None:
        """Raises if the provided parent is not valid for this subclause."""
        if not self.can_be_child_of(parent):
            raise ValueError("Invalid parent reference")
