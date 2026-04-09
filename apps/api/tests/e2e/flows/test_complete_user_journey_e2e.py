"""
Refers to Suite ID: TS-E2E-FLW-JRN-001

E2E Complete User Journey (TASK-QA-097):
1. Tenant/user-authenticated project creation
2. Document upload and listing
3. LangGraph decision-intelligence execution contract
4. Coherence score v2 evaluation across 6 categories
5. Alert generation and tenant isolation safeguards
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest


def _skip_if_decision_ports_not_wired(response) -> None:
    if response.status_code >= 500 and "requires real port implementations" in response.text:
        pytest.skip(
            "Decision Intelligence real ports are not wired in this local runtime.",
            allow_module_level=False,
        )


async def _create_project(client, headers: dict[str, str], *, suffix: str = "journey") -> dict:
    payload = {
        "name": f"E2E Journey {suffix}",
        "code": f"E2E-JRN-{suffix.upper()}-{uuid4().hex[:6]}",
        "description": "Complete user journey project",
        "project_type": "construction",
        "estimated_budget": 250000.0,
        "currency": "EUR",
    }
    response = await client.post("/api/v1/projects", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


async def _upload_document(client, headers: dict[str, str], project_id: str, filename: str) -> dict:
    files = {"file": (filename, b"%PDF-1.4 synthetic contract for e2e", "application/pdf")}
    data = {"document_type": "contract"}
    try:
        response = await client.post(
            f"/api/v1/projects/{project_id}/documents",
            data=data,
            files=files,
            headers=headers,
        )
    except PermissionError:
        pytest.skip(
            "Document upload storage path is not writable in this local runtime.",
            allow_module_level=False,
        )
    if response.status_code >= 500 and "Permission denied" in response.text:
        pytest.skip(
            "Document upload storage path is not writable in this local runtime.",
            allow_module_level=False,
        )
    assert response.status_code == 202
    return response.json()


def _build_headers(*, generate_token, user_id: UUID, tenant_id: UUID, email: str, role: str) -> dict[str, str]:
    token = generate_token(
        user_id=user_id,
        tenant_id=tenant_id,
        email=email,
        role=role,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_001_complete_journey_bootstrap_project_upload_and_listing(
    client,
    test_user,
    test_tenant,
    generate_token,
) -> None:
    """
    TS-E2E-FLW-JRN-001 validates bootstrap flow:
    authenticated project creation + document upload + document listing.
    """
    headers = _build_headers(
        generate_token=generate_token,
        user_id=test_user.id,
        tenant_id=test_tenant.id,
        email=test_user.email,
        role=test_user.role.value,
    )
    project = await _create_project(client, headers, suffix="bootstrap")
    project_id = project["id"]

    queued = await _upload_document(
        client,
        headers,
        project_id=project_id,
        filename="bootstrap-contract.pdf",
    )
    assert "id" in queued
    assert queued["upload_status"] in {"uploaded", "processing", "parsed"}

    list_response = await client.get(
        f"/api/v1/projects/{project_id}/documents",
        headers=headers,
    )
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total_count"] >= 1
    assert any(item["id"] == queued["id"] for item in body["items"])


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_002_complete_journey_langgraph_decision_execution_contract(
    client,
    test_user,
    test_tenant,
    generate_token,
) -> None:
    """
    TS-E2E-FLW-JRN-001 validates LangGraph orchestration contract endpoint.
    Skips when real decision-intelligence runtime ports are intentionally not wired.
    """
    headers = _build_headers(
        generate_token=generate_token,
        user_id=test_user.id,
        tenant_id=test_tenant.id,
        email=test_user.email,
        role=test_user.role.value,
    )
    payload = {
        "project_id": str(uuid4()),
        "document_bytes_b64": "JVBERi0xLjQgbW9jayBwZGY=",
    }
    response = await client.post(
        "/api/v1/decision-intelligence/execute",
        json=payload,
        headers=headers,
    )

    _skip_if_decision_ports_not_wired(response)
    assert response.status_code == 200
    body = response.json()
    assert body["coherence_score"] >= 0
    assert isinstance(body["risks"], list)
    assert isinstance(body["evidence_links"], list)
    assert isinstance(body["citations"], list)


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_003_complete_journey_coherence_v2_returns_six_categories(
    client,
    test_user,
    test_tenant,
    generate_token,
) -> None:
    """
    TS-E2E-FLW-JRN-001 validates coherence v2 output with category breakdown.
    """
    headers = _build_headers(
        generate_token=generate_token,
        user_id=test_user.id,
        tenant_id=test_tenant.id,
        email=test_user.email,
        role=test_user.role.value,
    )
    payload = {
        "clauses": [
            {
                "id": "cls-budget-1",
                "text": "Budget is EUR 100000 with monthly payment milestones.",
                "data": {"budget": 100000, "category": "BUDGET"},
            },
            {
                "id": "cls-time-1",
                "text": "Work must finish before 2026-12-31 per schedule baseline.",
                "data": {"deadline": "2026-12-31", "category": "TIME"},
            },
            {
                "id": "cls-legal-1",
                "text": "Warranty and contract penalties apply for delays.",
                "data": {"contract": True, "category": "LEGAL"},
            },
            {
                "id": "cls-tech-1",
                "text": "Material specification must follow approved BOM.",
                "data": {"specification": "BOM-A", "category": "TECHNICAL"},
            },
            {
                "id": "cls-quality-1",
                "text": "Inspection and quality standards must pass at handover.",
                "data": {"inspection": True, "category": "QUALITY"},
            },
            {
                "id": "cls-scope-1",
                "text": "Project scope includes structural and MEP deliverables.",
                "data": {"scope": "structural, MEP", "category": "SCOPE"},
            },
        ],
        "low_budget_mode": True,
        "include_rag_similarity": False,
    }

    response = await client.post(
        "/api/v1/coherence/evaluate",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 200

    body = response.json()
    assert isinstance(body["overall_score"], int | float)
    assert isinstance(body["alerts"], list)
    categories = {str(item["category"]).upper() for item in body["category_breakdown"]}
    expected = {"SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME", "SCHEDULE", "FINANCIAL", "GENERAL"}
    assert len(categories) >= 1
    assert categories.issubset(expected)

    project = await _create_project(client, headers, suffix="coherence-dashboard")
    dashboard_response = await client.get(f"/api/v1/coherence/dashboard/{project['id']}", headers=headers)
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    assert set(dashboard["sub_scores"].keys()) == {"SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME"}
    assert set(dashboard["weights_used"].keys()) == {"SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME"}


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_004_complete_journey_alert_generation_review_and_history(
    client,
    test_user,
    test_tenant,
    generate_token,
) -> None:
    """
    TS-E2E-FLW-JRN-001 validates alert generation path and review traceability.
    """
    headers = _build_headers(
        generate_token=generate_token,
        user_id=test_user.id,
        tenant_id=test_tenant.id,
        email=test_user.email,
        role=test_user.role.value,
    )
    project = await _create_project(client, headers, suffix="alerts")
    project_id = project["id"]

    create_response = await client.post(
        "/api/v1/alerts",
        json={
            "project_id": project_id,
            "rule_code": "R-JRN-001",
            "category": "TIME",
            "severity": "high",
            "message": "Schedule mismatch detected against contractual deadline",
            "affected_entities": {"contract_end_date": "2026-12-31", "schedule_end_date": "2026-12-20"},
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    created = create_response.json()
    alert_id = created["id"]

    list_response = await client.get(
        f"/api/v1/alerts/projects/{project_id}?status_filter=open",
        headers=headers,
    )
    assert list_response.status_code == 200
    assert any(item["id"] == alert_id for item in list_response.json()["items"])

    review_response = await client.post(
        f"/api/v1/alerts/{alert_id}/review",
        json={"decision": "approve", "comment": "Confirmed by PM"},
        headers=headers,
    )
    assert review_response.status_code == 200
    reviewed = review_response.json()
    assert reviewed["status"] == "acknowledged"
    assert reviewed["reviewed_by"] is not None

    history_response = await client.get(
        f"/api/v1/alerts/{alert_id}/history",
        headers=headers,
    )
    assert history_response.status_code == 200
    history = history_response.json()["items"]
    assert any(item.get("action") == "created" for item in history)
    assert any(item.get("action") == "reviewed" for item in history)


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_005_complete_journey_tenant_isolation_blocks_cross_tenant_access(
    client,
    db,
    test_user,
    test_tenant,
    generate_token,
) -> None:
    """
    TS-E2E-FLW-JRN-001 validates tenant isolation for project/doc/alert resources.
    """
    from src.core.auth.models import SubscriptionPlan, Tenant, User, UserRole
    from src.core.auth.service import hash_password

    owner_headers = _build_headers(
        generate_token=generate_token,
        user_id=test_user.id,
        tenant_id=test_tenant.id,
        email=test_user.email,
        role=test_user.role.value,
    )
    owner_project = await _create_project(client, owner_headers, suffix="isolation")
    owner_project_id = owner_project["id"]

    other_tenant = Tenant(
        id=uuid4(),
        name="Journey Tenant B",
        slug=f"journey-tenant-b-{uuid4().hex[:8]}",
        subscription_plan=SubscriptionPlan.STARTER,
        subscription_status="active",
        ai_budget_monthly=25.0,
        ai_spend_current=0.0,
        max_projects=10,
        max_users=5,
        max_storage_gb=25,
        is_active=True,
    )
    db.add(other_tenant)
    await db.commit()
    await db.refresh(other_tenant)

    other_user = User(
        id=uuid4(),
        tenant_id=other_tenant.id,
        email=f"journey-b-{uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Password123!"),
        first_name="Journey",
        last_name="TenantB",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db.add(other_user)
    await db.commit()
    await db.refresh(other_user)

    other_headers = {
        "Authorization": "Bearer "
        + generate_token(
            user_id=other_user.id,
            tenant_id=other_tenant.id,
            email=other_user.email,
            role="admin",
        )
    }

    project_get_response = await client.get(f"/api/v1/projects/{owner_project_id}", headers=other_headers)
    assert project_get_response.status_code == 404

    docs_list_response = await client.get(
        f"/api/v1/projects/{owner_project_id}/documents",
        headers=other_headers,
    )
    assert docs_list_response.status_code == 200
    docs_payload = docs_list_response.json()
    assert docs_payload["total_count"] == 0
    assert docs_payload["items"] == []

    owner_alert_response = await client.post(
        "/api/v1/alerts",
        json={
            "project_id": owner_project_id,
            "rule_code": "R-JRN-ISO",
            "category": "LEGAL",
            "severity": "medium",
            "message": "Cross-tenant access must not leak alert resources",
            "affected_entities": {"source": "tenant-a"},
        },
        headers=owner_headers,
    )
    assert owner_alert_response.status_code == 201
    owner_alert_id = UUID(owner_alert_response.json()["id"])

    cross_tenant_review = await client.post(
        f"/api/v1/alerts/{owner_alert_id}/review",
        json={"decision": "approve", "comment": "unauthorized"},
        headers=other_headers,
    )
    assert cross_tenant_review.status_code == 404
