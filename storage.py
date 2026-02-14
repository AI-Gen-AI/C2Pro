"""
C2Pro - Storage Port

Define la interfaz para los servicios de almacenamiento de archivos.
"""
from __future__ import annotations

from typing import Protocol

from fastapi import UploadFile


class IStorageService(Protocol):
    """
    Interfaz para un servicio de almacenamiento de archivos.
    """

    async def save_file(self, file: UploadFile, destination_path: str) -> str:
        """
        Guarda un archivo en el servicio de almacenamiento.
        """
        ...