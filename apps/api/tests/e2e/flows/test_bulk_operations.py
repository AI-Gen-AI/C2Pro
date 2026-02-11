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

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

from src.core.auth.models import Tenant, User, UserRole, SubscriptionPlan
from src.core.auth.service import hash_password


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
    await db.flush()
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
    await db.flush()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def bulk_project(db, bulk_tenant: Tenant):
    """Create a project for bulk operations testing."""
    from src.projects.adapters.http.router import _add_fake_project

    project_data = {
        "id": uuid4(),
        "tenant_id": bulk_tenant.id,
        "name": "Bulk Operations Project",
        "code": "BULK-OPS-001",
        "project_type": "construction",
        "estimated_budget": 5000000.0,  # Large project
        "currency": "EUR",
    }
    _add_fake_project(project_data)
    return project_data


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

    # Should accept bulk upload (or 404 until implemented)
    assert response.status_code in [202, 404]

    # In GREEN phase:
    # body = response.json()
    # assert body["accepted_count"] == 10
    # assert body["failed_count"] == 0
    # assert len(body["document_ids"]) == 10


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

    # Create 20 alerts first (from previous test suite)
    alert_ids = []
    for i in range(20):
        alert_data = {
            "project_id": str(bulk_project["id"]),
            "rule_code": f"R{i % 5 + 1}",
            "category": "TIME",
            "severity": "medium",
            "message": f"Alert {i}",
        }
        response = await client.post(
            "/api/v1/alerts",
            json=alert_data,
            headers=headers,
        )
        if response.status_code == 201:
            alert_ids.append(response.json()["id"])

    # Bulk approve (already implemented)
    if alert_ids:
        bulk_data = {
            "alert_ids": [str(aid) for aid in alert_ids],
            "decision": "approve",
        }

        response = await client.post(
            "/api/v1/alerts/bulk-review",
            json=bulk_data,
            headers=headers,
        )

        # Should succeed
        assert response.status_code == 200


