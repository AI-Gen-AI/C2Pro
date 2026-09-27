"""Canonical document storage provider factory.

Production upload and Celery ingestion must resolve the same durable object store.
Local filesystem storage remains available for local/test use only.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from src.config import settings
from src.core.exceptions import StorageError
from src.documents.adapters.storage.local_file_storage_service import LocalFileStorageService
from src.documents.adapters.storage.r2_storage_service import R2StorageService
from src.documents.ports.storage_service import IStorageService


class _AsyncBytesBody:
    """Async body facade so R2 downloads never block the event loop."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    async def read(self) -> bytes:
        return self._data


class _AsyncBoto3S3Client:
    """Async facade over the already-pinned synchronous boto3 S3 client."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def put_object(self, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._client.put_object, **kwargs)

    async def get_object(self, **kwargs: Any) -> Any:
        response = await asyncio.to_thread(self._client.get_object, **kwargs)
        body = response.get("Body") if isinstance(response, dict) else None
        read = getattr(body, "read", None)
        if callable(read):
            data = await asyncio.to_thread(read)
            response = dict(response)
            response["Body"] = _AsyncBytesBody(bytes(data))
        return response

    async def delete_object(self, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._client.delete_object, **kwargs)

    async def list_objects_v2(self, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._client.list_objects_v2, **kwargs)

    async def delete_objects(self, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._client.delete_objects, **kwargs)


def _build_r2_client(config: Any) -> _AsyncBoto3S3Client:
    endpoint = config.storage_endpoint
    required = {
        "R2 endpoint": endpoint,
        "R2 access key id": config.r2_access_key_id,
        "R2 secret access key": config.r2_secret_access_key,
        "R2 bucket name": config.r2_bucket_name,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        # Never include values: credentials/config belong outside logs and errors.
        raise StorageError("R2 storage configuration incomplete")

    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=config.r2_access_key_id,
        aws_secret_access_key=config.r2_secret_access_key,
    )
    return _AsyncBoto3S3Client(client)


def build_storage_service(config: Any = settings) -> IStorageService:
    """Resolve the configured storage provider without silent fallback."""

    provider = str(config.storage_provider).lower()
    if provider == "local":
        return LocalFileStorageService(base_dir=Path(config.local_storage_path))
    if provider == "r2":
        return R2StorageService(client=_build_r2_client(config))
    if provider == "s3":
        raise StorageError("S3 storage provider is not configured")
    raise StorageError("Unsupported storage provider")
