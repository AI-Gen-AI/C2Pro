"""
Use Case for checking whether a clause exists.
"""
from uuid import UUID

from src.documents.ports.document_repository import IDocumentRepository


class CheckClauseExistsUseCase:
    def __init__(self, document_repository: IDocumentRepository):
        self.document_repository = document_repository

    async def execute(self, clause_id: UUID) -> bool:
        return await self.document_repository.clause_exists(clause_id)
