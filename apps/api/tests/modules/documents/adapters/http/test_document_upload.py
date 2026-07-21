import io
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from src.documents.adapters.http.router import get_storage_service
from src.documents.adapters.storage.local_file_storage_service import (
    LocalFileStorageService,
)

# El limite de tamano se toma de .env.example (MAX_UPLOAD_SIZE_MB=50)
MAX_UPLOAD_SIZE_MB = 50


@pytest.mark.requires_services
@pytest.mark.asyncio
class TestDocumentUpload:
    """
    Suite de tests para el endpoint de subida de documentos.
    Ref: Plan de Auditoria [TEST-BE-01], [TEST-BE-04], [TEST-BE-05]
    """

    @pytest.fixture(autouse=True)
    def _override_storage(self, app, tmp_path: Path):
        app.dependency_overrides[get_storage_service] = lambda: LocalFileStorageService(
            base_dir=tmp_path / "uploads"
        )
        yield
        app.dependency_overrides.pop(get_storage_service, None)

    async def _create_project(self, client: AsyncClient, headers: dict[str, str]) -> str:
        response = await client.post(
            "/api/v1/projects",
            json={"name": f"Upload Project {uuid.uuid4().hex[:8]}", "project_type": "construction"},
            headers=headers,
        )
        assert response.status_code == 201, f"Project creation failed: {response.status_code}: {response.text}"
        return response.json()["id"]

    async def test_upload_successful_with_valid_pdf(self, client: AsyncClient, get_auth_headers):
        """
        [TEST-BE-01]: Verifica que un archivo PDF valido se acepta para procesamiento.

        Given: Un cliente autenticado y un archivo PDF valido.
        When: Se envia una peticion POST a /api/v1/projects/{project_id}/documents.
        Then: La API debe responder con 202 Accepted.
        And: La respuesta debe contener el documento encolado para procesamiento asincrono.
        """
        # Arrange
        # Crear un archivo PDF falso en memoria
        fake_pdf_content = b"%PDF-1.5\n%fake content"
        files = {"file": ("contract.pdf", io.BytesIO(fake_pdf_content), "application/pdf")}
        data = {"document_type": "contract"}
        headers = get_auth_headers()
        project_id = await self._create_project(client, headers)

        # Act
        response = await client.post(
            f"/api/v1/projects/{project_id}/documents",
            files=files,
            data=data,
            headers=headers,
        )

        # Assert
        assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.text}"
        response_data = response.json()
        assert response_data["id"]
        assert response_data["project_id"] == project_id
        assert response_data["processing_status"] == "queued"
        assert "status_detail" in response_data
        assert "task_id" in response_data

    async def test_upload_fails_with_unsupported_file_type(self, client: AsyncClient, get_auth_headers):
        """
        [TEST-BE-04]: Verifica que un tipo de archivo no soportado es rechazado.

        Given: Un cliente autenticado y un archivo .zip.
        When: Se envia una peticion POST a /api/v1/projects/{project_id}/documents.
        Then: La API responde con 400 Bad Request.
        """
        # Arrange
        fake_zip_content = b"PK\x03\x04..."
        files = {"file": ("archive.zip", io.BytesIO(fake_zip_content), "application/zip")}
        data = {"document_type": "contract"}
        headers = get_auth_headers()
        project_id = await self._create_project(client, headers)

        # Act
        response = await client.post(
            f"/api/v1/projects/{project_id}/documents",
            files=files,
            data=data,
            headers=headers,
        )

        # Assert
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        assert response.json()["detail"] == "File type '.zip' is not allowed."

    async def test_upload_fails_with_file_too_large(self, client: AsyncClient, get_auth_headers):
        """
        [TEST-BE-05]: Verifica que un archivo que excede el limite de tamano es rechazado.

        Given: Un cliente autenticado y un archivo mayor a MAX_UPLOAD_SIZE_MB.
        When: Se envia una peticion POST a /api/v1/projects/{project_id}/documents.
        Then: La API responde con 413 Request Entity Too Large.
        """
        # Arrange
        # Crear un archivo falso de 51MB (limite es 50MB)
        large_content = b"a" * ((MAX_UPLOAD_SIZE_MB + 1) * 1024 * 1024)
        files = {"file": ("large_file.pdf", io.BytesIO(large_content), "application/pdf")}
        data = {"document_type": "contract"}
        headers = get_auth_headers()
        project_id = await self._create_project(client, headers)

        # Act
        response = await client.post(
            f"/api/v1/projects/{project_id}/documents",
            files=files,
            data=data,
            headers=headers,
        )

        # Assert
        assert response.status_code == 413, f"Expected 413, got {response.status_code}: {response.text}"
        assert response.json()["detail"] == "File size exceeds limit of 50MB."
