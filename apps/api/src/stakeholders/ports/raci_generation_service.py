"""
RACI generation service port.

Refers to Suite ID: TS-UA-STK-UC-002.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.stakeholders.application.dtos import RaciGenerationResult


class IRaciGenerationService(Protocol):
    """Port for generating and persisting RACI assignments."""

    async def generate_and_persist(self, project_id: UUID) -> RaciGenerationResult:
        """Generate and persist RACI assignments for a project."""
        ...
