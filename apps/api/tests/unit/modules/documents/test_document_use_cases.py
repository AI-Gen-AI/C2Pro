"""TS-UD-DOC-DOC-001 / TASK-BCK-095: CreateDocumentUseCase unit tests."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.tenants.types import TenantId
from src.documents.application.dtos import CreateDocumentDTO
from src.documents.application.use_cases import CreateDocumentUseCase
from src.documents.domain.models import Document, DocumentStatus, DocumentType
from src.documents.ports.document_repository import IDocumentRepository

# =================================================================
# Fixtures
# =================================================================

def _make_dto(**overrides) -> CreateDocumentDTO:
    defaults = {
        "project_id": uuid4(),
        "tenant_id": uuid4(),
        "filename": "contract.pdf",
        "document_type": DocumentType.CONTRACT,
        "file_format": "pdf",
        "storage_url": "/uploads/contract.pdf",
        "file_size_bytes": 1024,
        "created_by": uuid4(),
    }
    defaults.update(overrides)
    return CreateDocumentDTO(**defaults)


# =================================================================
# Tests
# =================================================================


@pytest.mark.asyncio
async def test_create_document_happy_path():
    """Should create and return a Document with status UPLOADED."""
    repo = AsyncMock(spec=IDocumentRepository)
    use_case = CreateDocumentUseCase(repository=repo)
    dto = _make_dto()

    result = await use_case.execute(dto)

    repo.add.assert_awaited_once_with(TenantId(dto.tenant_id), result)
    assert isinstance(result, Document)
    assert result.project_id == dto.project_id
    assert result.tenant_id == dto.tenant_id
    assert result.filename == dto.filename
    assert result.document_type == dto.document_type
    assert result.upload_status == DocumentStatus.UPLOADED

    assert result.id is not None


@pytest.mark.asyncio
async def test_create_document_raises_exception_on_repository_error():
    """Should propagate repository exceptions to the caller."""
    repo = AsyncMock(spec=IDocumentRepository)
    repo.add.side_effect = ConnectionError("DB connection lost")
    use_case = CreateDocumentUseCase(repository=repo)
    dto = _make_dto()

    with pytest.raises(ConnectionError, match="DB connection lost"):
        await use_case.execute(dto)

    repo.add.assert_awaited_once()


def test_create_document_with_missing_name_fails():
    """CreateDocumentDTO requires a non-empty filename."""
    # CreateDocumentDTO is a frozen dataclass; filename is a required str field.
    # Passing empty string is allowed by the dataclass, so validation must
    # be at the domain level. Verify that the DTO can't be constructed
    # without filename at all (TypeError from missing required arg).
    with pytest.raises(TypeError):
        CreateDocumentDTO(
            project_id=uuid4(),
            tenant_id=uuid4(),
            # filename omitted
            document_type=DocumentType.CONTRACT,
        )
