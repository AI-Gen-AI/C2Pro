"""
RAG Ingestion Service Interface (Port).
Defines the contract for ingesting document chunks into a RAG system.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from uuid import UUID

from src.documents.domain.models import Document

class IRagIngestionService(ABC):
    @abstractmethod
    async def ingest_document_chunks(
        self, document: Document, parsed_payload: Dict[str, Any], tenant_id: UUID
    ) -> None:
        """
        Ingests parsed document content into the RAG system.
        :param document: The domain Document entity.
        :param parsed_payload: The content parsed by the file parser.
        :param tenant_id: The ID of the current tenant.
        """
        pass
