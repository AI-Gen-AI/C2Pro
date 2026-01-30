from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.application.dtos import RagAnswer
from src.documents.adapters.rag.rag_service import RagService
from src.documents.ports.rag_service import IRagService


class SqlAlchemyRagService(IRagService):
    def __init__(self, db_session: AsyncSession) -> None:
        self.rag_service = RagService(db_session)

    async def answer_question(
        self, *, question: str, project_id: UUID, top_k: int
    ) -> RagAnswer:
        return await self.rag_service.answer_question(
            question=question,
            project_id=project_id,
            top_k=top_k,
        )
