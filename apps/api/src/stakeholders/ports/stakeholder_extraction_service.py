"""
Stakeholder Extraction Service Port.

Refers to Suite ID: TS-UA-STK-UC-001.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.stakeholders.domain.models import Stakeholder


class IStakeholderExtractionService(Protocol):
    """Port for extracting stakeholders from contract text."""

    async def extract_from_text(
        self,
        *,
        text: str,
        project_id: UUID,
        tenant_id: UUID,
    ) -> list[Stakeholder]:
        """Extract stakeholders from contract text."""
        ...
