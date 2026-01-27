"""
Use Case for listing documents for a specific project.
"""
from typing import List, Tuple
from uuid import UUID

from src.documents.domain.models import Document
from src.documents.ports.document_repository import IDocumentRepository

class ListProjectDocumentsUseCase:
    def __init__(self, document_repository: IDocumentRepository):
        self.document_repository = document_repository

    async def execute(
        self, project_id: UUID, tenant_id: UUID, skip: int = 0, limit: int = 20
    ) -> Tuple[List[Document], int]:
        """
        Lists documents for a specific project, with pagination and tenant isolation.
        Returns a tuple of (list of Document domain entities, total count).
        """
        # The document_repository is expected to handle tenant isolation implicitly
        # (e.g., via the session context or tenant-aware queries).
        # Authorization for the project itself should ideally happen in a higher layer
        # or a Project-specific repository/service.
        
        # For now, we trust the repository to return only documents accessible by the current tenant_id context.
        documents, total_count = await self.document_repository.list_for_project(
            project_id, skip, limit
        )
        return documents, total_count
