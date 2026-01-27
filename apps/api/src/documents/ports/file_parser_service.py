"""
File Parser Service Interface (Port).
Defines the contract for parsing various document types.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any

from src.documents.domain.models import Document, DocumentType

class IFileParserService(ABC):
    @abstractmethod
    async def parse_document_file(self, document: Document, file_path: Path) -> Dict[str, Any]:
        """
        Parses a document file based on its type and format.
        :param document: The domain Document entity.
        :param file_path: Path to the downloaded file.
        :return: A dictionary containing the parsed payload (e.g., text blocks, schedule, budget).
        :raises ValueError: If no parser is available for the document type/format.
        """
        pass
