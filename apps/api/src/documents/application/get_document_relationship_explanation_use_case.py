"""
TS-UA-DOC-REL-001

Use case for producing a grounded relationship explanation for a document.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import HTTPException, status

from src.core.tenants.types import require_tenant_id
from src.documents.application.dtos import (
    DocumentRelationshipExplanationResponse,
    RelationshipExplanationCitationResponse,
)
from src.documents.application.services.relationship_explanation_service import (
    EvidenceRelationshipExplanationService,
    ExplanationAlertInput,
)
from src.documents.ports.document_repository import IDocumentRepository
from src.shared_kernel.enums import AlertSeverity


class GetDocumentRelationshipExplanationUseCase:
    """Load a document aggregate and linked alerts, then build an explanation payload."""

    def __init__(
        self,
        document_repository: IDocumentRepository,
        explanation_service: EvidenceRelationshipExplanationService,
    ):
        self.document_repository = document_repository
        self.explanation_service = explanation_service

    async def execute(
        self, tenant_id: UUID, document_id: UUID
    ) -> DocumentRelationshipExplanationResponse:
        scoped_tenant_id = require_tenant_id(tenant_id)
        document = await self.document_repository.get_document_with_clauses(
            scoped_tenant_id, document_id
        )
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        clause_ids = {clause.id for clause in document.clauses}
        alert_signals = await self.document_repository.list_alert_signals_for_document(
            scoped_tenant_id, document_id
        )
        filtered_alerts = [
            ExplanationAlertInput(
                id=alert.id,
                title=alert.title,
                severity=cast(AlertSeverity, alert.severity),
                status=alert.status,
                created_at=alert.created_at,
                updated_at=alert.updated_at,
                source_clause_id=alert.source_clause_id,
            )
            for alert in alert_signals
            if alert.source_clause_id is None or alert.source_clause_id in clause_ids
        ]

        explanation = self.explanation_service.build(document=document, alerts=filtered_alerts)
        return DocumentRelationshipExplanationResponse(
            document_id=document.id,
            summary=explanation.summary,
            strongest_cluster=explanation.strongest_cluster,
            review_priority=explanation.review_priority,
            latest_signal=explanation.latest_signal,
            citations=[
                RelationshipExplanationCitationResponse(
                    clause_id=citation.clause_id,
                    clause_code=citation.clause_code,
                    label=citation.label,
                    page=citation.page,
                    reason=citation.reason,
                )
                for citation in explanation.citations
            ],
        )
