from abc import ABC, abstractmethod
from typing import BinaryIO
from pathlib import Path

class StorageServicePort(ABC):
    @abstractmethod
    async def upload_file(self, file_content: BinaryIO, file_id: UUID, file_extension: str) -> str:
        pass

    @abstractmethod
    async def download_file(self, file_name_in_storage: str) -> Path:
        pass

    @abstractmethod
    async def delete_file(self, file_name_in_storage: str):
        pass
