"""
Clause Extraction Service Interface (Port).
Refers to Suite ID: TS-UA-DOC-UC-002.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.documents.domain.models import Clause


class IClauseExtractionService(Protocol):
    """Port for extracting clauses from document text."""

    async def extract_from_text(
        self,
        text: str,
        document_id: UUID,
        project_id: UUID,
        tenant_id: UUID,
    ) -> list[Clause]:
        """Extract clauses from raw text."""
        ...
