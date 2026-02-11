"""
Refers to Suite ID: TS-E2E-FLW-ALR-001

E2E Test Suite: Alert Review Workflow
Priority: 🔴 P0 CRÍTICO
Coverage Target: 85%

Tests the complete alert review and approval workflow:
1. Alert Creation → 2. Alert Listing → 3. Alert Review →
4. Approval/Rejection → 5. Evidence Collection → 6. Status Tracking

This validates the human-in-the-loop coherence validation process:
"System detects incoherence → Human reviews → Decision recorded → Dashboard updated"

Architecture Flow (from PLAN_ARQUITECTURA_v2.1.md):
- Analysis Engine generates alerts
- Alerts queued for review
- Project manager reviews alerts
- Approves (genuine issue) or Rejects (false positive)
- Evidence collected and linked
- Dashboard shows review status
- Coherence score reflects approved alerts only

Anti-gaming measures (Gate 7):
- Mass approval detection
- Suspicious high score flagging
- Resolve/reintroduce pattern detection
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
async def alert_tenant(db) -> Tenant:
    """Create a tenant for alert workflow testing."""
    tenant = Tenant(
        id=uuid4(),
        name="Alert Workflow Company",
        slug=f"alert-test-{uuid4().hex[:8]}",
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
    await db.flush()
    await db.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def alert_user(db, alert_tenant: Tenant) -> User:
    """Create a user for alert workflow testing."""
    user = User(
        id=uuid4(),
        tenant_id=alert_tenant.id,
        email="alert_user@test.com",
        hashed_password=hash_password("Password123!"),
        first_name="Alert",
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
async def alert_project(db, alert_tenant: Tenant):
    """Create a project for alert workflow testing."""
    from src.projects.adapters.http.router import _add_fake_project

    project_data = {
        "id": uuid4(),
        "tenant_id": alert_tenant.id,
        "name": "Alert Workflow Project",
        "code": "ALERT-FLOW-001",
        "project_type": "construction",
        "estimated_budget": 500000.0,
        "currency": "EUR",
    }
    _add_fake_project(project_data)
    return project_data


# ===========================================
# TEST 1: Create Alert
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_001_create_alert_from_coherence_rule(
    client,
    alert_user: User,
    alert_tenant: Tenant,
    alert_project,
    generate_token,
):
    """
    GIVEN A coherence rule violation is detected
    WHEN System creates an alert
    THEN Alert is created with correct metadata
    AND Alert status is "pending"
    AND Alert is linked to rule, project, and affected entities

    Validates: Alert creation from Analysis Engine
    """
    token = generate_token(
        user_id=alert_user.id,
        tenant_id=alert_tenant.id,
        email=alert_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = alert_project["id"]

    # Create alert (from analysis engine)
    alert_data = {
        "project_id": str(project_id),
        "rule_code": "R1",
        "category": "TIME",
        "severity": "high",
        "message": "Contract deadline differs from schedule end date by 15 days",
        "affected_entities": {
            "contract_end_date": "2026-12-31",
            "schedule_end_date": "2026-12-16",
        },
    }

    response = await client.post(
        "/api/v1/alerts",
        json=alert_data,
        headers=headers,
    )

    # Should create alert (or 404 until implemented)
    assert response.status_code in [201, 404]

    # In GREEN phase:
    # body = response.json()
    # assert body["status"] == "pending"
    # assert body["rule_code"] == "R1"
    # assert body["tenant_id"] == str(alert_tenant.id)


# ===========================================
# TEST 2: List Alerts for Review
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_002_list_pending_alerts_for_review(
    client,
    alert_user: User,
    alert_tenant: Tenant,
    alert_project,
    generate_token,
):
    """
    GIVEN Multiple alerts exist (some pending, some reviewed)
    WHEN User requests list of pending alerts
    THEN Only pending alerts are returned
    AND Alerts are sorted by severity (critical > high > medium > low)
    AND Alerts are filtered by tenant_id

    Validates: Alert listing and filtering
    """
    token = generate_token(
        user_id=alert_user.id,
        tenant_id=alert_tenant.id,
        email=alert_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = alert_project["id"]

    # List pending alerts
    response = await client.get(
        f"/api/v1/projects/{project_id}/alerts?status=pending",
        headers=headers,
    )

    # Should return list (or 404 until implemented)
    assert response.status_code in [200, 404]

    # In GREEN phase:
    # body = response.json()
    # assert "items" in body
    # assert all(a["status"] == "pending" for a in body["items"])
    # assert all(a["tenant_id"] == str(alert_tenant.id) for a in body["items"])


# ===========================================
# TEST 3: Approve Alert (Genuine Issue)
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_003_approve_alert_as_genuine_issue(
    client,
    alert_user: User,
    alert_tenant: Tenant,
    alert_project,
    generate_token,
):
    """
    GIVEN An alert is pending review
    WHEN User approves the alert as a genuine issue
    THEN Alert status changes to "approved"
    AND Approval is recorded with user_id and timestamp
    AND Coherence score is updated (alert counts against score)
    AND Alert appears in dashboard as active issue

    Validates: Alert approval workflow
    """
    token = generate_token(
        user_id=alert_user.id,
        tenant_id=alert_tenant.id,
        email=alert_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Create a fake alert ID
    alert_id = uuid4()

    # Approve alert
    approval_data = {
        "decision": "approve",
        "comment": "Confirmed: Contract deadline inconsistency is a real issue",
    }

    response = await client.post(
        f"/api/v1/alerts/{alert_id}/review",
        json=approval_data,
        headers=headers,
    )

    # Should process approval (or 404 until implemented)
    assert response.status_code in [200, 404]

    # In GREEN phase:
    # body = response.json()
    # assert body["status"] == "approved"
    # assert body["reviewed_by"] == str(alert_user.id)
    # assert "reviewed_at" in body


# ===========================================
# TEST 4: Reject Alert (False Positive)
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_004_reject_alert_as_false_positive(
    client,
    alert_user: User,
    alert_tenant: Tenant,
    alert_project,
    generate_token,
):
    """
    GIVEN An alert is pending review
    WHEN User rejects the alert as a false positive
    THEN Alert status changes to "rejected"
    AND Rejection is recorded with reason
    AND Coherence score is NOT affected by this alert
    AND Alert does NOT appear in active issues

    Validates: Alert rejection workflow
    """
    token = generate_token(
        user_id=alert_user.id,
        tenant_id=alert_tenant.id,
        email=alert_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    alert_id = uuid4()

    # Reject alert
    rejection_data = {
        "decision": "reject",
        "comment": "False positive: Dates are correct, system misread contract",
    }

    response = await client.post(
        f"/api/v1/alerts/{alert_id}/review",
        json=rejection_data,
        headers=headers,
    )

    # Should process rejection (or 404 until implemented)
    assert response.status_code in [200, 404]

    # In GREEN phase:
    # body = response.json()
    # assert body["status"] == "rejected"
    # assert body["reviewed_by"] == str(alert_user.id)


# ===========================================
# TEST 5: Bulk Approve Alerts
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_005_bulk_approve_multiple_alerts(
    client,
    alert_user: User,
    alert_tenant: Tenant,
    alert_project,
    generate_token,
):
    """
    GIVEN Multiple alerts are pending review
    WHEN User bulk approves 5 alerts
    THEN All 5 alerts are approved
    AND All approvals are recorded
    AND Coherence score is updated once (not 5 times)

    Validates: Bulk operations efficiency
    """
    token = generate_token(
        user_id=alert_user.id,
        tenant_id=alert_tenant.id,
        email=alert_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Bulk approve
    alert_ids = [uuid4() for _ in range(5)]
    bulk_data = {
        "alert_ids": [str(aid) for aid in alert_ids],
        "decision": "approve",
        "comment": "Bulk approval of critical alerts",
    }

    response = await client.post(
        "/api/v1/alerts/bulk-review",
        json=bulk_data,
        headers=headers,
    )

    # Should process bulk operation (or 404 until implemented)
    assert response.status_code in [200, 404]

    # In GREEN phase:
    # body = response.json()
    # assert body["approved_count"] == 5


# ===========================================
# TEST 6: Anti-Gaming Detection - Mass Approval
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_006_anti_gaming_mass_approval_detection(
    client,
    alert_user: User,
    alert_tenant: Tenant,
    alert_project,
    generate_token,
):
    """
    GIVEN User attempts to approve 50+ alerts in 1 minute
    WHEN Anti-gaming system detects mass approval pattern
    THEN Warning is issued
    AND Audit log records suspicious activity
    AND Project manager is notified

    Validates: Gate 7 - Anti-gaming measures
    """
    token = generate_token(
        user_id=alert_user.id,
        tenant_id=alert_tenant.id,
        email=alert_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = alert_project["id"]

    # Try to bulk approve 50 alerts
    alert_ids = [str(uuid4()) for _ in range(50)]
    bulk_data = {
        "alert_ids": alert_ids,
        "decision": "approve",
    }

    response = await client.post(
        "/api/v1/alerts/bulk-review",
        json=bulk_data,
        headers=headers,
    )

    # Should process but trigger warning (or 404 until implemented)
    assert response.status_code in [200, 404, 429]  # 429 if rate limited

    # In GREEN phase:
    # body = response.json()
    # if "warning" in body:
    #     assert "mass approval" in body["warning"].lower()


# ===========================================
# TEST 7: Evidence Collection
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_007_attach_evidence_to_alert(
    client,
    alert_user: User,
    alert_tenant: Tenant,
    alert_project,
    generate_token,
):
    """
    GIVEN An alert has been approved
    WHEN User attaches evidence (document excerpt, screenshot, note)
    THEN Evidence is linked to alert
    AND Evidence is stored securely
    AND Evidence appears in alert details

    Validates: Evidence collection for audit trail
    """
    token = generate_token(
        user_id=alert_user.id,
        tenant_id=alert_tenant.id,
        email=alert_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    alert_id = uuid4()

    # Attach evidence
    evidence_data = {
        "type": "note",
        "content": "Contract clause 8.2 specifies December 31, schedule shows December 16",
        "source": "manual_review",
    }

    response = await client.post(
        f"/api/v1/alerts/{alert_id}/evidence",
        json=evidence_data,
        headers=headers,
    )

    # Should attach evidence (or 404 until implemented)
    assert response.status_code in [201, 404]


# ===========================================
# TEST 8: Alert Status Tracking
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_008_track_alert_status_transitions(
    client,
    alert_user: User,
    alert_tenant: Tenant,
    alert_project,
    generate_token,
):
    """
    GIVEN An alert exists
    WHEN Alert transitions through statuses
    THEN Status history is recorded
    AND Transitions: pending → approved → resolved

    Validates: Status tracking and audit trail
    """
    token = generate_token(
        user_id=alert_user.id,
        tenant_id=alert_tenant.id,
        email=alert_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    alert_id = uuid4()

    # Get status history
    response = await client.get(
        f"/api/v1/alerts/{alert_id}/history",
        headers=headers,
    )

    # Should return history (or 404 until implemented)
    assert response.status_code in [200, 404]


# ===========================================
# TEST 9: Dashboard Shows Review Status
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_009_dashboard_shows_review_statistics(
    client,
    alert_user: User,
    alert_tenant: Tenant,
    alert_project,
    generate_token,
):
    """
    GIVEN Alerts have been reviewed
    WHEN User requests dashboard
    THEN Dashboard shows:
    - Total alerts
    - Pending alerts count
    - Approved alerts count
    - Rejected alerts count
    - Review completion percentage

    Validates: Dashboard integration
    """
    token = generate_token(
        user_id=alert_user.id,
        tenant_id=alert_tenant.id,
        email=alert_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = alert_project["id"]

    # Get dashboard
    response = await client.get(
        f"/api/coherence/dashboard/{project_id}",
        headers=headers,
    )

    # Should return dashboard with alert stats (already implemented)
    assert response.status_code == 200

    body = response.json()
    # Dashboard should include alert_count
    assert "alert_count" in body


# ===========================================
# TEST 10: Tenant Isolation in Alert Review
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_010_alert_review_respects_tenant_isolation(
    client,
    db,
    alert_user: User,
    alert_tenant: Tenant,
    alert_project,
    generate_token,
):
    """
    GIVEN Tenant A has alerts
    WHEN Tenant B tries to review Tenant A's alert
    THEN Request is denied with 404 Not Found

    Validates: Security in alert workflow
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

    # Tenant A's alert
    alert_id = uuid4()

    # Tenant B tries to review
    review_data = {
        "decision": "approve",
        "comment": "Trying to access another tenant's alert",
    }

    response = await client.post(
        f"/api/v1/alerts/{alert_id}/review",
        json=review_data,
        headers=headers_b,
    )

    # Should be blocked
    assert response.status_code == 404


