"""#711 explicit Retry resets the automatic recovery budget."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.documents.adapters.http import router
from src.documents.domain.models import Document, DocumentStatus, DocumentType


@pytest.mark.asyncio
async def test_reprocess_clears_only_processing_recovery_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    document = Document(
        id=document_id,
        project_id=project_id,
        tenant_id=tenant_id,
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        upload_status=DocumentStatus.ERROR,
        document_metadata={
            "processing_recovery": {
                "stage": DocumentStatus.PARSING.value,
                "generation": "v1:legacy",
                "attempts": 3,
            },
            "business_metadata": "preserve-me",
        },
    )

    repo = Mock()
    repo.get_by_id = AsyncMock(return_value=document)

    async def _update_status(_tenant_id, _document_id, status, **_kwargs):
        document.upload_status = status

    async def _update_metadata(_tenant_id, _document_id, metadata):
        document.document_metadata = metadata

    repo.update_status = AsyncMock(side_effect=_update_status)
    repo.update_metadata = AsyncMock(side_effect=_update_metadata)
    repo.commit = AsyncMock()
    repo.refresh = AsyncMock()
    monkeypatch.setattr(
        router,
        "_enqueue_document_processing",
        lambda _document_id: "retry-task",
    )

    response = await router.reprocess_document_endpoint(
        project_id=project_id,
        document_id=document_id,
        user_id=uuid4(),
        tenant_id=tenant_id,
        repo=repo,
    )

    repo.update_metadata.assert_awaited_once_with(
        tenant_id,
        document_id,
        {"business_metadata": "preserve-me"},
    )
    assert response.task_id == "retry-task"
    assert document.document_metadata == {"business_metadata": "preserve-me"}
