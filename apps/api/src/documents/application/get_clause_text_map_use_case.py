from __future__ import annotations

from typing import Iterable
from uuid import UUID

from src.documents.ports.document_repository import IDocumentRepository


class GetClauseTextMapUseCase:
    def __init__(self, document_repository: IDocumentRepository) -> None:
        self.document_repository = document_repository

    async def execute(self, clause_ids: Iterable[UUID]) -> dict[UUID, str]:
        ids = [clause_id for clause_id in clause_ids if clause_id]
        if not ids:
            return {}
        return await self.document_repository.get_clause_text_map(ids)
