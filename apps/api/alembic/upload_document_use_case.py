"""
C2Pro - Upload Document Use Case
"""
from __future__ import annotations

import uuid
from pathlib import Path
from uuid import UUID

import structlog
from fastapi import UploadFile

from src.documents.application.ports.repository import IDocumentRepository
from src.documents.application.ports.storage import IStorageService
from src.documents.domain.models import Document, DocumentStatus, DocumentType

logger = structlog.get_logger()


class UploadDocumentUseCase:
    """
    Caso de uso para subir un documento, guardarlo en el almacenamiento
    y registrarlo en la base de datos.
    """

    def __init__(
        self,
        storage_service: IStorageService,
        document_repository: IDocumentRepository,
    ):
        self.storage_service = storage_service
        self.document_repository = document_repository

    async def execute(
        self, file: UploadFile, project_id: UUID, tenant_id: UUID
    ) -> Document:
        """
        Ejecuta el caso de uso.
        """
        document_id = uuid.uuid4()
        file_extension = Path(file.filename).suffix.lower()

        # Estructura de ruta: tenant_id/project_id/document_id.extension
        destination_path = f"{tenant_id}/{project_id}/{document_id}{file_extension}"

        # 1. Guardar el archivo en el almacenamiento
        storage_path = await self.storage_service.save_file(
            file=file, destination_path=destination_path
        )

        # 2. Crear la entidad de dominio Document
        # Mover el cursor al final para obtener el tamaño del archivo
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)  # Resetear el cursor

        document_entity = Document(
            id=document_id,
            project_id=project_id,
            tenant_id=tenant_id,
            filename=file.filename,
            storage_path=storage_path,
            document_type=DocumentType.OTHER,  # TODO: Obtener de la request
            status=DocumentStatus.UPLOADED,
            file_size_bytes=file_size,
        )

        # 3. Persistir la entidad en la base de datos
        await self.document_repository.add(document_entity)

        logger.info("document_persisted", document_id=str(document_id))

        return document_entity