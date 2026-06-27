"""
Unit tests for ParseDocumentUseCase.
Verifies that the use case correctly orchestrates document parsing and persists metadata.
"""
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.documents.application.parse_document_use_case import ParseDocumentUseCase
from src.documents.domain.models import Document, DocumentStatus, DocumentType


@pytest.fixture
def mock_repository():
    repo = MagicMock(spec=["get_by_id", "update_status", "update_metadata", "commit"])
    repo.update_metadata = AsyncMock()
    return repo


@pytest.fixture
def mock_storage():
    return MagicMock(spec=["download_file"])


@pytest.fixture
def mock_parser():
    return MagicMock(spec=["parse_document_file"])


@pytest.fixture
def mock_extraction():
    mock = MagicMock(spec=["extract_entities_from_document"])
    mock.extract_entities_from_document = AsyncMock()
    return mock


@pytest.fixture
def mock_rag():
    mock = MagicMock(spec=["ingest_document_chunks"])
    mock.ingest_document_chunks = AsyncMock()
    return mock


@pytest.fixture
def use_case(mock_repository, mock_storage, mock_parser, mock_extraction, mock_rag):
    return ParseDocumentUseCase(
        document_repository=mock_repository,
        storage_service=mock_storage,
        file_parser_service=mock_parser,
        entity_extraction_service=mock_extraction,
        rag_ingestion_service=mock_rag,
    )


@pytest.fixture
def sample_document():
    return Document(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        upload_status=DocumentStatus.UPLOADED,
        file_format=".pdf",
    )


class _BudgetRows(list):
    stated_total: float = 654_144_805.0


@pytest.mark.asyncio
async def test_parse_document_updates_parsed_at(
    use_case,
    mock_repository,
    mock_storage,
    mock_parser,
    sample_document,
):
    """TASK-BCK-063: Verify that parsed_at is passed to repository on success."""
    tenant_id = sample_document.tenant_id
    document_id = sample_document.id
    user_id = uuid4()

    # Setup mocks
    mock_repository.get_by_id = AsyncMock(return_value=sample_document)
    mock_repository.update_status = AsyncMock()
    mock_repository.commit = AsyncMock()

    mock_storage.download_file = AsyncMock(return_value=Path("/tmp/contract.pdf"))
    mock_parser.parse_document_file = AsyncMock(return_value={"text_blocks": []})

    # We use patch for datetime.now to have a stable timestamp for verification
    fixed_now = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    with patch("src.documents.application.parse_document_use_case.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_now

        await use_case.execute(tenant_id, document_id, user_id)

    # Verify update_status was called with status=PARSED and parsed_at=fixed_now
    # It is called twice: once for PARSING and once for PARSED
    mock_repository.update_status.assert_any_call(
        tenant_id, document_id, DocumentStatus.PARSING
    )

    mock_repository.update_status.assert_any_call(
        tenant_id,
        document_id,
        DocumentStatus.PARSED,
        parsing_error=None,
        parsed_at=fixed_now,
    )

    assert mock_repository.commit.call_count == 2


@pytest.mark.asyncio
async def test_parse_document_persists_budget_stated_total(
    use_case,
    mock_repository,
    mock_storage,
    mock_parser,
    sample_document,
):
    """TS-COH-BUD-RECON-004: budget declared total is stored in document metadata."""
    budget_document = Document(
        id=sample_document.id,
        project_id=sample_document.project_id,
        tenant_id=sample_document.tenant_id,
        document_type=DocumentType.BUDGET,
        filename="budget.xlsx",
        upload_status=DocumentStatus.UPLOADED,
        file_format=".xlsx",
    )
    tenant_id = budget_document.tenant_id
    document_id = budget_document.id
    user_id = uuid4()

    budget_rows = _BudgetRows(
        [{"item": "Capitulo 01", "quantity": 1, "unit_price": 100.0, "total": 100.0}]
    )
    mock_repository.get_by_id = AsyncMock(return_value=budget_document)
    mock_repository.update_status = AsyncMock()
    mock_repository.commit = AsyncMock()
    mock_storage.download_file = AsyncMock(return_value=Path("/tmp/budget.xlsx"))
    mock_parser.parse_document_file = AsyncMock(
        return_value={"file_format": ".xlsx", "budget": budget_rows}
    )

    await use_case.execute(tenant_id, document_id, user_id)

    mock_repository.update_metadata.assert_awaited_with(
        tenant_id,
        document_id,
        {"stated_total": 654_144_805.0},
    )


@pytest.mark.asyncio
async def test_parse_document_handles_not_found(use_case, mock_repository):
    mock_repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc:
        await use_case.execute(uuid4(), uuid4(), uuid4())

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_parse_document_handles_failure(
    use_case,
    mock_repository,
    mock_storage,
    sample_document,
):
    tenant_id = sample_document.tenant_id
    document_id = sample_document.id

    mock_repository.get_by_id = AsyncMock(return_value=sample_document)
    mock_repository.update_status = AsyncMock()
    mock_repository.commit = AsyncMock()

    mock_storage.download_file = AsyncMock(side_effect=RuntimeError("Storage boom"))

    with pytest.raises(RuntimeError, match="Storage boom"):
        await use_case.execute(tenant_id, document_id, uuid4())

    # Verify status updated to ERROR
    mock_repository.update_status.assert_any_call(
        tenant_id, document_id, DocumentStatus.ERROR, parsing_error="Storage boom"
    )
    assert mock_repository.commit.call_count == 2
