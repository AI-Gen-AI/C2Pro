"""
Use Case for answering questions over project documents (RAG).
"""
from uuid import UUID

from src.documents.application.dtos import RagAnswer
from src.documents.ports.rag_service import IRagService


class AnswerRagQuestionUseCase:
    def __init__(self, rag_service: IRagService) -> None:
        self.rag_service = rag_service

    async def execute(
        self,
        *,
        question: str,
        project_id: UUID,
        top_k: int,
    ) -> RagAnswer:
        return await self.rag_service.answer_question(
            question=question,
            project_id=project_id,
            top_k=top_k,
        )
