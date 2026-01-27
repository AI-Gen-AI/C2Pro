from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from uuid import UUID

from apps.api.src.modules.documents.domain.models import Document, DocumentStatus, DocumentType
from apps.api.src.modules.documents.application.dtos import DocumentListItem
from apps.api.src.core.database import AsyncSession


class DocumentRepository(ABC):
    @abstractmethod
    async def get_by_id(self, document_id: UUID, tenant_id: UUID) -> Optional[Document]:
        pass

    @abstractmethod
    async def add(self, document: Document, db_session: AsyncSession) -> Document:
        pass

    @abstractmethod
    async def update(self, document: Document, db_session: AsyncSession) -> Document:
        pass

    @abstractmethod
    async def delete(self, document: Document, db_session: AsyncSession):
        pass

    @abstractmethod
    async def list_by_project_id(
        self, project_id: UUID, tenant_id: UUID, skip: int = 0, limit: int = 20
    ) -> Tuple[List[DocumentListItem], int]:
        pass

    @abstractmethod
    async def get_tenant_id_from_project(self, project_id: UUID) -> Optional[UUID]:
        pass

