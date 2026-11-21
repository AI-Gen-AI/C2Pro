"""Deterministic clause inventory over the N2 projection (frozen by JV1-A1).

Implemented by A5 (lane L2), which owns this file once A1 is merged. The
provider must declare every inventoried clause as examined (with or without
risk).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

N4ClauseLanguage = Literal["EN", "ES", "PT"]

N4_CLAUSE_INVENTORY_MAX_CHARS_PER_MESSAGE = 3000
N4_CLAUSE_INVENTORY_LANGUAGES: tuple[N4ClauseLanguage, ...] = ("EN", "ES", "PT")


@dataclass(frozen=True, slots=True)
class N4InventoryClause:
    clause_ref: str
    heading: str
    start_offset: int
    end_offset: int
    language: N4ClauseLanguage | None


def build_n4_clause_inventory(projection_text: str) -> tuple[N4InventoryClause, ...]:
    """Detect clause headings (EN/ES/PT) in the N2 projection, in source order."""
    raise NotImplementedError("JV1-A5 implements the clause inventory")


def render_n4_clause_inventory_messages(
    clauses: Sequence[N4InventoryClause],
    max_chars: int = N4_CLAUSE_INVENTORY_MAX_CHARS_PER_MESSAGE,
) -> tuple[str, ...]:
    """Render the inventory as prompt messages of at most ``max_chars`` each."""
    raise NotImplementedError("JV1-A5 implements the clause inventory")
