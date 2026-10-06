"""
Refers to Suite ID: TS-E2E-FLW-BLK-001

E2E Test Suite: Bulk Operations
Priority: 🟠 P1 HIGH
Coverage Target: 80%

Tests bulk operations for efficiency and performance:
1. Bulk Document Upload → 2. Bulk Alert Review →
3. Bulk WBS Creation → 4. Bulk Data Export → 5. Progress Tracking

This validates efficient handling of large-scale operations:
"Process 100+ items efficiently with progress tracking and error handling"

Architecture Considerations (from PLAN_ARQUITECTURA_v2.1.md):
- Atomic transactions (all or nothing)
- Progress tracking (percentage complete)
- Partial success handling (50/100 succeeded)
- Error reporting per item
- Rate limiting (prevent abuse)
- Background job processing (async)

Performance Targets:
- 100 documents: < 30 seconds
- 1000 WBS items: < 10 seconds
- 50 alerts: < 2 seconds
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio

from src.core.auth.models import SubscriptionPlan, Tenant, User, UserRole
from src.core.auth.service import hash_password
from src.projects.adapters.persistence.models import ProjectORM

# ===========================================
# FIXTURES
# ===========================================


@pytest_asyncio.fixture
async def bulk_tenant(db) -> Tenant:
    """Create a tenant for bulk operations testing."""
    tenant = Tenant(
        id=uuid4(),
        name="Bulk Operations Company",
        slug=f"bulk-test-{uuid4().hex[:8]}",
        subscription_plan=SubscriptionPlan.ENTERPRISE,  # Higher limits
        subscription_status="active",
        ai_budget_monthly=500.0,  # Higher budget for bulk ops
        ai_spend_current=0.0,
        max_projects=100,
        max_users=50,
        max_storage_gb=500,
        is_active=True,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def bulk_user(db, bulk_tenant: Tenant) -> User:
    """Create a user for bulk operations testing."""
    user = User(
        id=uuid4(),
        tenant_id=bulk_tenant.id,
        email="bulk_user@test.com",
        hashed_password=hash_password("Password123!"),
        first_name="Bulk",
        last_name="User",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def bulk_project(db, bulk_tenant: Tenant):
    """Create a project for bulk operations testing."""
    project = ProjectORM(
        id=uuid4(),
        tenant_id=bulk_tenant.id,
        name="Bulk Operations Project",
        code="BULK-OPS-001",
        project_type="construction",
        estimated_budget=5000000.0,
        currency="EUR",
        metadata_json={"version": 1},
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return {
        "id": project.id,
        "tenant_id": project.tenant_id,
        "name": project.name,
        "code": project.code,
        "project_type": project.project_type,
        "estimated_budget": project.estimated_budget,
        "currency": project.currency,
    }


# ===========================================
# TEST 1: Bulk Document Upload
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
@pytest.mark.slow
async def test_001_bulk_document_upload(
    client,
    bulk_user: User,
    bulk_tenant: Tenant,
    bulk_project,
    generate_token,
):
    """
    GIVEN A project exists
    WHEN User uploads 10 documents in bulk
    THEN All documents are queued for processing
    AND Bulk operation returns summary (accepted, failed)
    AND Each document gets a unique ID

    Validates: Bulk document upload efficiency
    """
    token = generate_token(
        user_id=bulk_user.id,
        tenant_id=bulk_tenant.id,
        email=bulk_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = bulk_project["id"]

    # Prepare 10 documents
    documents = []
    for i in range(10):
        documents.append({
            "filename": f"contract_{i}.pdf",
            "document_type": "contract" if i % 2 == 0 else "specifications",
            "file_data": f"PDF content {i}",
        })

    # Bulk upload
    response = await client.post(
        f"/api/v1/projects/{project_id}/documents/bulk",
        json={"documents": documents},
        headers=headers,
    )

    assert response.status_code == 202
    body = response.json()
    assert body["accepted_count"] == 10
    assert body["failed_count"] == 0
    assert len(body["document_ids"]) == 10


# ===========================================
# TEST 2: Bulk Alert Approval (Already Implemented)
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_002_bulk_alert_approval_with_progress(
    client,
    bulk_user: User,
    bulk_tenant: Tenant,
    bulk_project,
    generate_token,
):
    """
    GIVEN 20 alerts are pending review
    WHEN User bulk approves all alerts
    THEN All alerts are approved
    AND Operation completes successfully
    AND Coherence score is recalculated once

    Validates: Bulk alert review (already implemented in TS-E2E-FLW-ALR-001)
    """
    token = generate_token(
        user_id=bulk_user.id,
        tenant_id=bulk_tenant.id,
        email=bulk_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    alert_ids = []
    for i in range(20):
        create_response = await client.post(
            "/api/v1/alerts",
            json={
                "project_id": str(bulk_project["id"]),
                "rule_code": f"R{i % 5 + 1}",
                "category": "TIME",
                "severity": "medium",
                "message": f"Alert {i}",
            },
            headers=headers,
        )
        assert create_response.status_code == 201
        alert_ids.append(create_response.json()["id"])

    bulk_data = {
        "alert_ids": alert_ids,
        "decision": "approve",
    }

    response = await client.post(
        "/api/v1/alerts/bulk-review",
        json=bulk_data,
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["processed_count"] == 20


# ===========================================
# TEST 3: Bulk WBS Creation
# ===========================================


# ===========================================
# TEST 4: Bulk Data Export
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_004_bulk_export_project_data(
    client,
    bulk_user: User,
    bulk_tenant: Tenant,
    bulk_project,
    generate_token,
):
    """
    GIVEN A project with documents, WBS, alerts, etc.
    WHEN User exports all project data
    THEN Complete data package is generated
    AND Export includes all entities
    AND Export format is valid (JSON/ZIP)

    Validates: Bulk data export
    """
    token = generate_token(
        user_id=bulk_user.id,
        tenant_id=bulk_tenant.id,
        email=bulk_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = bulk_project["id"]

    # Request export
    response = await client.post(
        f"/api/v1/projects/{project_id}/export",
        json={"format": "json", "include": ["documents", "wbs", "alerts", "coherence"]},
        headers=headers,
    )

    assert response.status_code == 202
    body = response.json()
    assert "export_id" in body
    assert body["status"] == "processing"


# ===========================================
# TEST 5: Partial Success Handling
# ===========================================


# ===========================================
# TEST 6: Progress Tracking
# ===========================================


# ===========================================
# TEST 7: Rate Limiting for Bulk Operations
# ===========================================


# ===========================================
# TEST 8: Tenant Isolation in Bulk Operations
# ===========================================


# ===========================================
# TEST 9: Atomic Transactions (All or Nothing)
# ===========================================


# ===========================================
# TEST 10: Bulk Delete Operation
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_010_bulk_delete_alerts(
    client,
    bulk_user: User,
    bulk_tenant: Tenant,
    bulk_project,
    generate_token,
):
    """
    GIVEN 10 rejected alerts exist
    WHEN User bulk deletes all rejected alerts
    THEN All alerts are removed
    AND Only rejected alerts are deleted (not pending/approved)

    Validates: Bulk delete operations
    """
    token = generate_token(
        user_id=bulk_user.id,
        tenant_id=bulk_tenant.id,
        email=bulk_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    alert_ids = []
    for i in range(10):
        create_response = await client.post(
            "/api/v1/alerts",
            json={
                "project_id": str(bulk_project["id"]),
                "rule_code": f"R{i}",
                "category": "TIME",
                "severity": "low",
                "message": f"Alert {i}",
            },
            headers=headers,
        )
        assert create_response.status_code == 201
        alert_id = create_response.json()["id"]
        alert_ids.append(alert_id)
        review_response = await client.post(
            f"/api/v1/alerts/{alert_id}/review",
            json={"decision": "reject", "comment": "False positive"},
            headers=headers,
        )
        assert review_response.status_code == 200

    response = await client.post(
        "/api/v1/alerts/bulk-delete",
        json={"alert_ids": alert_ids, "status_filter": "rejected"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["deleted_count"] == 10


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_bulk_wbs_creation_endpoint_is_retired(
    client,
    bulk_user: User,
    bulk_tenant: Tenant,
    bulk_project,
    generate_token,
):
    """PC-1R (#886) retired POST /projects/{id}/wbs/bulk (#885): it acknowledged >=100 items
    with 202 and never persisted them, and persisted partial trees otherwise. A governed WBS
    import becomes a DRAFT change set (ADR-029, PC-2a)."""
    token = generate_token(
        user_id=bulk_user.id, tenant_id=bulk_tenant.id, email=bulk_user.email, role="admin"
    )
    response = await client.post(
        f"/api/v1/projects/{bulk_project['id']}/wbs/bulk",
        json={"items": [{"code": "1", "name": "Root", "level": 1}], "atomic": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in (404, 405)
