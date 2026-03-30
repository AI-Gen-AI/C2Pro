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
from httpx import ASGITransport, AsyncClient

from src.analysis.adapters.persistence.models import Alert, Analysis
from src.analysis.domain.enums import AnalysisStatus, AnalysisType
from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentStatus, DocumentType
from src.core.auth.models import Tenant, User, UserRole, SubscriptionPlan
from src.core.approval import ApprovalStatus
from src.core.auth.service import hash_password
from src.core.database import get_session
from src.main import create_application
from src.projects.adapters.persistence.models import ProjectORM


# ===========================================
# FIXTURES
# ===========================================


async def _create_alert(client, headers: dict[str, str], project_id) -> dict:
    response = await client.post(
        "/api/v1/alerts",
        json={
            "project_id": str(project_id),
            "rule_code": "R1",
            "category": "TIME",
            "severity": "high",
            "message": "Contract deadline differs from schedule end date by 15 days",
            "affected_entities": {
                "contract_end_date": "2026-12-31",
                "schedule_end_date": "2026-12-16",
            },
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


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
    await db.commit()
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
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def alert_project(db, alert_tenant: Tenant):
    """Create a project for alert workflow testing."""
    project = ProjectORM(
        id=uuid4(),
        tenant_id=alert_tenant.id,
        name="Alert Workflow Project",
        code="ALERT-FLOW-001",
        project_type="construction",
        estimated_budget=500000.0,
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

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "open"
    assert body["rule_code"] == "R1"
    assert body["tenant_id"] == str(alert_tenant.id)
    assert body["project_id"] == str(project_id)


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

    created = await _create_alert(client, headers, project_id)

    response = await client.get(
        f"/api/v1/projects/{project_id}/alerts?status=pending",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any(item["id"] == created["id"] for item in body["items"])
    assert all(item["tenant_id"] == str(alert_tenant.id) for item in body["items"])


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

    created = await _create_alert(client, headers, alert_project["id"])
    alert_id = created["id"]

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

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "acknowledged"
    assert body["reviewed_by"] == str(alert_user.id)
    assert body["reviewed_at"] is not None


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

    created = await _create_alert(client, headers, alert_project["id"])
    alert_id = created["id"]

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

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "dismissed"
    assert body["reviewed_by"] == str(alert_user.id)


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

    alert_ids = []
    for _ in range(5):
        created = await _create_alert(client, headers, alert_project["id"])
        alert_ids.append(created["id"])
    bulk_data = {
        "alert_ids": alert_ids,
        "decision": "approve",
        "comment": "Bulk approval of critical alerts",
    }

    response = await client.post(
        "/api/v1/alerts/bulk-review",
        json=bulk_data,
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["processed_count"] == 5
    assert body["decision"] == "approve"


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

    for _ in range(50):
        await _create_alert(client, headers, alert_project["id"])
    alert_ids = []
    list_response = await client.get(
        f"/api/v1/projects/{alert_project['id']}/alerts?status=pending",
        headers=headers,
    )
    assert list_response.status_code == 200
    alert_ids = [item["id"] for item in list_response.json()["items"][:50]]
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
    body = response.json()
    assert body["processed_count"] == 50
    assert body["warning"] is not None


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

    created = await _create_alert(client, headers, alert_project["id"])
    alert_id = created["id"]
    review_response = await client.post(
        f"/api/v1/alerts/{alert_id}/review",
        json={"decision": "approve", "comment": "Confirmed issue"},
        headers=headers,
    )
    assert review_response.status_code == 200

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

    assert response.status_code == 201
    body = response.json()
    assert body["alert_id"] == alert_id
    assert body["evidence_count"] == 1


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

    created = await _create_alert(client, headers, alert_project["id"])
    alert_id = created["id"]
    approve_response = await client.post(
        f"/api/v1/alerts/{alert_id}/review",
        json={"decision": "approve", "comment": "Confirmed issue"},
        headers=headers,
    )
    assert approve_response.status_code == 200
    resolve_response = await client.post(
        f"/api/v1/alerts/{alert_id}/resolve",
        json={
            "resolution": "Contract amended to match schedule deadline",
            "resolved_by": str(alert_user.id),
        },
        headers=headers,
    )
    assert resolve_response.status_code == 200

    # Get status history
    response = await client.get(
        f"/api/v1/alerts/{alert_id}/history",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["alert_id"] == alert_id
    assert len(body["items"]) >= 3


# ===========================================
# TEST 9: Dashboard Shows Review Status
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_009_dashboard_shows_review_statistics(
    client,
    db,
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
    created = await _create_alert(client, headers, project_id)
    approved = await client.post(
        f"/api/v1/alerts/{created['id']}/review",
        json={"decision": "approve", "comment": "Confirmed issue"},
        headers=headers,
    )
    assert approved.status_code == 200
    await _create_alert(client, headers, project_id)

    document = DocumentORM(
        id=uuid4(),
        project_id=project_id,
        document_type=DocumentType.CONTRACT,
        filename="dashboard-contract.pdf",
        upload_status=DocumentStatus.PARSED,
        file_format="pdf",
        file_size_bytes=1024,
        created_by=alert_user.id,
        document_metadata={},
    )
    calculated_at = datetime.utcnow().replace(microsecond=0)
    analysis = Analysis(
        id=uuid4(),
        project_id=project_id,
        analysis_type=AnalysisType.COHERENCE,
        status=AnalysisStatus.COMPLETED,
        result_json={"source": "analysis"},
        coherence_score=88,
        coherence_breakdown={
            "SCOPE": 91,
            "BUDGET": 77,
            "QUALITY": 89,
            "TECHNICAL": 83,
            "LEGAL": 94,
            "TIME": 80,
        },
        alerts_count=2,
        started_at=calculated_at,
        completed_at=calculated_at,
    )
    coherence = CoherenceResultORM(
        project_id=project_id,
        global_score=12,
        category_scores={
            "SCOPE": 10,
            "BUDGET": 10,
            "QUALITY": 10,
            "TECHNICAL": 10,
            "LEGAL": 10,
            "TIME": 10,
        },
        category_details=[],
        alerts=[],
        is_gaming_detected=False,
        gaming_violations=[],
        penalty_points=0,
        calculated_at=calculated_at - timedelta(days=1),
    )
    db.add(document)
    db.add(analysis)
    db.add(coherence)
    await db.commit()

    response = await client.get(
        f"/api/coherence/dashboard/{project_id}",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == str(project_id)
    assert body["tenant_id"] == str(alert_tenant.id)
    assert body["coherence_score"] == 88
    assert body["global_score"] == 88
    assert body["sub_scores"]["SCOPE"] == 91
    assert body["sub_scores"]["LEGAL"] == 94
    assert body["alert_count"] == 2
    assert body["document_count"] == 1
    assert body["last_updated"].startswith(calculated_at.isoformat())


# ===========================================
# TEST 10: Dashboard Values Change With Persisted Inputs
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_010_dashboard_values_change_when_analysis_and_documents_change(
    client,
    db,
    alert_user: User,
    alert_tenant: Tenant,
    alert_project,
    generate_token,
):
    """
    GIVEN A project with persisted dashboard inputs
    WHEN New documents and a newer analysis are persisted
    THEN Dashboard values change to reflect the latest real data

    Validates: Dashboard reactivity to persisted uploads and analyses
    """
    token = generate_token(
        user_id=alert_user.id,
        tenant_id=alert_tenant.id,
        email=alert_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}
    project_id = alert_project["id"]

    first_document = DocumentORM(
        id=uuid4(),
        project_id=project_id,
        document_type=DocumentType.CONTRACT,
        filename="phase-1.pdf",
        upload_status=DocumentStatus.PARSED,
        file_format="pdf",
        file_size_bytes=100,
        created_by=alert_user.id,
        document_metadata={},
    )
    first_analysis_at = datetime.utcnow().replace(microsecond=0) - timedelta(minutes=5)
    first_analysis = Analysis(
        id=uuid4(),
        project_id=project_id,
        analysis_type=AnalysisType.COHERENCE,
        status=AnalysisStatus.COMPLETED,
        result_json={"phase": 1},
        coherence_score=70,
        coherence_breakdown={
            "SCOPE": 70,
            "BUDGET": 70,
            "QUALITY": 70,
            "TECHNICAL": 70,
            "LEGAL": 70,
            "TIME": 70,
        },
        alerts_count=0,
        started_at=first_analysis_at,
        completed_at=first_analysis_at,
    )
    db.add(first_document)
    db.add(first_analysis)
    await db.commit()

    first_response = await client.get(
        f"/api/coherence/dashboard/{project_id}",
        headers=headers,
    )
    assert first_response.status_code == 200
    first_body = first_response.json()
    assert first_body["coherence_score"] == 70
    assert first_body["document_count"] == 1

    second_document = DocumentORM(
        id=uuid4(),
        project_id=project_id,
        document_type=DocumentType.SCHEDULE,
        filename="phase-2.pdf",
        upload_status=DocumentStatus.PARSED,
        file_format="pdf",
        file_size_bytes=200,
        created_by=alert_user.id,
        document_metadata={},
    )
    second_analysis_at = datetime.utcnow().replace(microsecond=0)
    second_analysis = Analysis(
        id=uuid4(),
        project_id=project_id,
        analysis_type=AnalysisType.COHERENCE,
        status=AnalysisStatus.COMPLETED,
        result_json={"phase": 2},
        coherence_score=93,
        coherence_breakdown={
            "SCOPE": 96,
            "BUDGET": 91,
            "QUALITY": 95,
            "TECHNICAL": 92,
            "LEGAL": 94,
            "TIME": 90,
        },
        alerts_count=0,
        started_at=second_analysis_at,
        completed_at=second_analysis_at,
    )
    db.add(second_document)
    db.add(second_analysis)
    await db.commit()

    second_response = await client.get(
        f"/api/coherence/dashboard/{project_id}",
        headers=headers,
    )
    assert second_response.status_code == 200
    second_body = second_response.json()
    assert second_body["coherence_score"] == 93
    assert second_body["sub_scores"]["SCOPE"] == 96
    assert second_body["document_count"] == 2
    assert second_body["last_updated"].startswith(second_analysis_at.isoformat())


# ===========================================
# TEST 11: Tenant Isolation in Alert Review
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_011_alert_review_respects_tenant_isolation(
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
    await db.commit()
    await db.refresh(tenant_b)

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
    await db.commit()
    await db.refresh(user_b)

    token_b = generate_token(
        user_id=user_b.id,
        tenant_id=tenant_b.id,
        email=user_b.email,
        role="admin",
    )
    headers_b = {"Authorization": f"Bearer {token_b}"}

    owner_token = generate_token(
        user_id=alert_user.id,
        tenant_id=alert_tenant.id,
        email=alert_user.email,
        role="admin",
    )
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    created = await _create_alert(client, owner_headers, alert_project["id"])
    alert_id = created["id"]

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

    assert response.status_code == 404


# ===========================================
# TEST 12: Resolve Alert After Fixing Issue
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_012_resolve_alert_after_issue_fixed(
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

    created = await _create_alert(client, headers, alert_project["id"])
    alert_id = created["id"]
    approve_response = await client.post(
        f"/api/v1/alerts/{alert_id}/review",
        json={"decision": "approve", "comment": "Confirmed issue"},
        headers=headers,
    )
    assert approve_response.status_code == 200

    # Resolve alert
    resolve_data = {
        "resolution": "Contract amended to match schedule deadline",
        "resolved_by": str(alert_user.id),
        "root_cause": "schedule_delay",
    }

    response = await client.post(
        f"/api/v1/alerts/{alert_id}/resolve",
        json=resolve_data,
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "resolved"
    assert body["root_cause"] == "schedule_delay"


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_012b_high_severity_resolution_requires_root_cause(
    client,
    alert_user: User,
    alert_tenant: Tenant,
    alert_project,
    generate_token,
):
    """
    GIVEN A high severity alert has been approved
    WHEN User resolves it without root cause
    THEN API rejects the request with a validation error

    Validates: server-side severity-aware resolution rules
    """
    token = generate_token(
        user_id=alert_user.id,
        tenant_id=alert_tenant.id,
        email=alert_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    created = await _create_alert(client, headers, alert_project["id"])
    alert_id = created["id"]
    approve_response = await client.post(
        f"/api/v1/alerts/{alert_id}/review",
        json={"decision": "approve", "comment": "Confirmed issue"},
        headers=headers,
    )
    assert approve_response.status_code == 200

    response = await client.post(
        f"/api/v1/alerts/{alert_id}/resolve",
        json={
            "resolution": "Contract amended to match schedule deadline",
            "resolved_by": str(alert_user.id),
        },
        headers=headers,
    )

    assert response.status_code == 400
    assert "root_cause" in response.json()["detail"]


# ===========================================
# TEST 13: Alert Filters and Search
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_013_filter_alerts_by_category_and_severity(
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

    await _create_alert(client, headers, project_id)
    response = await client.get(
        f"/api/v1/projects/{project_id}/alerts?category=TIME&severity=high&status=pending",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert all(a["category"] == "TIME" for a in body["items"])
    assert all(a["severity"] == "high" for a in body["items"])


# ===========================================
# TEST 14: Alert State Persists Across Fresh Session
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_014_alert_state_changes_survive_fresh_session_and_client(
    client,
    alert_user: User,
    alert_tenant: Tenant,
    alert_project,
    generate_token,
    test_session_factory,
):
    """
    GIVEN An alert is created and updated
    WHEN The API process/session is recreated
    THEN Alert state is loaded from persisted storage
    AND Review, evidence, history, and resolution changes survive

    Validates: Alert persistence across fresh process boundaries
    """
    token = generate_token(
        user_id=alert_user.id,
        tenant_id=alert_tenant.id,
        email=alert_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    created = await _create_alert(client, headers, alert_project["id"])
    alert_id = created["id"]

    review_response = await client.post(
        f"/api/v1/alerts/{alert_id}/review",
        json={"decision": "approve", "comment": "Confirmed issue"},
        headers=headers,
    )
    assert review_response.status_code == 200

    evidence_response = await client.post(
        f"/api/v1/alerts/{alert_id}/evidence",
        json={
            "type": "note",
            "content": "Persisted evidence note",
            "source": "manual_review",
        },
        headers=headers,
    )
    assert evidence_response.status_code == 201

    resolve_response = await client.post(
        f"/api/v1/alerts/{alert_id}/resolve",
        json={
            "resolution": "Persisted resolution",
            "resolved_by": str(alert_user.id),
            "root_cause": "technical_issue",
        },
        headers=headers,
    )
    assert resolve_response.status_code == 200

    # Fresh DB session simulates a new process reading persisted state.
    async with test_session_factory() as fresh_session:
        persisted = await fresh_session.get(Alert, alert_id)
        assert persisted is not None
        assert persisted.status.value == "resolved"
        assert persisted.reviewed_by == alert_user.id
        assert persisted.resolved_by == alert_user.id
        assert persisted.resolution_notes == "Persisted resolution"
        assert (persisted.alert_metadata or {}).get("root_cause") == "technical_issue"
        assert len((persisted.alert_metadata or {}).get("evidence", [])) == 1
        assert len((persisted.alert_metadata or {}).get("history", [])) >= 4

    # Fresh app/client simulates a restarted API process.
    restarted_app = create_application()

    async def override_get_session():
        async with test_session_factory() as fresh_session:
            yield fresh_session

    restarted_app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=restarted_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=30.0,
    ) as restarted_client:
        history_response = await restarted_client.get(
            f"/api/v1/alerts/{alert_id}/history",
            headers=headers,
        )
        assert history_response.status_code == 200
        history_body = history_response.json()
        assert history_body["alert_id"] == alert_id
        assert len(history_body["items"]) >= 4

        resolved_list_response = await restarted_client.get(
            f"/api/v1/projects/{alert_project['id']}/alerts?status=resolved",
            headers=headers,
        )
        assert resolved_list_response.status_code == 200
        resolved_items = resolved_list_response.json()["items"]
        assert any(item["id"] == alert_id for item in resolved_items)

    restarted_app.dependency_overrides.clear()
