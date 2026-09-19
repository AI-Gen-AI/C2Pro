"""
Local file-system storage adapter for documents.

Implements ``IStorageService`` by writing files to a configurable
directory on the local filesystem (defaults to ``./uploads``).
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

import structlog

from src.core.exceptions import StorageError
from src.documents.domain.storage_keys import is_document_object_prefix
from src.documents.ports.storage_service import IStorageService

logger = structlog.get_logger()

# Use /app/uploads for Docker compatibility with shared volumes
_DEFAULT_UPLOAD_DIR = Path("/app/uploads")
_FALLBACK_UPLOAD_DIR = Path(tempfile.gettempdir()) / "c2pro-uploads"


class LocalFileStorageService(IStorageService):
    """Stores files on the local filesystem."""

    def __init__(self, base_dir: Path | None = None) -> None:
        preferred_dir = base_dir or _DEFAULT_UPLOAD_DIR
        self._base_dir = self._ensure_writable_directory(preferred_dir)

    @staticmethod
    def _ensure_writable_directory(preferred_dir: Path) -> Path:
        try:
            preferred_dir.mkdir(parents=True, exist_ok=True)
            # mkdir succeeding does not guarantee that the process can create
            # files there (for example, a read-only mounted Docker volume).
            with tempfile.NamedTemporaryFile(dir=preferred_dir):
                pass
            return preferred_dir
        except OSError:
            _FALLBACK_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            logger.warning(
                "local_storage_fallback_dir",
                preferred=str(preferred_dir),
                fallback=str(_FALLBACK_UPLOAD_DIR),
            )
            return _FALLBACK_UPLOAD_DIR

    async def upload_file(self, file_content: BinaryIO, file_id: UUID, file_extension: str) -> str:
        dest = self._base_dir / f"{file_id}{file_extension}"
        with open(dest, "wb") as f:
            shutil.copyfileobj(file_content, f)
        logger.info("file_uploaded", path=str(dest))
        return str(dest)

    async def download_file(self, file_name_in_storage: str) -> Path:
        path = Path(file_name_in_storage)
        if not path.exists():
            path = self._base_dir / file_name_in_storage
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_name_in_storage}")
        return path

    async def delete_file(self, file_name_in_storage: str) -> None:
        path = Path(file_name_in_storage)
        if not path.exists():
            path = self._base_dir / file_name_in_storage
        if path.exists():
            path.unlink()
            logger.info("file_deleted", path=str(path))

    async def get_file_path(self, file_name_in_storage: str) -> Path:
        path = Path(file_name_in_storage)
        if path.exists():
            return path
        return self._base_dir / file_name_in_storage

    def _resolve_key(self, key: str) -> Path:
        """Map an object key to a path inside the store; refuse keys that escape it."""
        if not key or key.startswith(("/", "\\")) or Path(key).is_absolute():
            raise StorageError("Invalid storage key")
        base = self._base_dir.resolve()
        resolved = (base / key).resolve()
        if resolved == base or base not in resolved.parents:
            raise StorageError("Invalid storage key")
        return self._base_dir / key

    async def file_exists(self, key: str) -> bool:
        return self._resolve_key(key).exists()

    async def upload_bytes(self, data: bytes, key: str) -> str:
        dest = self._resolve_key(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        logger.info("bytes_uploaded", path=str(dest))
        return str(dest)

    async def download_object(self, key: str) -> Path:
        path = self._resolve_key(key)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {key}")
        return path

    async def delete_prefix(self, prefix: str) -> None:
        if not is_document_object_prefix(prefix):
            raise StorageError("delete_prefix requires a single document prefix")
        path = self._resolve_key(prefix)
        if path.is_dir():
            shutil.rmtree(path)
            logger.info("document_objects_deleted", prefix=prefix)
