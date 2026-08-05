"""V2 shadow-table persistence integration tests.

Refers to Suite ID: TS-INT-COH-V2-SHADOW-PERSIST-001.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.adapters.persistence import SqlAlchemyCoherenceRepository
from src.coherence.adapters.persistence.models import CoherenceResultORM, CoherenceV2ShadowORM
from src.core.auth.models import Tenant
from src.projects.adapters.persistence.models import ProjectORM


@pytest.fixture
async def shadow_persistence_project(db: AsyncSession, test_tenant: Tenant) -> ProjectORM:
    """TS-INT-COH-V2-SHADOW-PERSIST-001: create a tenant-owned project."""
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="V2 Shadow Persistence Project",
        code=f"V2S-{uuid4().hex[:8]}",
        description="Shadow score storage fixture",
    )
    db.add(project)
    await db.commit()
    return project


@pytest.mark.asyncio
async def test_shadow_rows_do_not_leak_into_v1_latest_read(
    db: AsyncSession,
    test_tenant: Tenant,
    shadow_persistence_project: ProjectORM,
) -> None:
    """TS-INT-COH-V2-SHADOW-PERSIST-001: v1 latest reads only coherence_results."""
    v1_row = CoherenceResultORM(
        project_id=shadow_persistence_project.id,
        tenant_id=test_tenant.id,
        global_score=73,
        category_scores={},
        category_details=[],
        alerts=[],
        is_gaming_detected=False,
        gaming_violations=[],
        penalty_points=0,
        score_version="coherence-v1",
    )
    shadow_row = CoherenceV2ShadowORM(
        project_id=shadow_persistence_project.id,
        tenant_id=test_tenant.id,
        coherence_score=99.0,
        completeness_score=1.0,
        technical_reliability_index=0.9,
        active_weight=1.0,
        score_version="coherence-v2",
        status="scored",
        score_reason="scored_categories_only",
        categories_v2=[],
    )
    db.add_all([v1_row, shadow_row])
    await db.commit()

    repository = SqlAlchemyCoherenceRepository(db, tenant_id=test_tenant.id)
    latest = await repository.get_latest_for_project(shadow_persistence_project.id)

    assert latest is not None
    assert latest.global_score == 73
