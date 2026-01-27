"""
Storage Service Interface (Port).
Defines the contract for interacting with file storage.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

class IStorageService(ABC):
    @abstractmethod
    async def upload_file(self, file_content: BinaryIO, file_id: UUID, file_extension: str) -> str:
        """
        Uploads a file to storage.
        :param file_content: Binary content of the file.
        :param file_id: Unique ID to use for the file in storage.
        :param file_extension: Original file extension (e.g., '.pdf').
        :return: The URL or path to the stored file.
        """
        pass

    @abstractmethod
    async def download_file(self, file_name_in_storage: str) -> Path:
        """
        Downloads a file from storage.
        :param file_name_in_storage: The name/path of the file in storage.
        :return: Path to the downloaded temporary file.
        """
        pass

    @abstractmethod
    async def delete_file(self, file_name_in_storage: str) -> None:
        """
        Deletes a file from storage.
        :param file_name_in_storage: The name/path of the file in storage.
        """
        pass
