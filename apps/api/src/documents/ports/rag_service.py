from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.documents.application.dtos import RagAnswer


class IRagService(ABC):
    @abstractmethod
    async def answer_question(
        self, *, question: str, project_id: UUID, top_k: int
    ) -> RagAnswer:
        ...
