"""
Coherence repository score-version persistence tests.

Refers to Suite ID: TS-INT-DB-COH-001.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.adapters.persistence import SqlAlchemyCoherenceRepository
from src.coherence.application.dtos import CategoryScoreDetail, CoherenceCalculationResult
from src.coherence.domain.category_weights import CoherenceCategory
from src.core.auth.models import Tenant
from src.projects.adapters.persistence.models import ProjectORM


@pytest.fixture
async def repository_project(db: AsyncSession, test_tenant: Tenant) -> ProjectORM:
    """TS-INT-DB-COH-001: Create a tenant-owned project for repository round trips."""
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Coherence Versioning Project",
        code=f"COH-{uuid4().hex[:8]}",
        description="Repository score versioning fixture",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@pytest.mark.asyncio
async def test_repository_roundtrip_preserves_score_version_fields(
    db: AsyncSession,
    repository_project: ProjectORM,
) -> None:
    """TS-INT-DB-COH-001: Save/read preserves score_version audit-trail fields."""
    result = CoherenceCalculationResult(
        project_id=repository_project.id,
        global_score=72,
        category_scores={category: 72 for category in CoherenceCategory},
        category_details=[
            CategoryScoreDetail(category=category, score=72, violations=[])
            for category in CoherenceCategory
        ],
        alerts=[],
        is_gaming_detected=False,
        gaming_violations=[],
        penalty_points=0,
        score_version="v1_exponential_decay",
        score_reason="insufficient_evidence",
        score_missing_dimensions=["BUDGET", "TIME"],
    )
    repository = SqlAlchemyCoherenceRepository(db, tenant_id=repository_project.tenant_id)

    result_id = await repository.save(result)
    retrieved = await repository.get_by_id(result_id)

    assert retrieved is not None
    assert retrieved.score_version == "v1_exponential_decay"
    assert retrieved.score_reason == "insufficient_evidence"
    assert retrieved.score_missing_dimensions == ["BUDGET", "TIME"]
