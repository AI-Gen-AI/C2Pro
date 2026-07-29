"""EPIC-OPS-DOCFLOW Stream C: HITL reviewer identity spoofing regression.

Refers to Suite ID: TS-SEC-HITL-SPOOF-001.

The /hitl/queue/{item_id}/approve and /reject endpoints must record the
AUTHENTICATED session's identity as the reviewer, never a client-supplied
value — otherwise any authenticated user could forge a review as another
user (e.g. an admin/PM), corrupting the HITL audit trail (a core
differentiator).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import SubscriptionPlan, Tenant, User, UserRole
from src.core.auth.service import hash_password
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus

pytestmark = [pytest.mark.security, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def hitl_tenant(db: AsyncSession) -> Tenant:
    tenant = Tenant(
        id=uuid4(),
        name="HITL Spoof Test Company",
        slug=f"hitl-spoof-{uuid4().hex[:8]}",
        subscription_plan=SubscriptionPlan.PROFESSIONAL,
        subscription_status="active",
        ai_budget_monthly=100.0,
        ai_spend_current=0.0,
        max_projects=50,
        max_users=10,
        max_storage_gb=100,
        is_active=True,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def hitl_reviewer(db: AsyncSession, hitl_tenant: Tenant) -> User:
    """The real, authenticated reviewer making the request."""
    user = User(
        id=uuid4(),
        tenant_id=hitl_tenant.id,
        email="real_reviewer@test.com",
        hashed_password=hash_password("Password123!"),
        first_name="Real",
        last_name="Reviewer",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _seed_review_item(db: AsyncSession, tenant_id) -> ReviewItemORM:
    item_id = uuid4()
    item = ReviewItemORM(
        id=item_id,
        item_id=item_id,
        item_type="risk_extraction",
        current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        confidence=0.4,
        impact_level=ImpactLevel.HIGH,
        tenant_id=tenant_id,
        sla_due_date=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=3),
        item_data={},
        review_metadata={},
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def test_approve_records_authenticated_reviewer_not_spoofed_name(
    client,
    db: AsyncSession,
    hitl_tenant: Tenant,
    hitl_reviewer: User,
    generate_token,
) -> None:
    """A spoofed reviewer_name in the request body must never appear in
    the audit trail — approved_by must be the authenticated user's name."""
    item = await _seed_review_item(db, hitl_tenant.id)
    token = generate_token(
        user_id=hitl_reviewer.id,
        tenant_id=hitl_tenant.id,
        email=hitl_reviewer.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"/api/v1/hitl/queue/{item.item_id}/approve",
        json={"reviewer_name": "Forged Admin Identity"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["approved_by"] == "Real Reviewer"
    assert body["approved_by"] != "Forged Admin Identity"


async def test_approve_ignores_reviewer_id_even_when_supplied(
    client,
    db: AsyncSession,
    hitl_tenant: Tenant,
    hitl_reviewer: User,
    generate_token,
) -> None:
    """A spoofed reviewer_id in the request body has no effect — the DTO no
    longer accepts one, and identity is always server-derived."""
    item = await _seed_review_item(db, hitl_tenant.id)
    token = generate_token(
        user_id=hitl_reviewer.id,
        tenant_id=hitl_tenant.id,
        email=hitl_reviewer.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"/api/v1/hitl/queue/{item.item_id}/approve",
        json={"reviewer_id": str(uuid4()), "reviewer_name": "Forged Admin Identity"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["approved_by"] == "Real Reviewer"


async def test_reject_records_authenticated_reviewer_not_spoofed_name(
    client,
    db: AsyncSession,
    hitl_tenant: Tenant,
    hitl_reviewer: User,
    generate_token,
) -> None:
    """Same regression for the reject path, which previously discarded the
    authenticated user entirely and trusted only the client-supplied name."""
    item = await _seed_review_item(db, hitl_tenant.id)
    token = generate_token(
        user_id=hitl_reviewer.id,
        tenant_id=hitl_tenant.id,
        email=hitl_reviewer.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"/api/v1/hitl/queue/{item.item_id}/reject",
        json={"reviewer_name": "Forged Admin Identity", "reason": "Not accurate enough"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["approved_by"] == "Real Reviewer"
    assert body["approved_by"] != "Forged Admin Identity"
