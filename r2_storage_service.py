"""
C2Pro - R2 Storage Service Adapter

Implementación del servicio de almacenamiento compatible con Cloudflare R2 y MinIO.
"""
from __future__ import annotations

import aioboto3
import structlog
from botocore.client import Config
from fastapi import UploadFile

from src.config import settings
from src.core.exceptions import StorageError

logger = structlog.get_logger()


class R2StorageService:
    """
    Servicio para interactuar con un bucket compatible con S3 (R2/MinIO).
    """

    def __init__(self):
        session = aioboto3.Session()
        self.client = session.client(
            "s3",
            endpoint_url=settings.R2_ENDPOINT_URL,  # Es None para R2, http://... para MinIO
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
        self.bucket_name = settings.R2_BUCKET_NAME
        logger.info(
            "r2_storage_service_initialized",
            bucket=self.bucket_name,
            endpoint=settings.R2_ENDPOINT_URL or "Cloudflare R2",
        )

    async def save_file(self, file: UploadFile, destination_path: str) -> str:
        """
        Sube un archivo al bucket de R2/MinIO.

        Args:
            file: El archivo a subir.
            destination_path: La ruta (key) donde se guardará en el bucket.

        Returns:
            La URL pública o identificador del archivo guardado.
        """
        try:
            await self.client.upload_fileobj(
                file.file,
                self.bucket_name,
                destination_path,
                ExtraArgs={"ContentType": file.content_type},
            )
            logger.info("file_uploaded_to_r2", filename=file.filename, path=destination_path)
            # En un caso real, devolveríamos la URL pública. Por ahora, la ruta es suficiente.
            return destination_path
        except Exception as e:
            logger.error("r2_upload_failed", error=str(e), exc_info=True)
            raise StorageError(f"Failed to upload file to R2/MinIO: {e}") from e