"""Tenant-scoped, read-only inventory of immutable document revision evidence.

This report counts physically persisted clauses in each *explicit* revision.
It NEVER changes the current revision or feeds trusted Health/Coherence.
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel

from src.core.tenants.types import require_tenant_id
from src.documents.ports.document_repository import IDocumentRepository
from src.temporal.application.revision_status import RevisionStatus
from src.temporal.ports.document_revision_repository import IDocumentRevisionRepository


class RevisionStatusReader(Protocol):
    async def read(
        self, *, tenant_id: UUID, project_id: UUID, document_id: UUID, revision_id: UUID
    ) -> RevisionStatus | None: ...


class DocumentRevisionEvidenceItem(BaseModel):
    revision_id: UUID
    rev_no: int
    clause_count: int
    scope: str
    trusted_current: bool
    trust_state: str | None = None


class DocumentRevisionEvidenceReport(BaseModel):
    document_id: UUID
    items: list[DocumentRevisionEvidenceItem]
    current_trusted_revision_id: UUID | None
    total_persisted_clauses: int


class ListDocumentRevisionEvidenceUseCase:
    """Historical/proposed clause inventory, never canonical promotion."""

    def __init__(
        self,
        *,
        document_repository: IDocumentRepository,
        revision_repository: IDocumentRevisionRepository,
        status_reader: RevisionStatusReader,
    ) -> None:
        self._documents = document_repository
        self._revisions = revision_repository
        self._statuses = status_reader

    async def execute(
        self, *, tenant_id: UUID, document_id: UUID
    ) -> DocumentRevisionEvidenceReport:
        tenant_id = require_tenant_id(tenant_id)
        doc = await self._documents.get_by_id(tenant_id, document_id)
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        lineage = await self._revisions.list_lineage(document_id, tenant_id)
        items: list[DocumentRevisionEvidenceItem] = []
        current_trusted_revision_id: UUID | None = None
        for revision in lineage:
            if (
                revision.tenant_id != tenant_id
                or revision.document_id != document_id
                or revision.project_id != doc.project_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Revision not found.",
                )
            # These are revision-bound rows, not a trusted-current projection.
            clauses = await self._documents.list_clauses_bound_to_revision(
                tenant_id, document_id, revision.revision_id
            )
            revision_status = await self._statuses.read(
                tenant_id=tenant_id,
                project_id=doc.project_id,
                document_id=document_id,
                revision_id=revision.revision_id,
            )
            source = revision_status if revision_status and revision_status.status == "available" else None
            trusted_current = bool(
                source
                and source.trust_state == "trusted"
                and source.is_current
                and source.current_basis == "trusted"
            )
            if trusted_current:
                current_trusted_revision_id = revision.revision_id
                scope = "trusted_current"
            elif source and source.trust_state == "proposed":
                scope = "proposed"
            elif source and source.current_basis == "trusted" and source.trust_state in (
                "trusted", "rejected", "superseded"
            ):
                scope = "historical"
            else:
                scope = "unresolved"
            items.append(
                DocumentRevisionEvidenceItem(
                    revision_id=revision.revision_id,
                    rev_no=revision.rev_no,
                    clause_count=len(clauses),
                    scope=scope,
                    trusted_current=trusted_current,
                    trust_state=source.trust_state if source else None,
                )
            )
        return DocumentRevisionEvidenceReport(
            document_id=document_id,
            items=items,
            current_trusted_revision_id=current_trusted_revision_id,
            total_persisted_clauses=sum(item.clause_count for item in items),
        )
