"""DocumentArtifact repository port (ADR-017 / TASK-V3-017-03).

TS-INT-ADR017-ART-001
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.analysis.domain.contracts import DocumentArtifact
from src.core.tenants.types import TenantId


class IDocumentArtifactRepository(Protocol):
    async def save(
        self,
        artifact: DocumentArtifact,
        *,
        project_id: UUID,
        tenant_id: TenantId,
    ) -> DocumentArtifact: ...

    async def list_active_for_project(
        self,
        *,
        project_id: UUID,
        tenant_id: TenantId,
    ) -> list[DocumentArtifact]: ...

    async def list_superseded_for_document(
        self,
        *,
        project_id: UUID,
        tenant_id: TenantId,
        document_id: UUID,
    ) -> list[DocumentArtifact]: ...


__all__ = ["IDocumentArtifactRepository"]
