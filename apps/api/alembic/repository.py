"""
C2Pro - Document Repository Port

Define la interfaz para el repositorio de persistencia de documentos.
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.documents.domain.models import Document


class IDocumentRepository(Protocol):
    """
    Interfaz para un repositorio de documentos.
    """

    async def add(self, document: Document) -> None:
        """Añade un nuevo documento a la persistencia."""
        ...