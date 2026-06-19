"""
Cloudflare R2 implementation of the IStorageService port.

Refers to Suite ID: TS-UAD-PER-R2-001.

Protected by circuit breaker to prevent cascading failures
when R2/S3 storage is unavailable.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, BinaryIO, Protocol
from uuid import UUID

import structlog

from src.config import settings
from src.core.exceptions import StorageError
from src.core.resilience import (
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
)
from src.core.resilience.config import get_circuit_breaker_settings
from src.documents.ports.storage_service import IStorageService

logger = structlog.get_logger()


class _R2Client(Protocol):
    async def put_object(self, **kwargs: Any) -> Any: ...
    async def get_object(self, **kwargs: Any) -> Any: ...
    async def delete_object(self, **kwargs: Any) -> Any: ...


class R2StorageService(IStorageService):
    """
    R2 Storage Service with circuit breaker protection.

    Refers to Suite ID: TS-UAD-PER-R2-001.
    """

    def __init__(self, client: _R2Client) -> None:
        self._client = client
        self._bucket = settings.r2_bucket_name
        self._endpoint = settings.storage_endpoint.rstrip("/")
        self._circuit_breaker = self._init_circuit_breaker()

    def _init_circuit_breaker(self):
        """Initialize circuit breaker for R2 operations."""
        cb_settings = get_circuit_breaker_settings()
        if not cb_settings.enable_circuit_breakers:
            return None

        return CircuitBreakerRegistry.register(
            CircuitBreakerConfig(
                service_name="r2_storage",
                failure_threshold=cb_settings.r2_failure_threshold,
                recovery_timeout=cb_settings.r2_recovery_timeout,
            )
        )

    async def _check_circuit_breaker(self) -> None:
        """Check circuit breaker state before operation."""
        if self._circuit_breaker and not await self._circuit_breaker.can_execute():
            raise StorageError("R2 storage circuit breaker is open")

    async def upload_file(self, file_content: BinaryIO, file_id: UUID, file_extension: str) -> str:
        key = f"{file_id}{file_extension}"
        await self._check_circuit_breaker()

        try:
            body = await self._read_content(file_content)
            await self._client.put_object(Bucket=self._bucket, Key=key, Body=body)
            if self._circuit_breaker:
                await self._circuit_breaker.record_success()
            logger.debug("r2_upload_success", key=key, bucket=self._bucket)
            return f"{self._endpoint}/{self._bucket}/{key}"
        except CircuitBreakerOpenError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            if self._circuit_breaker:
                await self._circuit_breaker.record_failure(exc)
            logger.warning("r2_upload_failed", key=key, error=str(exc))
            raise StorageError(str(exc)) from exc

    async def download_file(self, file_name_in_storage: str) -> Path:
        key = Path(file_name_in_storage).name
        await self._check_circuit_breaker()

        try:
            response = await self._client.get_object(Bucket=self._bucket, Key=key)
            body = response.get("Body")
            content = await self._read_body(body)
            suffix = Path(key).suffix
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(content)
                if self._circuit_breaker:
                    await self._circuit_breaker.record_success()
                logger.debug("r2_download_success", key=key)
                return Path(tmp.name)
        except CircuitBreakerOpenError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            if self._circuit_breaker:
                await self._circuit_breaker.record_failure(exc)
            logger.warning("r2_download_failed", key=key, error=str(exc))
            raise StorageError(str(exc)) from exc

    async def delete_file(self, file_name_in_storage: str) -> None:
        key = Path(file_name_in_storage).name
        await self._check_circuit_breaker()

        try:
            await self._client.delete_object(Bucket=self._bucket, Key=key)
            if self._circuit_breaker:
                await self._circuit_breaker.record_success()
            logger.debug("r2_delete_success", key=key)
        except CircuitBreakerOpenError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            if self._circuit_breaker:
                await self._circuit_breaker.record_failure(exc)
            logger.warning("r2_delete_failed", key=key, error=str(exc))
            raise StorageError(str(exc)) from exc

    async def get_file_path(self, file_name_in_storage: str) -> Path:
        """Return a local temporary path for a remotely stored object."""
        return await self.download_file(file_name_in_storage)

    async def file_exists(self, key: str) -> bool:
        """Check whether a file exists in the R2 bucket by its object key."""
        await self._check_circuit_breaker()
        try:
            await self._client.get_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    async def upload_bytes(self, data: bytes, key: str) -> str:
        """Upload raw bytes to R2 under a content-addressed key."""
        await self._check_circuit_breaker()
        try:
            await self._client.put_object(Bucket=self._bucket, Key=key, Body=data)
            if self._circuit_breaker:
                await self._circuit_breaker.record_success()
            logger.debug("r2_upload_bytes_success", key=key, bucket=self._bucket)
            return f"{self._endpoint}/{self._bucket}/{key}"
        except CircuitBreakerOpenError:
            raise
        except Exception as exc:
            if self._circuit_breaker:
                await self._circuit_breaker.record_failure(exc)
            logger.warning("r2_upload_bytes_failed", key=key, error=str(exc))
            raise StorageError(str(exc)) from exc

    async def _read_content(self, file_content: BinaryIO) -> bytes:
        read_method = file_content.read
        if inspect.iscoroutinefunction(read_method):
            return await read_method()
        return read_method()

    async def _read_body(self, body: Any) -> bytes:
        if body is None:
            return b""
        read_method = getattr(body, "read", None)
        if read_method is None:
            return bytes(body)
        if inspect.iscoroutinefunction(read_method):
            return await read_method()
        return read_method()
