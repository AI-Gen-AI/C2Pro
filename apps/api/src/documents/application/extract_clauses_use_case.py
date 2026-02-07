"""
Extract Clauses Use Case.
Refers to Suite ID: TS-UA-DOC-UC-002.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from src.documents.domain.models import Clause
from src.documents.ports.clause_extraction_service import IClauseExtractionService
from src.documents.ports.document_repository import IDocumentRepository


class ExtractClausesUseCase:
    """Refers to Suite ID: TS-UA-DOC-UC-002."""

    def __init__(
        self,
        document_repository: IDocumentRepository,
        clause_extraction_service: IClauseExtractionService,
    ) -> None:
        self.document_repository = document_repository
        self.clause_extraction_service = clause_extraction_service

    async def execute(self, document_id: UUID, text: str) -> list[Clause]:
        """
        Extracts clauses from text and persists them for a document.
        """
        document = await self.document_repository.get_by_id(document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )

        tenant_id = await self.document_repository.get_project_tenant_id(document.project_id)
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project for document not found.",
            )

        clauses = await self.clause_extraction_service.extract_from_text(
            text=text,
            document_id=document_id,
            project_id=document.project_id,
            tenant_id=tenant_id,
        )

        if not clauses:
            return []

        for clause in clauses:
            await self.document_repository.add_clause(clause)

        await self.document_repository.commit()
        return clauses
