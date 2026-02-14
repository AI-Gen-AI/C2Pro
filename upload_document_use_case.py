"""
C2Pro - Upload Document Use Case
"""
from __future__ import annotations

import uuid
from pathlib import Path
from uuid import UUID

import structlog
from fastapi import UploadFile

from src.documents.application.ports.storage import IStorageService

logger = structlog.get_logger()


class UploadDocumentUseCase:
    """
    Caso de uso para subir un documento, guardarlo en el almacenamiento
    y registrarlo en la base de datos.
    """

    def __init__(self, storage_service: IStorageService):
        # TODO: Inyectar un DocumentRepository port
        self.storage_service = storage_service

    async def execute(self, file: UploadFile, project_id: UUID) -> dict:
        """
        Ejecuta el caso de uso.
        """
        document_id = uuid.uuid4()
        file_extension = Path(file.filename).suffix.lower()
        # Estructura de ruta: tenant_id/project_id/document_id.extension
        # TODO: Obtener tenant_id del contexto de seguridad
        destination_path = f"tenant-placeholder/{project_id}/{document_id}{file_extension}"

        storage_path = await self.storage_service.save_file(
            file=file, destination_path=destination_path
        )

        # TODO: Guardar la entidad Document en la base de datos usando el repositorio.
        logger.info("document_entity_creation_placeholder", document_id=str(document_id))

        return {"document_id": document_id, "storage_path": storage_path}