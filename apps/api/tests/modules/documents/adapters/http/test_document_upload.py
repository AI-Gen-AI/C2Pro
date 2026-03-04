import io
import uuid
from uuid import UUID

import pytest
from httpx import AsyncClient

from src.projects.adapters.persistence.models import ProjectORM

# El limite de tamano se toma de .env.example (MAX_UPLOAD_SIZE_MB=50)
MAX_UPLOAD_SIZE_MB = 50
VALID_PROJECT_ID = str(uuid.uuid4())


@pytest.fixture
async def project_id(db, test_tenant):
    project = ProjectORM(
        tenant_id=test_tenant.id,
        name="Upload Test Project",
        project_type="construction",
        status="draft",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return str(project.id)


@pytest.mark.asyncio
class TestDocumentUpload:
    """
    Suite de tests para el endpoint de subida de documentos.
    Ref: Plan de Auditoria [TEST-BE-01], [TEST-BE-04], [TEST-BE-05]
    """

    async def test_upload_successful_with_valid_pdf(self, client: AsyncClient, get_auth_headers, project_id):
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

        # Act
        response = await client.post(
            f"/api/v1/projects/{project_id}/documents",
            files=files,
            data=data,
            headers=get_auth_headers(),
        )

        # Assert
        assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.text}"
        response_data = response.json()
        assert "id" in response_data
        assert "task_id" in response_data

        # Verificar que el document_id es un UUID valido
        try:
            doc_id = UUID(response_data["id"])
            assert str(doc_id) == response_data["id"]
        except (ValueError, TypeError):
            pytest.fail(f"'{response_data['id']}' no es un UUID valido.")

    async def test_upload_fails_with_unsupported_file_type(self, client: AsyncClient, get_auth_headers):
        """
        [TEST-BE-04]: Verifica que un tipo de archivo no soportado es rechazado.

        Given: Un cliente autenticado y un archivo .zip.
        When: Se envia una peticion POST a /api/v1/documents/upload.
        Then: La API debe responder con 422 Unprocessable Entity.
        """
        # Arrange
        fake_zip_content = b"PK\x03\x04..."
        files = {"file": ("archive.zip", io.BytesIO(fake_zip_content), "application/zip")}
        data = {"document_type": "contract"}

        # Act
        response = await client.post(
            f"/api/v1/projects/{VALID_PROJECT_ID}/documents",
            files=files,
            data=data,
            headers=get_auth_headers(),
        )

        # Assert
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"

    async def test_upload_fails_with_file_too_large(self, client: AsyncClient, get_auth_headers):
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
        data = {"document_type": "contract"}

        # Act
        response = await client.post(
            f"/api/v1/projects/{VALID_PROJECT_ID}/documents",
            files=files,
            data=data,
            headers=get_auth_headers(),
        )

        # Assert
        assert response.status_code == 413, f"Expected 413, got {response.status_code}: {response.text}"