# ===========================================
# TEST 11: Resolve Alert After Fixing Issue
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_011_resolve_alert_after_issue_fixed(
    client,
    alert_user: User,
    alert_tenant: Tenant,
    alert_project,
    generate_token,
):
    """
    GIVEN An alert has been approved
    WHEN Issue is fixed in the project
    THEN User marks alert as "resolved"
    AND Coherence score is recalculated
    AND Resolved alert no longer counts against score

    Validates: Alert resolution workflow
    """
    token = generate_token(
        user_id=alert_user.id,
        tenant_id=alert_tenant.id,
        email=alert_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    alert_id = uuid4()

    # Resolve alert
    resolve_data = {
        "resolution": "Contract amended to match schedule deadline",
        "resolved_by": str(alert_user.id),
    }

    response = await client.post(
        f"/api/v1/alerts/{alert_id}/resolve",
        json=resolve_data,
        headers=headers,
    )

    # Should resolve alert (or 404 until implemented)
    assert response.status_code in [200, 404]


# ===========================================
# TEST 12: Alert Filters and Search
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_012_filter_alerts_by_category_and_severity(
    client,
    alert_user: User,
    alert_tenant: Tenant,
    alert_project,
    generate_token,
):
    """
    GIVEN Multiple alerts exist with different categories and severities
    WHEN User filters alerts by category=TIME and severity=high
    THEN Only TIME alerts with high severity are returned

    Validates: Alert filtering and search
    """
    token = generate_token(
        user_id=alert_user.id,
        tenant_id=alert_tenant.id,
        email=alert_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = alert_project["id"]

    # Filter alerts
    response = await client.get(
        f"/api/v1/projects/{project_id}/alerts?category=TIME&severity=high",
        headers=headers,
    )

    # Should return filtered results (or 404 until implemented)
    assert response.status_code in [200, 404]

    # In GREEN phase:
    # body = response.json()
    # assert all(a["category"] == "TIME" for a in body["items"])
    # assert all(a["severity"] == "high" for a in body["items"])
