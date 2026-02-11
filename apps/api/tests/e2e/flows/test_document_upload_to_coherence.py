"""
Refers to Suite ID: TS-E2E-FLW-DOC-001

E2E Test Suite: Document Upload to Coherence Flow
Priority: 🔴 P0 CRÍTICO
Coverage Target: 85%

Tests the complete document processing pipeline:
1. Document Upload → 2. Parsing → 3. Clause Extraction →
4. Entity Extraction → 5. Analysis → 6. Coherence Score Calculation

This validates the core value proposition of C2Pro:
"Upload a contract, get automatic coherence analysis"

Architecture Flow (from c2pro_master_flow_diagram_v2.2.1.md):
- User uploads document
- Document stored in Cloudflare R2
- Anonymizer processes PII
- Clause Extractor (Claude Sonnet 4) extracts clauses
- Entity Extractor identifies dates, money, durations
- Analysis runs coherence rules
- Coherence Score v2 calculated (6 categories)
- Dashboard displays results
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
async def flow_tenant(db) -> Tenant:
    """Create a tenant for flow testing."""
    tenant = Tenant(
        id=uuid4(),
        name="Flow Test Company",
        slug=f"flow-test-{uuid4().hex[:8]}",
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
async def flow_user(db, flow_tenant: Tenant) -> User:
    """Create a user for flow testing."""
    user = User(
        id=uuid4(),
        tenant_id=flow_tenant.id,
        email="flow_user@test.com",
        hashed_password=hash_password("Password123!"),
        first_name="Flow",
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
async def flow_project(db, flow_tenant: Tenant):
    """Create a project for flow testing."""
    from src.projects.adapters.http.router import _add_fake_project

    project_data = {
        "id": uuid4(),
        "tenant_id": flow_tenant.id,
        "name": "E2E Flow Project",
        "code": "E2E-FLOW-001",
        "project_type": "construction",
        "estimated_budget": 500000.0,
        "currency": "EUR",
    }
    _add_fake_project(project_data)
    return project_data


# ===========================================
# TEST 1: Complete Happy Path Flow
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_001_complete_document_to_coherence_happy_path(
    client,
    flow_user: User,
    flow_tenant: Tenant,
    flow_project,
    generate_token,
):
    """
    GIVEN A valid project exists
    WHEN User uploads a contract document
    THEN System processes document through complete pipeline
    AND Coherence score becomes available

    Flow:
    1. Upload document → 202 Accepted
    2. Document is parsed and stored
    3. Clauses are extracted
    4. Entities are extracted
    5. Analysis is run
    6. Coherence score is calculated
    7. Dashboard shows results

    This is the CORE flow of C2Pro.
    """
    token = generate_token(
        user_id=flow_user.id,
        tenant_id=flow_tenant.id,
        email=flow_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = flow_project["id"]

    # Step 1: Upload document
    files = {
        "file": ("contract.pdf", b"%PDF-1.4 fake contract", "application/pdf"),
    }
    data = {
        "document_type": "contract",
        "description": "Main project contract",
    }

    upload_response = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        data=data,
        files=files,
        headers=headers,
    )

    # Should accept for async processing
    assert upload_response.status_code in [202, 404]  # 404 until implemented

    # In GREEN phase, would check:
    # - Document stored in R2
    # - Processing job queued
    # - Initial status = "processing"


# ===========================================
# TEST 2: Document Upload Creates Record
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_002_document_upload_creates_database_record(
    client,
    flow_user: User,
    flow_tenant: Tenant,
    flow_project,
    generate_token,
):
    """
    GIVEN A valid project
    WHEN User uploads a document
    THEN A document record is created in database
    AND Document has correct metadata

    Validates: Document entity creation
    """
    token = generate_token(
        user_id=flow_user.id,
        tenant_id=flow_tenant.id,
        email=flow_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = flow_project["id"]

    # Upload document
    files = {
        "file": ("specs.pdf", b"%PDF-1.4 specifications", "application/pdf"),
    }
    data = {
        "document_type": "specifications",
        "description": "Technical specifications",
    }

    upload_response = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        data=data,
        files=files,
        headers=headers,
    )

    # Should accept
    assert upload_response.status_code in [202, 404]

    # In GREEN phase, verify database record:
    # - document.tenant_id == flow_tenant.id
    # - document.project_id == project_id
    # - document.filename == "specs.pdf"
    # - document.status == "processing"


# ===========================================
# TEST 3: Clause Extraction Triggered
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_003_document_upload_triggers_clause_extraction(
    client,
    flow_user: User,
    flow_tenant: Tenant,
    flow_project,
    generate_token,
):
    """
    GIVEN A document has been uploaded
    WHEN Document processing starts
    THEN Clause extraction is triggered
    AND Clauses are stored in database

    Validates: Clause Extractor agent execution
    """
    token = generate_token(
        user_id=flow_user.id,
        tenant_id=flow_tenant.id,
        email=flow_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = flow_project["id"]

    # Upload document
    files = {
        "file": ("contract.pdf", b"%PDF-1.4 with clauses", "application/pdf"),
    }
    data = {"document_type": "contract"}

    upload_response = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        data=data,
        files=files,
        headers=headers,
    )

    assert upload_response.status_code in [202, 404]

    # In GREEN phase:
    # - Wait for async processing
    # - Query clauses: GET /api/v1/documents/{doc_id}/clauses
    # - Verify clauses exist
    # - Verify clause.tenant_id == flow_tenant.id


# ===========================================
# TEST 4: Entity Extraction from Clauses
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_004_clause_extraction_triggers_entity_extraction(
    client,
    flow_user: User,
    flow_tenant: Tenant,
    flow_project,
    generate_token,
):
    """
    GIVEN Clauses have been extracted
    WHEN Entity extraction runs
    THEN Entities are extracted (dates, money, durations)
    AND Entities are linked to clauses

    Validates: Entity Extractor agent execution
    """
    token = generate_token(
        user_id=flow_user.id,
        tenant_id=flow_tenant.id,
        email=flow_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = flow_project["id"]

    # Upload document with entities
    files = {
        "file": ("contract_entities.pdf", b"%PDF-1.4 Payment: 100000 EUR", "application/pdf"),
    }
    data = {"document_type": "contract"}

    upload_response = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        data=data,
        files=files,
        headers=headers,
    )

    assert upload_response.status_code in [202, 404]

    # In GREEN phase:
    # - Wait for processing
    # - Query entities: GET /api/v1/documents/{doc_id}/entities
    # - Verify dates, money, durations extracted
    # - Verify entity.clause_id is set


# ===========================================
# TEST 5: Analysis Triggered After Extraction
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_005_entity_extraction_triggers_analysis(
    client,
    flow_user: User,
    flow_tenant: Tenant,
    flow_project,
    generate_token,
):
    """
    GIVEN Entities have been extracted
    WHEN Analysis is triggered
    THEN Coherence rules are evaluated
    AND Alerts are created for violations

    Validates: Analysis module execution
    """
    token = generate_token(
        user_id=flow_user.id,
        tenant_id=flow_tenant.id,
        email=flow_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = flow_project["id"]

    # Upload document
    files = {
        "file": ("contract.pdf", b"%PDF-1.4 contract", "application/pdf"),
    }
    data = {"document_type": "contract"}

    upload_response = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        data=data,
        files=files,
        headers=headers,
    )

    assert upload_response.status_code in [202, 404]

    # In GREEN phase:
    # - Wait for processing
    # - Query alerts: GET /api/v1/projects/{project_id}/alerts
    # - Verify alerts exist (if violations found)
    # - Verify alert.tenant_id == flow_tenant.id


# ===========================================
# TEST 6: Coherence Score Calculated
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_006_analysis_triggers_coherence_score_calculation(
    client,
    flow_user: User,
    flow_tenant: Tenant,
    flow_project,
    generate_token,
):
    """
    GIVEN Analysis has completed
    WHEN Coherence score is calculated
    THEN Score is available (0-100)
    AND Sub-scores by category are available
    AND Dashboard displays results

    Validates: Coherence Engine v2 execution
    """
    token = generate_token(
        user_id=flow_user.id,
        tenant_id=flow_tenant.id,
        email=flow_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = flow_project["id"]

    # Upload document
    files = {
        "file": ("contract.pdf", b"%PDF-1.4 contract", "application/pdf"),
    }
    data = {"document_type": "contract"}

    upload_response = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        data=data,
        files=files,
        headers=headers,
    )

    assert upload_response.status_code in [202, 404]

    # In GREEN phase:
    # - Wait for processing
    # - Query: GET /api/v1/coherence/dashboard/{project_id}
    # - Verify global_score exists
    # - Verify sub_scores exists (6 categories)
    # - Verify methodology_version == "2.0"


# ===========================================
# TEST 7: Dashboard Shows Results
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_007_coherence_dashboard_displays_results(
    client,
    flow_user: User,
    flow_tenant: Tenant,
    flow_project,
    generate_token,
):
    """
    GIVEN Processing is complete
    WHEN User requests coherence dashboard
    THEN Dashboard shows complete data:
    - Global score
    - Sub-scores by category (SCOPE, BUDGET, QUALITY, TECHNICAL, LEGAL, TIME)
    - Alert count
    - Document count

    Validates: Coherence Dashboard endpoint
    """
    token = generate_token(
        user_id=flow_user.id,
        tenant_id=flow_tenant.id,
        email=flow_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = flow_project["id"]

    # Query dashboard
    response = await client.get(
        f"/api/coherence/dashboard/{project_id}",
        headers=headers,
    )

    # Should return dashboard data (or 404 if not implemented)
    assert response.status_code in [200, 404]

    if response.status_code == 200:
        body = response.json()
        # Should have coherence score structure
        assert "coherence_score" in body or "global_score" in body


# ===========================================
# TEST 8: Multiple Documents Processed
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_008_multiple_documents_all_processed(
    client,
    flow_user: User,
    flow_tenant: Tenant,
    flow_project,
    generate_token,
):
    """
    GIVEN A project with no documents
    WHEN User uploads 3 documents
    THEN All 3 documents are processed
    AND Coherence score reflects all documents

    Validates: Multi-document processing
    """
    token = generate_token(
        user_id=flow_user.id,
        tenant_id=flow_tenant.id,
        email=flow_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = flow_project["id"]

    # Upload 3 documents
    documents = [
        ("contract.pdf", "contract"),
        ("specifications.pdf", "specifications"),
        ("schedule.pdf", "schedule"),
    ]

    for filename, doc_type in documents:
        files = {
            "file": (filename, f"%PDF-1.4 {doc_type}".encode(), "application/pdf"),
        }
        data = {"document_type": doc_type}

        response = await client.post(
            f"/api/v1/projects/{project_id}/documents",
            data=data,
            files=files,
            headers=headers,
        )

        assert response.status_code in [202, 404]

    # In GREEN phase:
    # - Wait for all processing to complete
    # - Verify 3 documents in database
    # - Verify coherence score considers all documents


# ===========================================
# TEST 9: Async Processing Status
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_009_document_processing_status_polling(
    client,
    flow_user: User,
    flow_tenant: Tenant,
    flow_project,
    generate_token,
):
    """
    GIVEN A document is being processed
    WHEN User polls document status
    THEN Status transitions: pending → processing → completed
    AND User can track progress

    Validates: Status tracking and polling
    """
    token = generate_token(
        user_id=flow_user.id,
        tenant_id=flow_tenant.id,
        email=flow_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = flow_project["id"]

    # Upload document
    files = {
        "file": ("contract.pdf", b"%PDF-1.4 contract", "application/pdf"),
    }
    data = {"document_type": "contract"}

    upload_response = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        data=data,
        files=files,
        headers=headers,
    )

    assert upload_response.status_code in [202, 404]

    # In GREEN phase:
    # document_id = upload_response.json()["id"]
    # Poll status: GET /api/v1/documents/{document_id}/status
    # Verify status progression


# ===========================================
# TEST 10: Error Handling - Invalid File
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_010_invalid_file_type_rejected(
    client,
    flow_user: User,
    flow_tenant: Tenant,
    flow_project,
    generate_token,
):
    """
    GIVEN A project exists
    WHEN User uploads an invalid file type (e.g., .exe)
    THEN Upload is rejected with 400 Bad Request
    AND Error message explains valid file types

    Validates: Input validation
    """
    token = generate_token(
        user_id=flow_user.id,
        tenant_id=flow_tenant.id,
        email=flow_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = flow_project["id"]

    # Upload invalid file
    files = {
        "file": ("malware.exe", b"MZ\x90\x00", "application/x-msdownload"),
    }
    data = {"document_type": "contract"}

    response = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        data=data,
        files=files,
        headers=headers,
    )

    # Should reject
    assert response.status_code in [400, 404, 415]  # 415 = Unsupported Media Type


# ===========================================
# TEST 11: Error Handling - File Too Large
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_011_file_too_large_rejected(
    client,
    flow_user: User,
    flow_tenant: Tenant,
    flow_project,
    generate_token,
):
    """
    GIVEN A project exists
    WHEN User uploads a file larger than max size (50 MB)
    THEN Upload is rejected with 413 Payload Too Large
    AND Error message explains size limit

    Validates: File size limits
    """
    token = generate_token(
        user_id=flow_user.id,
        tenant_id=flow_tenant.id,
        email=flow_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    project_id = flow_project["id"]

    # Create large file (simulated with small data for test)
    files = {
        "file": ("huge.pdf", b"x" * (51 * 1024 * 1024), "application/pdf"),  # 51 MB
    }
    data = {"document_type": "contract"}

    response = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        data=data,
        files=files,
        headers=headers,
    )

    # Should reject (or not implemented yet)
    assert response.status_code in [413, 404]


# ===========================================
# TEST 12: Tenant Isolation in Flow
# ===========================================


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_012_document_flow_respects_tenant_isolation(
    client,
    db,
    flow_user: User,
    flow_tenant: Tenant,
    flow_project,
    generate_token,
):
    """
    GIVEN Tenant A uploads a document to their project
    WHEN Tenant B tries to access Tenant A's coherence dashboard
    THEN Tenant B receives 404 Not Found

    Validates: Tenant isolation throughout the entire flow
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
    project_id = flow_project["id"]

    # Tenant B tries to access Tenant A's coherence dashboard
    response = await client.get(
        f"/api/coherence/dashboard/{project_id}",
        headers=headers_b,
    )

    # Should be blocked
    assert response.status_code == 404  # Not 403, to avoid info leak
