"""
TS-UA-DOC-REL-001

Tests for GetDocumentRelationshipExplanationUseCase.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.analysis.domain.enums import AlertSeverity
from src.documents.application.get_document_relationship_explanation_use_case import (
    GetDocumentRelationshipExplanationUseCase,
)
from src.documents.application.services.relationship_explanation_service import (
    EvidenceRelationshipExplanationService,
)
from src.documents.domain.models import (
    Clause,
    ClauseType,
    Document,
    DocumentAlertSignal,
    DocumentStatus,
    DocumentType,
)


def _build_document() -> Document:
    document_id = uuid4()
    project_id = uuid4()
    return Document(
        id=document_id,
        tenant_id=uuid4(),
        project_id=project_id,
        document_type=DocumentType.CONTRACT,
        filename="Contract.pdf",
        upload_status=DocumentStatus.PARSED,
        created_at=datetime(2026, 4, 1, 9, 0, 0),
        clauses=[
            Clause(
                id=uuid4(),
                tenant_id=uuid4(),
                project_id=project_id,
                document_id=document_id,
                clause_code="CL-001",
                clause_type=ClauseType.PENALTY,
                title="Delay penalty",
                full_text="Delay penalty applies after milestone slippage.",
                extraction_confidence=0.91,
                extracted_entities={"evidence_location": {"page_number": 3}},
            )
        ],
    )


@pytest.mark.asyncio
async def test_execute_builds_grounded_relationship_explanation_from_document_and_alerts() -> None:
    """Use case should delegate summarization to the explanation service with repository-backed alerts."""
    document = _build_document()
    repository = MagicMock()
    repository.get_document_with_clauses = AsyncMock(return_value=document)
    repository.list_alert_signals_for_document = AsyncMock(
        return_value=[
            DocumentAlertSignal(
                id=uuid4(),
                title="Delay issue",
                severity=AlertSeverity.CRITICAL,
                status="open",
                created_at=datetime(2026, 4, 2, 12, 0, 0),
                updated_at=datetime(2026, 4, 2, 14, 0, 0),
                source_clause_id=document.clauses[0].id,
            )
        ]
    )

    response = await GetDocumentRelationshipExplanationUseCase(
        document_repository=repository,
        explanation_service=EvidenceRelationshipExplanationService(),
    ).execute(uuid4(), document.id)

    assert response.document_id == document.id
    assert "1 extracted clauses" in response.summary
    assert "delay penalty" in response.strongest_cluster.lower()
    assert response.citations[0].clause_id == document.clauses[0].id
    repository.list_alert_signals_for_document.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_filters_alerts_for_missing_clause_links() -> None:
    """Use case should ignore alerts linked to clauses outside the loaded document aggregate."""
    document = _build_document()
    repository = MagicMock()
    repository.get_document_with_clauses = AsyncMock(return_value=document)
    repository.list_alert_signals_for_document = AsyncMock(
        return_value=[
            DocumentAlertSignal(
                id=uuid4(),
                title="Foreign alert",
                severity=AlertSeverity.HIGH,
                status="open",
                created_at=datetime(2026, 4, 2, 12, 0, 0),
                updated_at=None,
                source_clause_id=uuid4(),
            )
        ]
    )

    response = await GetDocumentRelationshipExplanationUseCase(
        document_repository=repository,
        explanation_service=EvidenceRelationshipExplanationService(),
    ).execute(uuid4(), document.id)

    assert "0 active alerts" in response.summary
