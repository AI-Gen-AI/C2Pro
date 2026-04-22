"""
Stakeholder Repository Interface (Port).
Defines the contract for interacting with stakeholder persistence.
"""
from abc import ABC, abstractmethod
from uuid import UUID

from src.core.tenants.types import TenantId
from src.stakeholders.domain.models import (  # Assuming RACI will be handled by stakeholder module
    RaciAssignment,
    Stakeholder,
)


class IStakeholderRepository(ABC):
    @abstractmethod
    async def add(self, stakeholder: Stakeholder, tenant_id: TenantId) -> None:
        """Adds a new stakeholder to the repository."""
        pass

    @abstractmethod
    async def get_by_id(
        self, stakeholder_id: UUID, tenant_id: TenantId
    ) -> Stakeholder | None:
        """Retrieves a stakeholder by its ID."""
        pass

    @abstractmethod
    async def get_all_stakeholders(self, tenant_id: TenantId) -> list[Stakeholder]:
        """Retrieves all stakeholders for a given tenant."""
        pass

    @abstractmethod
    async def get_stakeholders_by_project(
        self,
        project_id: UUID,
        tenant_id: TenantId,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Stakeholder], int]:
        """Retrieves all stakeholders for a given project with pagination."""
        pass

    @abstractmethod
    async def update(self, stakeholder: Stakeholder, tenant_id: TenantId) -> None:
        """Updates an existing stakeholder with tenant verification."""
        pass

    @abstractmethod
    async def delete(self, stakeholder_id: UUID, tenant_id: TenantId) -> None:
        """Deletes a stakeholder by its ID."""
        pass

    @abstractmethod
    async def add_raci_assignment(
        self, assignment: RaciAssignment, tenant_id: TenantId
    ) -> None:
        """Adds a new RACI assignment with tenant verification."""
        pass

    @abstractmethod
    async def list_raci_assignments(
        self, project_id: UUID, tenant_id: TenantId
    ) -> list[RaciAssignment]:
        """Lists RACI assignments for a project."""
        pass

    @abstractmethod
    async def get_raci_assignment(
        self,
        project_id: UUID,
        wbs_item_id: UUID,
        stakeholder_id: UUID,
        tenant_id: TenantId,
    ) -> RaciAssignment | None:
        """Retrieves a single RACI assignment by composite key."""
        pass

    @abstractmethod
    async def get_accountable_assignment(
        self,
        project_id: UUID,
        wbs_item_id: UUID,
        tenant_id: TenantId,
        exclude_stakeholder_id: UUID | None = None,
    ) -> RaciAssignment | None:
        """Finds an existing ACCOUNTABLE assignment for a task."""
        pass

    @abstractmethod
    async def update_raci_assignment(
        self, assignment: RaciAssignment, tenant_id: TenantId
    ) -> None:
        """Updates an existing RACI assignment with tenant verification."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commits pending changes to the repository."""
        pass

    @abstractmethod
    async def refresh(self, entity: object) -> None:
        """Refreshes the state of an entity from the repository."""
        pass
