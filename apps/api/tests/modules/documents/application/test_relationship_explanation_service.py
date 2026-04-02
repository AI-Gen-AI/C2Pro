"""
TS-UA-SVC-EXT-002

Tests for the evidence relationship explanation service.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from src.analysis.domain.enums import AlertSeverity
from src.documents.application.services.relationship_explanation_service import (
    EvidenceRelationshipExplanationService,
    ExplanationAlertInput,
)
from src.documents.domain.models import Clause, ClauseType, Document, DocumentStatus, DocumentType


def _build_document() -> Document:
    document_id = uuid4()
    project_id = uuid4()

    return Document(
        id=document_id,
        project_id=project_id,
        document_type=DocumentType.CONTRACT,
        filename="Contract.pdf",
        upload_status=DocumentStatus.PARSED,
        created_at=datetime(2026, 1, 20, 9, 0, 0),
        updated_at=datetime(2026, 1, 21, 9, 0, 0),
        clauses=[
            Clause(
                id=uuid4(),
                project_id=project_id,
                document_id=document_id,
                clause_code="CL-001",
                clause_type=ClauseType.PENALTY,
                title="Delay penalty",
                full_text="Delay penalty applies after milestone slippage.",
                extraction_confidence=0.92,
                extracted_entities={"evidence_location": {"page_number": 3}},
            ),
            Clause(
                id=uuid4(),
                project_id=project_id,
                document_id=document_id,
                clause_code="CL-002",
                clause_type=ClauseType.RESPONSIBILITY,
                title="Notice requirements",
                full_text="Notice must be issued within 5 days.",
                extraction_confidence=0.88,
                extracted_entities={"evidence_location": {"page_number": 5}},
            ),
        ],
    )


def test_build_returns_explanation_grounded_in_alerts_and_clause_citations() -> None:
    """Service should produce a structured explanation with citations."""
    document = _build_document()
    alerts = [
        ExplanationAlertInput(
            id=uuid4(),
            title="Delay issue",
            severity=AlertSeverity.CRITICAL,
            status="open",
            created_at=datetime(2026, 1, 21, 14, 23, 0),
            updated_at=datetime(2026, 1, 21, 16, 30, 0),
            source_clause_id=document.clauses[0].id,
        ),
        ExplanationAlertInput(
            id=uuid4(),
            title="Notice gap",
            severity=AlertSeverity.HIGH,
            status="in_progress",
            created_at=datetime(2026, 1, 22, 8, 0, 0),
            updated_at=None,
            source_clause_id=document.clauses[1].id,
        ),
    ]

    explanation = EvidenceRelationshipExplanationService().build(
        document=document,
        alerts=alerts,
    )

    assert "2 extracted clauses" in explanation.summary
    assert "2 active alerts" in explanation.summary
    assert "delay penalty" in explanation.strongest_cluster.lower()
    assert "critical" in explanation.review_priority.lower()
    assert "notice gap" in explanation.latest_signal.lower()
    assert len(explanation.citations) >= 2
    assert explanation.citations[0].clause_code == "CL-001"
    assert explanation.citations[0].page == 3


def test_build_without_alerts_still_returns_clause_grounded_citations() -> None:
    """Service should still explain the document graph when no alerts exist."""
    document = _build_document()

    explanation = EvidenceRelationshipExplanationService().build(
        document=document,
        alerts=[],
    )

    assert "0 active alerts" in explanation.summary
    assert "no active alerts" in explanation.latest_signal.lower()
    assert len(explanation.citations) == 2
