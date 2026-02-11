"""
C2Pro - Ingestion Domain Layer

Pure business entities and exceptions for document ingestion.
No framework dependencies, only Pydantic for data validation.
"""

from src.modules.ingestion.domain.entities import (
    IngestionChunk,
    IngestionError,
    TableData,
)

__all__ = ["IngestionChunk", "IngestionError", "TableData"]
