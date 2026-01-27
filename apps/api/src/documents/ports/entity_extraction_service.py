"""
Entity Extraction Service Interface (Port).
Defines the contract for extracting domain entities from parsed document content.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from uuid import UUID

from src.documents.domain.models import Document

class IEntityExtractionService(ABC):
    @abstractmethod
    async def extract_entities_from_document(
        self, document: Document, parsed_payload: Dict[str, Any], tenant_id: UUID
    ) -> Dict[str, int]:
        """
        Extracts various entities (stakeholders, WBS, BOM) from parsed document content.
        :param document: The domain Document entity.
        :param parsed_payload: The content parsed by the file parser.
        :param tenant_id: The ID of the current tenant.
        :return: A summary of extracted entities (e.g., count of stakeholders).
        """
        pass
