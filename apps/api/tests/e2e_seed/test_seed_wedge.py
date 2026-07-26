"""
Verifying test for seed_wedge_e2e — runs the seed against the test DB
and asserts all rows exist with the expected IDs and statuses.

Test Suite ID: TS-QA-338-SEED-WEDGE
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import Alert as AlertORM
from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.core.auth.models import Tenant, User
from src.documents.adapters.persistence.models import DocumentORM
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus
from src.projects.adapters.persistence.models import ProjectORM

from .seed_wedge import (
    ALERT_ID,
    COHERENCE_ID,
    DOC_BUDGET_ID,
    DOC_CONTRACT_ID,
    DOC_SCHEDULE_ID,
    PROJECT_ID,
    REVIEW_ID,
    TENANT_ID,
    USER_ID,
    seed_wedge_e2e,
)


@pytest.mark.requires_services
@pytest.mark.asyncio
async def test_seed_wedge_creates_tenant_and_user(db: AsyncSession) -> None:
    """Seed creates the deterministic tenant and Clerk user."""
    ids = await seed_wedge_e2e(db)

    assert ids["tenant_id"] == TENANT_ID
    assert ids["user_id"] == USER_ID

    tenant = await db.get(Tenant, TENANT_ID)
    assert tenant is not None
    assert tenant.slug == "i13-real-e2e-tenant"
    assert tenant.subscription_plan.value == "professional"
    assert tenant.is_active is True

    user = await db.get(User, USER_ID)
    assert user is not None
    assert user.email == "testuser@c2pro.com"
    assert user.role.value == "admin"


@pytest.mark.requires_services
@pytest.mark.asyncio
async def test_seed_wedge_creates_project(db: AsyncSession) -> None:
    """Seed creates the Wedge Gate Pilot project with correct code."""
    await seed_wedge_e2e(db)

    project = await db.get(ProjectORM, PROJECT_ID)
    assert project is not None
    assert project.name == "Wedge Gate Pilot"
    assert project.code == "WEDGE-3"
    assert project.status == "active"


@pytest.mark.requires_services
@pytest.mark.asyncio
async def test_seed_wedge_creates_document_triplet(db: AsyncSession) -> None:
    """Seed creates exactly 3 documents: contract, budget, schedule."""
    await seed_wedge_e2e(db)

    expected = [
        (DOC_CONTRACT_ID, "baseline-contract.pdf", "contract"),
        (DOC_BUDGET_ID, "validated-budget.xlsx", "budget"),
        (DOC_SCHEDULE_ID, "approved-schedule.xlsx", "schedule"),
    ]
    for doc_id, filename, doc_type in expected:
        doc = await db.get(DocumentORM, doc_id)
        assert doc is not None, f"Document {doc_id} missing"
        assert doc.filename == filename
        assert doc.document_type.value == doc_type
        assert doc.upload_status.value == "parsed"


@pytest.mark.requires_services
@pytest.mark.asyncio
async def test_seed_wedge_creates_coherence_result(db: AsyncSession) -> None:
    """Seed creates coherence result with all 6 category scores."""
    await seed_wedge_e2e(db)

    coh = await db.get(CoherenceResultORM, COHERENCE_ID)
    assert coh is not None
    assert coh.global_score == 82
    assert coh.score_version == "coherence-v1"

    scores = coh.category_scores
    assert scores["SCOPE"] == 84
    assert scores["BUDGET"] == 78
    assert scores["QUALITY"] == 86
    assert scores["TECHNICAL"] == 80
    assert scores["LEGAL"] == 88
    assert scores["TIME"] == 76


@pytest.mark.requires_services
@pytest.mark.asyncio
async def test_seed_wedge_creates_alert(db: AsyncSession) -> None:
    """Seed creates the alert referencing doc-contract."""
    await seed_wedge_e2e(db)

    alert = await db.get(AlertORM, ALERT_ID)
    assert alert is not None
    assert alert.title == "Budget deviation has supporting evidence"
    assert alert.severity.value == "medium"
    assert alert.status.value == "open"


@pytest.mark.requires_services
@pytest.mark.asyncio
async def test_seed_wedge_creates_hitl_review_item(db: AsyncSession) -> None:
    """Seed creates the HITL review item linked to the alert."""
    await seed_wedge_e2e(db)

    review = await db.get(ReviewItemORM, REVIEW_ID)
    assert review is not None
    assert review.item_type == "alert"
    assert review.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED
    assert review.confidence == pytest.approx(0.88)
    assert review.impact_level == ImpactLevel.MEDIUM
    assert review.item_data["summary"] == "Budget deviation has supporting evidence"
    assert review.project_id == PROJECT_ID
    assert review.document_id == DOC_CONTRACT_ID


@pytest.mark.requires_services
@pytest.mark.asyncio
async def test_seed_wedge_is_idempotent(db: AsyncSession) -> None:
    """Running seed twice does not create duplicate rows."""
    ids_1 = await seed_wedge_e2e(db)
    ids_2 = await seed_wedge_e2e(db)

    assert ids_1 == ids_2

    # Verify no duplicate tenants
    result = await db.execute(select(Tenant).where(Tenant.id == TENANT_ID))
    assert len(result.all()) == 1

    # Verify no duplicate projects
    result = await db.execute(select(ProjectORM).where(ProjectORM.id == PROJECT_ID))
    assert len(result.all()) == 1

    # Verify no duplicate documents
    result = await db.execute(select(DocumentORM).where(DocumentORM.project_id == PROJECT_ID))
    assert len(result.all()) == 3
