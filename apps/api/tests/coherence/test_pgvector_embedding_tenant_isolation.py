"""TS-INT-DB-COH-EMBED-TENANT-001.

Regression coverage for tenant-scoped pgvector clause-embedding writes.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.adapters.persistence.pgvector_embedding_repository import (
    PgvectorEmbeddingRepository,
)
from src.coherence.ports.embedding_repository import EmbeddingRecord
from src.core.tenants.types import TenantId
from src.projects.adapters.persistence.models import ProjectORM


def _project(*, project_id: UUID, tenant_id: UUID) -> ProjectORM:
    """Create the minimum persisted project required by the embedding repository."""
    now = datetime.now(UTC).replace(tzinfo=None)
    return ProjectORM(
        id=project_id,
        tenant_id=tenant_id,
        name="Tenant-scoped embedding project",
        description=None,
        code=f"EMB-{project_id.hex[:8]}",
        project_type="construction",
        status="draft",
        estimated_budget=0.0,
        currency="EUR",
        start_date=None,
        end_date=None,
        coherence_score=None,
        last_analysis_at=None,
        metadata_json={},
        created_at=now,
        updated_at=now,
    )


def test_all_clause_embedding_insert_statements_bind_tenant_id() -> None:
    """TS-INT-DB-COH-EMBED-TENANT-001: every raw embedding write is tenant-bound."""
    source = inspect.getsource(PgvectorEmbeddingRepository)
    inserts = source.split("INSERT INTO clause_embeddings")[1:]

    assert len(inserts) == 3
    for insert in inserts:
        assert "tenant_id" in insert.split("ON CONFLICT", maxsplit=1)[0]
        assert "CAST(:tenant_id AS uuid)" in insert


@pytest.mark.asyncio
async def test_store_embedding_rejects_missing_tenant_context() -> None:
    """TS-INT-DB-COH-EMBED-TENANT-001: writes never fabricate a tenant ID."""
    session = AsyncMock()
    repository = PgvectorEmbeddingRepository(session, tenant_id=None)

    with pytest.raises(ValueError, match="tenant context"):
        await repository.store_embedding(
            clause_id="missing-tenant",
            project_id=uuid4(),
            embedding=[0.1] * 1536,
        )

    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_store_embedding_persists_and_filters_by_repository_tenant(
    db: AsyncSession,
) -> None:
    """TS-INT-DB-COH-EMBED-TENANT-001: writes remain visible only to their tenant."""
    tenant_a = TenantId(uuid4())
    tenant_b = TenantId(uuid4())
    project_id = uuid4()
    clause_id = f"tenant-clause-{uuid4().hex}"
    db.add(_project(project_id=project_id, tenant_id=tenant_a))
    await db.commit()

    repository = PgvectorEmbeddingRepository(db, tenant_id=tenant_a)
    await repository.store_embedding(
        clause_id=clause_id,
        project_id=project_id,
        embedding=[0.1] * 1536,
        document_type="contract",
        text="Tenant-scoped clause",
        category="SCOPE",
    )
    await repository.store_embeddings_batch(
        [
            EmbeddingRecord(
                clause_id=f"tenant-batch-{uuid4().hex}",
                project_id=project_id,
                document_type="budget",
                text="Tenant-scoped batch clause",
                embedding=[0.2] * 1536,
                category="BUDGET",
            )
        ]
    )

    await db.execute(
        text("SELECT set_config('app.current_tenant', :tenant_id, false)"),
        {"tenant_id": str(tenant_a)},
    )
    visible = await db.scalar(
        text(
            """
            SELECT COUNT(*)
            FROM clause_embeddings
            WHERE project_id = CAST(:project_id AS uuid)
              AND tenant_id = CAST(current_setting('app.current_tenant', true) AS uuid)
            """
        ),
        {"project_id": str(project_id)},
    )
    assert visible == 2

    await db.execute(
        text("SELECT set_config('app.current_tenant', :tenant_id, false)"),
        {"tenant_id": str(tenant_b)},
    )
    invisible = await db.scalar(
        text(
            """
            SELECT COUNT(*)
            FROM clause_embeddings
            WHERE project_id = CAST(:project_id AS uuid)
              AND tenant_id = CAST(current_setting('app.current_tenant', true) AS uuid)
            """
        ),
        {"project_id": str(project_id)},
    )
    assert invisible == 0
