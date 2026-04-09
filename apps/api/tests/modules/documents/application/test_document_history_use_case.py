"""
TS-UA-DOC-HIST-001

Tests for GetDocumentHistoryUseCase.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.documents.application.get_document_history_use_case import GetDocumentHistoryUseCase
from src.documents.domain.models import (
    Document,
    DocumentAlertHistoryEntry,
    DocumentEvidenceAlert,
    DocumentHistorySnapshot,
    DocumentStatus,
    DocumentType,
)


def _build_document() -> Document:
    return Document(
        id=uuid4(),
        project_id=uuid4(),
        document_type=DocumentType.CONTRACT,
        filename="Prime Contract.pdf",
        upload_status=DocumentStatus.PARSED,
        created_at=datetime(2026, 4, 1, 9, 0, 0),
        parsed_at=datetime(2026, 4, 2, 10, 15, 0),
    )


@pytest.mark.asyncio
async def test_execute_builds_sorted_document_and_alert_history() -> None:
    """Use case should combine document milestones and alert history into an ordered response."""
    document = _build_document()
    repository = MagicMock()
    repository.get_history_snapshot = AsyncMock(
        return_value=DocumentHistorySnapshot(
            document=document,
            clause_count=2,
            alerts=[
                DocumentEvidenceAlert(
                    id=uuid4(),
                    title="Delay penalty risk",
                    created_at=datetime(2026, 4, 3, 8, 0, 0),
                    history=[
                        DocumentAlertHistoryEntry(
                            action="reviewed",
                            detail="Delay penalty risk · approved",
                            occurred_at=datetime(2026, 4, 4, 11, 30, 0),
                        )
                    ],
                )
            ],
        )
    )

    response = await GetDocumentHistoryUseCase(document_repository=repository).execute(document.id)

    assert response.document_id == document.id
    assert [item.title for item in response.items] == [
        "Document uploaded",
        "Document parsed",
        "Alert created",
        "Alert Reviewed",
    ]
    assert response.items[1].detail == "2 clauses extracted"


@pytest.mark.asyncio
async def test_execute_uses_alert_created_at_when_history_omits_created_event() -> None:
    """Use case should synthesize the created event when alert history starts later in the lifecycle."""
    document = _build_document()
    alert_id = uuid4()
    repository = MagicMock()
    repository.get_history_snapshot = AsyncMock(
        return_value=DocumentHistorySnapshot(
            document=document,
            clause_count=1,
            alerts=[
                DocumentEvidenceAlert(
                    id=alert_id,
                    title="Unpriced change order",
                    created_at=datetime(2026, 4, 3, 8, 0, 0),
                    history=[],
                )
            ],
        )
    )

    response = await GetDocumentHistoryUseCase(document_repository=repository).execute(document.id)

    created_events = [item for item in response.items if item.source_id == str(alert_id)]
    assert len(created_events) == 1
    assert created_events[0].title == "Alert created"
    assert created_events[0].detail == "Unpriced change order"