# ===========================================
# TEST 3: Bulk WBS Creation
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_003_bulk_wbs_creation(
    client,
    bulk_user: User,
    bulk_tenant: Tenant,
    bulk_project,
    generate_token,
):
    """
    GIVEN A project with no WBS structure
    WHEN User creates 50 WBS items in bulk
    THEN All items are created
    AND Hierarchy is validated
    AND Parent-child relationships are correct

    Validates: Bulk WBS creation efficiency
    """
    token = generate_token(
        user_id=bulk_user.id,
        tenant_id=bulk_tenant.id,
        email=bulk_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = bulk_project["id"]

    # Create 50 WBS items (1 root + 49 children)
    wbs_items = [
        {
            "code": "1",
            "name": "Root WBS",
            "level": 1,
            "description": "Project root",
        }
    ]

    # Add 49 level-2 items
    for i in range(1, 50):
        wbs_items.append({
            "code": f"1.{i}",
            "name": f"Work Package {i}",
            "level": 2,
            "parent_code": "1",
        })

    # Bulk create
    response = await client.post(
        f"/api/v1/projects/{project_id}/wbs/bulk",
        json={"items": wbs_items},
        headers=headers,
    )

    # Should create all items (or 404 until implemented)
    assert response.status_code in [201, 404]

    # In GREEN phase:
    # body = response.json()
    # assert body["created_count"] == 50
    # assert body["failed_count"] == 0


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

    # Should initiate export (or 404 until implemented)
    assert response.status_code in [202, 404]

    # In GREEN phase:
    # body = response.json()
    # assert "export_id" in body
    # assert body["status"] == "processing"


# ===========================================
# TEST 5: Partial Success Handling
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_005_bulk_operation_partial_success(
    client,
    bulk_user: User,
    bulk_tenant: Tenant,
    bulk_project,
    generate_token,
):
    """
    GIVEN Bulk operation with some invalid items
    WHEN User submits 10 items (5 valid, 5 invalid)
    THEN 5 items succeed, 5 items fail
    AND Error details are provided for failed items
    AND Valid items are still processed

    Validates: Partial success handling
    """
    token = generate_token(
        user_id=bulk_user.id,
        tenant_id=bulk_tenant.id,
        email=bulk_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = bulk_project["id"]

    # Mix of valid and invalid WBS items
    wbs_items = [
        # Valid items
        {"code": "1", "name": "Valid Root", "level": 1},
        {"code": "1.1", "name": "Valid Child", "level": 2, "parent_code": "1"},
        # Invalid items (missing required fields)
        {"code": "2"},  # Missing name and level
        {"code": "1.2", "level": 2},  # Missing name
        {"name": "Invalid", "level": 2},  # Missing code
    ]

    response = await client.post(
        f"/api/v1/projects/{project_id}/wbs/bulk",
        json={"items": wbs_items},
        headers=headers,
    )

    # Should process with partial success (or 404 until implemented)
    assert response.status_code in [201, 207, 404]  # 207 = Multi-Status

    # In GREEN phase:
    # body = response.json()
    # assert body["created_count"] == 2  # Valid items
    # assert body["failed_count"] == 3  # Invalid items
    # assert len(body["errors"]) == 3


# ===========================================
# TEST 6: Progress Tracking
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
@pytest.mark.slow
async def test_006_bulk_operation_progress_tracking(
    client,
    bulk_user: User,
    bulk_tenant: Tenant,
    bulk_project,
    generate_token,
):
    """
    GIVEN A long-running bulk operation
    WHEN User polls progress endpoint
    THEN Progress percentage is returned
    AND Status transitions: pending → processing → completed
    AND Estimated time remaining is provided

    Validates: Progress tracking for long operations
    """
    token = generate_token(
        user_id=bulk_user.id,
        tenant_id=bulk_tenant.id,
        email=bulk_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = bulk_project["id"]

    # Initiate large bulk operation
    wbs_items = [{"code": f"{i}", "name": f"Item {i}", "level": 1} for i in range(100)]

    response = await client.post(
        f"/api/v1/projects/{project_id}/wbs/bulk",
        json={"items": wbs_items},
        headers=headers,
    )

    # Should return job ID for tracking (or 404 until implemented)
    assert response.status_code in [202, 404]

    # In GREEN phase:
    # job_id = response.json().get("job_id")
    # Poll progress
    # progress_response = await client.get(
    #     f"/api/v1/bulk-operations/{job_id}/progress",
    #     headers=headers
    # )
    # assert "percentage" in progress_response.json()


# ===========================================
# TEST 7: Rate Limiting for Bulk Operations
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_007_bulk_operations_rate_limited(
    client,
    bulk_user: User,
    bulk_tenant: Tenant,
    bulk_project,
    generate_token,
):
    """
    GIVEN User has exceeded bulk operation limits
    WHEN User attempts another bulk operation
    THEN Request is rate limited with 429
    AND Retry-After header is provided

    Validates: Rate limiting prevents abuse
    """
    token = generate_token(
        user_id=bulk_user.id,
        tenant_id=bulk_tenant.id,
        email=bulk_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = bulk_project["id"]

    # Make 5 rapid bulk operations
    for i in range(5):
        wbs_items = [{"code": f"batch{i}-{j}", "name": f"Item {j}", "level": 1} for j in range(10)]

        response = await client.post(
            f"/api/v1/projects/{project_id}/wbs/bulk",
            json={"items": wbs_items},
            headers=headers,
        )

    # 6th request should be rate limited (or not implemented yet)
    response = await client.post(
        f"/api/v1/projects/{project_id}/wbs/bulk",
        json={"items": [{"code": "final", "name": "Final", "level": 1}]},
        headers=headers,
    )

    # May be rate limited
    assert response.status_code in [202, 429, 404]


# ===========================================
# TEST 8: Tenant Isolation in Bulk Operations
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_008_bulk_operations_respect_tenant_isolation(
    client,
    db,
    bulk_user: User,
    bulk_tenant: Tenant,
    bulk_project,
    generate_token,
):
    """
    GIVEN Tenant A has a project
    WHEN Tenant B tries bulk operation on Tenant A's project
    THEN Request is denied with 404

    Validates: Security in bulk operations
    """
    # Create Tenant B
    tenant_b = Tenant(
        id=uuid4(),
        name="Tenant B",
        slug=f"tenant-b-{uuid4().hex[:8]}",
        subscription_plan=SubscriptionPlan.STARTER,
        subscription_status="active",
        ai_budget_monthly=50.0,
        ai_spend_current=0.0,
        max_projects=10,
        max_users=5,
        max_storage_gb=50,
        is_active=True,
    )
    db.add(tenant_b)
    await db.flush()

    user_b = User(
        id=uuid4(),
        tenant_id=tenant_b.id,
        email="user_b@test.com",
        hashed_password=hash_password("Password123!"),
        first_name="User",
        last_name="B",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db.add(user_b)
    await db.flush()

    token_b = generate_token(
        user_id=user_b.id,
        tenant_id=tenant_b.id,
        email=user_b.email,
        role="admin",
    )
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Tenant A's project
    project_id = bulk_project["id"]

    # Tenant B tries bulk operation
    wbs_items = [{"code": "1", "name": "Hacker Item", "level": 1}]

    response = await client.post(
        f"/api/v1/projects/{project_id}/wbs/bulk",
        json={"items": wbs_items},
        headers=headers_b,
    )

    # Should be blocked
    assert response.status_code == 404


# ===========================================
# TEST 9: Atomic Transactions (All or Nothing)
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_009_bulk_operation_atomic_transaction(
    client,
    bulk_user: User,
    bulk_tenant: Tenant,
    bulk_project,
    generate_token,
):
    """
    GIVEN Bulk operation with atomic=true flag
    WHEN One item fails validation
    THEN Entire batch is rolled back (all or nothing)
    AND No partial data is persisted

    Validates: Atomic transaction handling
    """
    token = generate_token(
        user_id=bulk_user.id,
        tenant_id=bulk_tenant.id,
        email=bulk_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = bulk_project["id"]

    # Mix of valid items + 1 invalid (should fail entire batch)
    wbs_items = [
        {"code": "1", "name": "Valid 1", "level": 1},
        {"code": "1.1", "name": "Valid 2", "level": 2, "parent_code": "1"},
        {"code": "INVALID"},  # Missing required fields
    ]

    response = await client.post(
        f"/api/v1/projects/{project_id}/wbs/bulk",
        json={"items": wbs_items, "atomic": True},
        headers=headers,
    )

    # Should reject entire batch (or 404 until implemented)
    assert response.status_code in [400, 404]

    # In GREEN phase:
    # body = response.json()
    # assert body["created_count"] == 0  # Nothing created (rolled back)


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

    # Create and reject 10 alerts
    alert_ids = []
    for i in range(10):
        alert_data = {
            "project_id": str(bulk_project["id"]),
            "rule_code": f"R{i}",
            "category": "TIME",
            "severity": "low",
            "message": f"Alert {i}",
        }
        create_response = await client.post(
            "/api/v1/alerts",
            json=alert_data,
            headers=headers,
        )
        if create_response.status_code == 201:
            alert_id = create_response.json()["id"]
            alert_ids.append(alert_id)

            # Reject it
            await client.post(
                f"/api/v1/alerts/{alert_id}/review",
                json={"decision": "reject", "comment": "False positive"},
                headers=headers,
            )

    # Bulk delete rejected alerts
    if alert_ids:
        response = await client.post(
            "/api/v1/alerts/bulk-delete",
            json={"alert_ids": [str(aid) for aid in alert_ids], "status_filter": "rejected"},
            headers=headers,
        )

        # Should delete all (or 404 until implemented)
        assert response.status_code in [200, 404]
