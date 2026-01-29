"""
Stakeholder Repository Interface (Port).
Defines the contract for interacting with stakeholder persistence.
"""
from abc import ABC, abstractmethod
from typing import List, Tuple
from uuid import UUID

from src.stakeholders.domain.models import Stakeholder, RaciAssignment # Assuming RACI will be handled by stakeholder module


class IStakeholderRepository(ABC):
    @abstractmethod
    async def add(self, stakeholder: Stakeholder) -> None:
        """Adds a new stakeholder to the repository."""
        pass

    @abstractmethod
    async def get_by_id(self, stakeholder_id: UUID) -> Stakeholder | None:
        """Retrieves a stakeholder by its ID."""
        pass

    @abstractmethod
    async def get_stakeholders_by_project(self, project_id: UUID, skip: int = 0, limit: int = 100) -> Tuple[List[Stakeholder], int]:
        """Retrieves all stakeholders for a given project with pagination."""
        pass

    @abstractmethod
    async def update(self, stakeholder: Stakeholder) -> None:
        """Updates an existing stakeholder."""
        pass

    @abstractmethod
    async def delete(self, stakeholder_id: UUID) -> None:
        """Deletes a stakeholder by its ID."""
        pass

    @abstractmethod
    async def add_raci_assignment(self, assignment: RaciAssignment) -> None:
        """Adds a new RACI assignment."""
        pass

    @abstractmethod
    async def list_raci_assignments(self, project_id: UUID) -> List[RaciAssignment]:
        """Lists RACI assignments for a project."""
        pass

    @abstractmethod
    async def get_raci_assignment(
        self, project_id: UUID, wbs_item_id: UUID, stakeholder_id: UUID
    ) -> RaciAssignment | None:
        """Retrieves a single RACI assignment by composite key."""
        pass

    @abstractmethod
    async def get_accountable_assignment(
        self,
        project_id: UUID,
        wbs_item_id: UUID,
        exclude_stakeholder_id: UUID | None = None,
    ) -> RaciAssignment | None:
        """Finds an existing ACCOUNTABLE assignment for a task."""
        pass

    @abstractmethod
    async def update_raci_assignment(self, assignment: RaciAssignment) -> None:
        """Updates an existing RACI assignment."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commits pending changes to the repository."""
        pass

    @abstractmethod
    async def refresh(self, entity: object) -> None:
        """Refreshes the state of an entity from the repository."""
        pass
