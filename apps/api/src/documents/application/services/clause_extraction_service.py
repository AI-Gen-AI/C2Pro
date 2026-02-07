"""
Clause Extraction Service.
Refers to Suite ID: TS-UA-SVC-EXT-001.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from src.documents.domain.models import Clause, ClauseType

class ClauseExtractionService:
    """Refers to Suite ID: TS-UA-SVC-EXT-001."""

    def __init__(self, llm_port: Any) -> None:
        self.llm_port = llm_port

    async def extract_from_text(
        self,
        text: str,
        document_id: UUID,
        project_id: UUID,
        tenant_id: UUID,
    ) -> list[Clause]:
        raw_clauses = await self.llm_port.extract_clauses(
            text=text,
            document_id=document_id,
            project_id=project_id,
            tenant_id=tenant_id,
        )

        clauses: list[Clause] = []
        for raw in raw_clauses or []:
            clause_type = _parse_clause_type(raw.get("clause_type"))
            clauses.append(
                Clause(
                    id=uuid4(),
                    project_id=project_id,
                    document_id=document_id,
                    clause_code=str(raw.get("clause_code")) if raw.get("clause_code") is not None else "",
                    clause_type=clause_type,
                    title=raw.get("title"),
                    full_text=raw.get("content"),
                    extraction_confidence=raw.get("confidence_score"),
                )
            )
        return clauses


def _parse_clause_type(value: Any) -> ClauseType:
    if isinstance(value, ClauseType):
        return value
    if isinstance(value, str):
        normalized = value.strip().upper()
        for clause_type in ClauseType:
            if clause_type.name == normalized or clause_type.value.upper() == normalized:
                return clause_type
    return ClauseType.OTHER
