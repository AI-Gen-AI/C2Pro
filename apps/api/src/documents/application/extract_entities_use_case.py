"""
Extract Entities Use Case.
Refers to Suite ID: TS-UA-DOC-UC-003.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from src.documents.ports.document_repository import IDocumentRepository
from src.documents.ports.entity_extraction_service import IEntityExtractionService


class ExtractEntitiesUseCase:
    """Refers to Suite ID: TS-UA-DOC-UC-003."""

    def __init__(
        self,
        document_repository: IDocumentRepository,
        entity_extraction_service: IEntityExtractionService,
    ) -> None:
        self.document_repository = document_repository
        self.entity_extraction_service = entity_extraction_service

    async def execute(self, document_id: UUID, parsed_payload: dict[str, Any]) -> dict[str, int]:
        """
        Extracts entities from parsed payload for a document.
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

        summary = await self.entity_extraction_service.extract_entities_from_document(
            document=document,
            parsed_payload=parsed_payload,
            tenant_id=tenant_id,
        )

        return summary
