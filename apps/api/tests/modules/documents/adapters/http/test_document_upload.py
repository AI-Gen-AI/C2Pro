import io
import uuid
from uuid import UUID

import pytest
from httpx import AsyncClient

# El limite de tamano se toma de .env.example (MAX_UPLOAD_SIZE_MB=50)
MAX_UPLOAD_SIZE_MB = 50
VALID_PROJECT_ID = str(uuid.uuid4())


@pytest.mark.asyncio
class TestDocumentUpload:
    """
    Suite de tests para el endpoint de subida de documentos.
    Ref: Plan de Auditoria [TEST-BE-01], [TEST-BE-04], [TEST-BE-05]
    """

    async def test_upload_successful_with_valid_pdf(self, client: AsyncClient):
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
        data = {"project_id": VALID_PROJECT_ID}

        # Act
        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        # Assert
        assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.text}"
        response_data = response.json()
        assert "document_id" in response_data
        assert "status_url" in response_data

        # Verificar que el document_id es un UUID valido
        try:
            doc_id = UUID(response_data["document_id"])
            assert str(doc_id) == response_data["document_id"]
        except (ValueError, TypeError):
            pytest.fail(f"'{response_data['document_id']}' no es un UUID valido.")

        assert response_data["status_url"] == f"/api/v1/documents/{doc_id}/status"

    async def test_upload_fails_with_unsupported_file_type(self, client: AsyncClient):
        """
        [TEST-BE-04]: Verifica que un tipo de archivo no soportado es rechazado.

        Given: Un cliente autenticado y un archivo .zip.
        When: Se envia una peticion POST a /api/v1/documents/upload.
        Then: La API debe responder con 422 Unprocessable Entity.
        """
        # Arrange
        fake_zip_content = b"PK\x03\x04..."
        files = {"file": ("archive.zip", io.BytesIO(fake_zip_content), "application/zip")}
        data = {"project_id": VALID_PROJECT_ID}

        # Act
        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        # Assert
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"

    async def test_upload_fails_with_file_too_large(self, client: AsyncClient):
        """
        [TEST-BE-05]: Verifica que un archivo que excede el limite de tamano es rechazado.

        Given: Un cliente autenticado y un archivo mayor a MAX_UPLOAD_SIZE_MB.
        When: Se envia una peticion POST a /api/v1/documents/upload.
        Then: La API debe responder con 413 Payload Too Large.
        """
        # Arrange
        # Crear un archivo falso de 51MB (limite es 50MB)
        large_content = b"a" * ((MAX_UPLOAD_SIZE_MB + 1) * 1024 * 1024)
        files = {"file": ("large_file.pdf", io.BytesIO(large_content), "application/pdf")}
        data = {"project_id": VALID_PROJECT_ID}

        # Act
        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        # Assert
        assert response.status_code == 413, f"Expected 413, got {response.status_code}: {response.text}"
