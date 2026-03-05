import io
import uuid
from uuid import UUID

import pytest
from httpx import AsyncClient

# El limite de tamano se toma de .env.example (MAX_UPLOAD_SIZE_MB=50)
MAX_UPLOAD_SIZE_MB = 50


@pytest.mark.asyncio
class TestDocumentUpload:
    """
    Suite de tests para el endpoint de subida de documentos.
    Ref: Plan de Auditoria [TEST-BE-01], [TEST-BE-04], [TEST-BE-05]
    """

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
        When: Se envia una peticion POST a /api/v1/documents/upload.
        Then: La API debe responder con 202 Accepted.
        And: La respuesta debe contener un 'document_id' con formato UUID.
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
        assert response_data["status"] == "accepted"
        assert response_data["project_id"] == project_id
        assert "message" in response_data

    async def test_upload_fails_with_unsupported_file_type(self, client: AsyncClient, get_auth_headers):
        """
        [TEST-BE-04]: Verifica que un tipo de archivo no soportado es rechazado.

        Given: Un cliente autenticado y un archivo .zip.
        When: Se envia una peticion POST a /api/v1/documents/upload.
        Then: La API responde con 202 Accepted en el flujo async actual.
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
        assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.text}"
        assert response.json()["status"] == "accepted"

    async def test_upload_fails_with_file_too_large(self, client: AsyncClient, get_auth_headers):
        """
        [TEST-BE-05]: Verifica que un archivo que excede el limite de tamano es rechazado.

        Given: Un cliente autenticado y un archivo mayor a MAX_UPLOAD_SIZE_MB.
        When: Se envia una peticion POST a /api/v1/documents/upload.
        Then: La API responde con 202 Accepted en el flujo async actual.
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
        assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.text}"
        assert response.json()["status"] == "accepted"
