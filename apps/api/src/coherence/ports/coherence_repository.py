"""
Coherence Repository Interface (Port).

Defines the contract for persisting coherence calculation results.
Refers to Suite ID: TS-INT-DB-COH-001.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.coherence.application.dtos import CoherenceCalculationResult


class ICoherenceRepository(ABC):
    """Repository interface for coherence calculation results."""

    @abstractmethod
    async def save(self, result: CoherenceCalculationResult) -> UUID:
        """
        Save a coherence calculation result.

        Args:
            result: Coherence calculation result to save

        Returns:
            UUID of the saved record
        """
        ...

    @abstractmethod
    async def get_by_id(self, result_id: UUID) -> CoherenceCalculationResult | None:
        """
        Get a coherence result by ID.

        Args:
            result_id: UUID of the result

        Returns:
            CoherenceCalculationResult or None if not found
        """
        ...

    @abstractmethod
    async def get_latest_for_project(
        self, project_id: UUID
    ) -> CoherenceCalculationResult | None:
        """
        Get the most recent coherence result for a project.

        Args:
            project_id: Project UUID

        Returns:
            Most recent CoherenceCalculationResult or None
        """
        ...

    @abstractmethod
    async def list_for_project(
        self, project_id: UUID, skip: int = 0, limit: int = 10
    ) -> tuple[list[CoherenceCalculationResult], int]:
        """
        List coherence results for a project with pagination.

        Args:
            project_id: Project UUID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (list of results, total count)
        """
        ...

    @abstractmethod
    async def delete(self, result_id: UUID) -> bool:
        """
        Delete a coherence result.

        Args:
            result_id: UUID of the result to delete

        Returns:
            True if deleted, False if not found
        """
        ...

    @abstractmethod
    async def get_project_tenant_id(self, project_id: UUID) -> UUID | None:
        """
        Get the tenant ID for a project.

        Args:
            project_id: Project UUID

        Returns:
            Tenant UUID or None if project not found
        """
        ...

    @abstractmethod
    async def commit(self) -> None:
        """Commit pending changes to the repository."""
        ...
