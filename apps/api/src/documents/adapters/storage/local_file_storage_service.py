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
        """
        Gets the full path to a file in storage.

        Args:
            file_name_in_storage: The name/path of the file in storage.

        Returns:
            Full Path to the file.
        """
        path = Path(file_name_in_storage)
        if path.exists():
            return path
        return self._base_dir / file_name_in_storage
