from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from src.core.tenants.types import require_tenant_id
from src.documents.ports.document_repository import IDocumentRepository


class GetClauseTextMapUseCase:
    def __init__(self, document_repository: IDocumentRepository) -> None:
        self.document_repository = document_repository

    async def execute(self, tenant_id: UUID, clause_ids: Iterable[UUID]) -> dict[UUID, str]:
        ids = [clause_id for clause_id in clause_ids if clause_id]
        if not ids:
            return {}
        return await self.document_repository.get_clause_text_map(require_tenant_id(tenant_id), ids)
