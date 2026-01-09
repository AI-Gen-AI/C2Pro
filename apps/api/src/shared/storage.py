import inspect
from pathlib import Path
from typing import IO
from uuid import UUID

import aiofiles

from src.config import settings


class StorageService:
    def __init__(self):
        # Configure a base directory for local storage
        # In a real application, this would be Cloudflare R2, S3, etc.
        self.base_storage_path = Path(settings.local_storage_path)  # Use configurable path

        # Ensure the base storage path exists
        self.base_storage_path.mkdir(parents=True, exist_ok=True)

    async def upload_file(self, file_content: IO, file_id: UUID, file_extension: str) -> str:
        """
        Uploads a file to local storage.
        In a production environment, this would upload to Cloudflare R2 or similar.
        """
        file_name = f"{file_id}{file_extension}"
        file_path = self.base_storage_path / file_name

        async with aiofiles.open(file_path, "wb") as out_file:
            # Read content in chunks to handle large files (supports sync or async file objects)
            read_method = file_content.read
            if inspect.iscoroutinefunction(read_method):
                while content := await read_method(65536):
                    await out_file.write(content)
            else:
                while content := read_method(65536):
                    await out_file.write(content)

        # Return a "storage URL" for the local file (e.g., /local-storage/{file_id}.ext)
        return f"/local-storage/{file_name}"

    async def download_file(self, file_name: str) -> Path:
        """
        Downloads a file from local storage.
        In a production environment, this would download from Cloudflare R2 or similar.
        """
        file_path = self.base_storage_path / file_name
        if not file_path.exists():
            raise FileNotFoundError(f"File {file_name} not found in storage.")
        return file_path

    async def delete_file(self, file_name: str) -> None:
        """
        Deletes a file from local storage.
        In a production environment, this would delete from Cloudflare R2 or similar.
        """
        file_path = self.base_storage_path / file_name
        if file_path.exists():
            file_path.unlink()
