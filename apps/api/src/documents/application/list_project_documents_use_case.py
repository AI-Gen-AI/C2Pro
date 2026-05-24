"""
Use Case for listing documents for a specific project.
"""
from uuid import UUID

from src.documents.domain.models import Document
from src.documents.ports.document_repository import IDocumentRepository
from src.projects.ports.project_repository import ProjectRepository


class ListProjectDocumentsUseCase:
    def __init__(
        self,
        document_repository: IDocumentRepository,
        project_repository: ProjectRepository,
    ):
        self.document_repository = document_repository
        self.project_repository = project_repository

    async def execute(
        self, project_id: UUID, tenant_id: UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[Document], int]:
        """
        Lists documents for a specific project, with pagination and tenant isolation.
        Returns a tuple of (list of Document domain entities, total count).
        """
        project = await self.project_repository.get_by_id(project_id, tenant_id)
        if project is None:
            return [], 0

        documents, total_count = await self.document_repository.list_for_project(
            tenant_id, project_id, skip, limit
        )
        return documents, total_count
