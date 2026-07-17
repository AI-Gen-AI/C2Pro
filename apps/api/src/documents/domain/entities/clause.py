"""
Legacy Clause entity compatibility layer.

Refers to Suite ID: TS-UD-DOC-CLS-001.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from src.core.json_types import JsonDict
from src.documents.domain.events import ClauseEntitiesExtracted
from src.documents.domain.exceptions import DomainValidationError


class EntityExtractor(Protocol):
    """Contract for the legacy clause entity extraction collaborator."""

    def extract(self, text: str) -> list[JsonDict]: ...


@dataclass(slots=True)
class Clause:
    """Legacy clause entity used by module-domain tests."""

    clause_id: UUID
    document_id: UUID
    tenant_id: UUID
    content: str
    clause_type: str
    confidence_score: float
    events: list[object] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.document_id is None or self.tenant_id is None:
            raise DomainValidationError("document_id and tenant_id are required")
        if not self.content or not self.content.strip():
            raise DomainValidationError("content is required")
        if not (0.0 <= self.confidence_score <= 1.0):
            raise DomainValidationError("confidence_score must be between 0 and 1")

    def extract_entities(self, extractor: EntityExtractor) -> list[JsonDict]:
        extracted = extractor.extract(self.content)
        event = ClauseEntitiesExtracted(
            clause_id=self.clause_id,
            extracted_entities=extracted,
        )
        self.events.append(event)
        return extracted

