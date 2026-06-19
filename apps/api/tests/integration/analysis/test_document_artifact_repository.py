"""DocumentArtifact persistence tests (ADR-017 / TASK-V3-017-03).

TS-INT-ADR017-ART-001
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.domain.contracts import DocumentArtifact, RiskItem


def _artifact(document_id: str, title: str) -> DocumentArtifact:
    return DocumentArtifact(
        document_id=document_id,
        document_revision_id=None,
        doc_type="contract",
        extracted_risks=[RiskItem(title=title, description="Risk desc")],
    )


@pytest.mark.asyncio
async def test_document_artifact_roundtrip_and_supersede(db: AsyncSession) -> None:
    from src.analysis.adapters.persistence.document_artifact_repository import (
        SqlAlchemyDocumentArtifactRepository,
    )
    from src.analysis.adapters.persistence.models import DocumentArtifactORM

    project_id = uuid4()
    tenant_id = uuid4()
    document_id = uuid4()
    repo = SqlAlchemyDocumentArtifactRepository(db)

    first = await repo.save(
        _artifact(str(document_id), "First risk"),
        project_id=project_id,
        tenant_id=tenant_id,
    )
    second = await repo.save(
        _artifact(str(document_id), "Second risk"),
        project_id=project_id,
        tenant_id=tenant_id,
    )

    active = await repo.list_active_for_project(project_id=project_id, tenant_id=tenant_id)
    assert active == [second]
    assert active[0].extracted_risks[0].title == "Second risk"

    rows = (
        await db.execute(
            select(DocumentArtifactORM.lifecycle_status).where(
                DocumentArtifactORM.document_id == document_id
            )
        )
    ).scalars().all()
    assert sorted(rows) == ["active", "superseded"]
    assert first.document_id == second.document_id == str(document_id)


@pytest.mark.asyncio
async def test_document_artifact_list_filters_tenant(db: AsyncSession) -> None:
    from src.analysis.adapters.persistence.document_artifact_repository import (
        SqlAlchemyDocumentArtifactRepository,
    )

    project_id = uuid4()
    tenant_a = uuid4()
    tenant_b = uuid4()
    repo = SqlAlchemyDocumentArtifactRepository(db)

    await repo.save(
        _artifact(str(uuid4()), "Tenant A risk"),
        project_id=project_id,
        tenant_id=tenant_a,
    )
    await repo.save(
        _artifact(str(uuid4()), "Tenant B risk"),
        project_id=project_id,
        tenant_id=tenant_b,
    )

    active = await repo.list_active_for_project(project_id=project_id, tenant_id=tenant_a)

    assert len(active) == 1
    assert active[0].extracted_risks[0].title == "Tenant A risk"
