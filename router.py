"""
C2Pro - API Router for Document Ingestion

Suite ID: [TEST-BE-01], [TEST-BE-04], [TEST-BE-05]
"""
import uuid
from pathlib import Path
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from src.config import settings
from src.documents.adapters.storage.local_file_storage_service import (
    LocalFileStorageService,
)
from src.documents.adapters.storage.r2_storage_service import R2StorageService
from src.documents.application.ports.storage import IStorageService
from src.documents.application.upload_document_use_case import UploadDocumentUseCase

logger = structlog.get_logger()

router = APIRouter(prefix="/documents", tags=["documents"])


# --- Dependency Factories ---


def get_storage_service() -> IStorageService:
    """Factory para obtener el servicio de almacenamiento según la configuración."""
    if settings.STORAGE_PROVIDER == "r2":
        return R2StorageService()
    return LocalFileStorageService()


def get_upload_use_case(
    storage_service: IStorageService = Depends(get_storage_service),
) -> UploadDocumentUseCase:
    return UploadDocumentUseCase(storage_service=storage_service)


@router.post("/upload", status_code=202)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    project_id: UUID = Form(...),
    upload_use_case: UploadDocumentUseCase = Depends(get_upload_use_case),
):
    """
    Sube un nuevo documento de contrato para su análisis asíncrono.

    Valida el tipo y tamaño del archivo antes de aceptarlo para procesamiento.
    """
    # 1. Validar tamaño del archivo (TEST-BE-05)
    # Usamos el header Content-Length para una validación temprana y eficiente.
    content_length = request.headers.get("content-length")
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if content_length and int(content_length) > max_size:
        logger.warning(
            "file_upload_too_large",
            filename=file.filename,
            size_bytes=content_length,
            limit_mb=settings.MAX_UPLOAD_SIZE_MB,
        )
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds the limit of {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )

    # 2. Validar tipo de archivo (TEST-BE-04)
    file_extension = Path(file.filename).suffix.lower()
    allowed_types = settings.ALLOWED_DOCUMENT_TYPES.split(",")
    if file_extension not in allowed_types:
        logger.warning(
            "file_upload_invalid_type",
            filename=file.filename,
            extension=file_extension,
            allowed=allowed_types,
        )
        raise HTTPException(
            status_code=422,
            detail=f"Invalid file type. Allowed types are: {', '.join(allowed_types)}",
        )

    # 3. Ejecutar caso de uso para guardar el archivo
    result = await upload_use_case.execute(file=file, project_id=project_id)
    document_id = result["document_id"]

    # TODO: Poner en cola la tarea asíncrona (Celery, etc.) para procesar el archivo.
    logger.info(
        "document_accepted_for_processing", document_id=str(document_id), project_id=str(project_id)
    )

    status_url = f"/api/v1/documents/{document_id}/status"
    return JSONResponse(
        status_code=202,
        content={"document_id": str(document_id), "status_url": status_url},
    )