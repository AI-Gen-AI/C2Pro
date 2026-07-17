"""
TS-UA-DOC-HIST-001

Use case for building a persisted document evidence timeline.
"""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from fastapi import HTTPException, status

from src.core.tenants.types import require_tenant_id
from src.documents.application.dtos import DocumentHistoryResponse, EvidenceHistoryEventResponse
from src.documents.domain.models import DocumentHistorySnapshot
from src.documents.ports.document_repository import IDocumentRepository


class GetDocumentHistoryUseCase:
    """Compose document milestones and linked alert events into an ordered response."""

    def __init__(self, document_repository: IDocumentRepository):
        self.document_repository = document_repository

    async def execute(self, tenant_id: UUID, document_id: UUID) -> DocumentHistoryResponse:
        snapshot = await self.document_repository.get_history_snapshot(
            require_tenant_id(tenant_id), document_id
        )
        if snapshot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        return self._build_response(snapshot)

    @staticmethod
    def _build_response(snapshot: DocumentHistorySnapshot) -> DocumentHistoryResponse:
        document = snapshot.document
        clause_label = "clause" if snapshot.clause_count == 1 else "clauses"

        events: list[EvidenceHistoryEventResponse] = [
            EvidenceHistoryEventResponse(
                id=f"document-uploaded-{document.id}",
                title="Document uploaded",
                detail=document.filename,
                occurred_at=cast(datetime, document.created_at),
                source_type="document",
                source_id=str(document.id),
            )
        ]

        if document.parsed_at is not None:
            events.append(
                EvidenceHistoryEventResponse(
                    id=f"document-parsed-{document.id}",
                    title="Document parsed",
                    detail=f"{snapshot.clause_count} {clause_label} extracted",
                    occurred_at=document.parsed_at,
                    source_type="document",
                    source_id=str(document.id),
                )
            )

        for alert in snapshot.alerts:
            events.append(
                EvidenceHistoryEventResponse(
                    id=f"alert-created-{alert.id}",
                    title="Alert created",
                    detail=alert.title,
                    occurred_at=alert.created_at,
                    source_type="alert",
                    source_id=str(alert.id),
                )
            )
            for index, history_item in enumerate(alert.history):
                events.append(
                    EvidenceHistoryEventResponse(
                        id=f"alert-history-{alert.id}-{index}",
                        title=f"Alert {history_item.action.replace('_', ' ').title()}",
                        detail=history_item.detail,
                        occurred_at=history_item.occurred_at,
                        source_type="alert",
                        source_id=str(alert.id),
                    )
                )

        events.sort(key=lambda event: event.occurred_at)
        return DocumentHistoryResponse(document_id=document.id, items=events)
