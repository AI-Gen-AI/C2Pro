"""DocumentArtifact repository port (ADR-017 / TASK-V3-017-03).

TS-INT-ADR017-ART-001
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.analysis.domain.contracts import DocumentArtifact


class IDocumentArtifactRepository(Protocol):
    async def save(
        self,
        artifact: DocumentArtifact,
        *,
        project_id: UUID,
        tenant_id: UUID,
    ) -> DocumentArtifact: ...

    async def list_active_for_project(
        self,
        *,
        project_id: UUID,
        tenant_id: UUID,
    ) -> list[DocumentArtifact]: ...


__all__ = ["IDocumentArtifactRepository"]
