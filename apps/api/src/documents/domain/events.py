"""
Domain events for documents bounded context.

Refers to Suite ID: TS-UD-DOC-CLS-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.core.json_types import JsonDict


@dataclass(slots=True)
class ClauseEntitiesExtracted:
    """Event emitted when entities are extracted from a clause."""

    clause_id: UUID
    extracted_entities: list[JsonDict]

