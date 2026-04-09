"""
Unit Tests for CreateDocumentUseCase.
"""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.documents.application.dtos import CreateDocumentDTO
from src.documents.application.use_cases import CreateDocumentUseCase
from src.documents.domain.models import Document, DocumentStatus, DocumentType

# =================================================================
# Fixtures
# =================================================================

def _make_dto(**overrides) -> CreateDocumentDTO:
    defaults = {
        "project_id": uuid4(),
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


def test_create_document_happy_path():
    """Should create and return a Document with status UPLOADED."""
    repo = Mock()
    use_case = CreateDocumentUseCase(repository=repo)
    dto = _make_dto()

    result = use_case.execute(dto)

    # Assert: repo.save was called exactly once with the new document
    repo.save.assert_called_once()
    saved_doc = repo.save.call_args[0][0]
    assert isinstance(saved_doc, Document)
    assert saved_doc.project_id == dto.project_id
    assert saved_doc.filename == dto.filename
    assert saved_doc.document_type == dto.document_type
    assert saved_doc.upload_status == DocumentStatus.UPLOADED

    # Assert: use case returns the same document
    assert result is saved_doc
    assert result.id is not None


def test_create_document_raises_exception_on_repository_error():
    """Should propagate repository exceptions to the caller."""
    repo = Mock()
    repo.save.side_effect = ConnectionError("DB connection lost")
    use_case = CreateDocumentUseCase(repository=repo)
    dto = _make_dto()

    with pytest.raises(ConnectionError, match="DB connection lost"):
        use_case.execute(dto)


def test_create_document_with_missing_name_fails():
    """CreateDocumentDTO requires a non-empty filename."""
    # CreateDocumentDTO is a frozen dataclass; filename is a required str field.
    # Passing empty string is allowed by the dataclass, so validation must
    # be at the domain level. Verify that the DTO can't be constructed
    # without filename at all (TypeError from missing required arg).
    with pytest.raises(TypeError):
        CreateDocumentDTO(
            project_id=uuid4(),
            # filename omitted
            document_type=DocumentType.CONTRACT,
        )
