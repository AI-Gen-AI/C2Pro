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

    @abstractmethod
    async def get_file_path(self, file_name_in_storage: str) -> Path:
        """
        Gets the full path to a file in storage.
        :param file_name_in_storage: The name/path of the file in storage.
        :return: Full Path to the file.
        """
        pass

    @abstractmethod
    async def file_exists(self, key: str) -> bool:
        """Check whether a file exists in storage by its object key.
        :param key: The object key in the bucket.
        :return: True if the object exists, False otherwise.
        """
        pass

    @abstractmethod
    async def upload_bytes(self, data: bytes, key: str) -> str:
        """Upload raw bytes to storage under a string key (content-addressed).
        :param data: Raw bytes to upload.
        :param key: Object key in the bucket.
        :return: URL or path to the stored object.
        """
        pass

    async def download_object(self, key: str) -> Path:
        """Download an object by its exact immutable key (P0b revision objects).

        Unlike ``download_file``, which some adapters reduce to a basename for legacy
        storage URLs, the key is never rewritten, so a revision can never be redirected
        to another object.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support exact-key downloads")

    async def delete_prefix(self, prefix: str) -> None:
        """Delete every object of one document (``tenants/{t}/projects/{p}/documents/{d}/``)."""
        raise NotImplementedError(f"{type(self).__name__} does not support prefix deletes")
