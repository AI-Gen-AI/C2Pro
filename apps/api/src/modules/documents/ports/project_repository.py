from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

class ProjectRepositoryPort(ABC):
    @abstractmethod
    async def get_tenant_id_by_project_id(self, project_id: UUID) -> Optional[UUID]:
        pass
