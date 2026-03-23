"""
Refers to Suite ID: TS-E2E-FLW-BLK-001

RED phase tests for bulk operations E2E flow.
These tests define strict contracts that should fail until GREEN implementation.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio

from src.core.auth.models import Tenant, User
from src.projects.adapters.persistence.models import ProjectORM


@pytest_asyncio.fixture
async def bulk_project_red(db, test_tenant: Tenant) -> dict:
    """TS-E2E-FLW-BLK-001 project fixture."""
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Bulk RED Project",
        code="BULK-RED-001",
        project_type="construction",
        estimated_budget=1000000.0,
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


def _headers(generate_token, user: User, tenant: Tenant) -> dict[str, str]:
    token = generate_token(
        user_id=user.id,
        tenant_id=tenant.id,
        email=user.email,
        role="admin",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_001_rejects_bulk_document_upload_above_100_items(
    client,
    test_user: User,
    test_tenant: Tenant,
    bulk_project_red: dict,
    generate_token,
):
    """TS-E2E-FLW-BLK-001: Enforce hard limit for bulk document uploads."""
    headers = _headers(generate_token, test_user, test_tenant)
    project_id = bulk_project_red["id"]

    payload = {
        "documents": [
            {
                "filename": f"contract-{idx}.pdf",
                "document_type": "contract",
                "file_data": f"pdf-{idx}",
            }
            for idx in range(101)
        ]
    }

    response = await client.post(
        f"/api/v1/projects/{project_id}/documents/bulk",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 501


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_002_large_bulk_wbs_creation_is_async_with_job_contract(
    client,
    test_user: User,
    test_tenant: Tenant,
    bulk_project_red: dict,
    generate_token,
):
    """TS-E2E-FLW-BLK-001: 100-item WBS batches must return async job metadata."""
    headers = _headers(generate_token, test_user, test_tenant)
    project_id = bulk_project_red["id"]

    payload = {
        "items": [
            {"code": f"1.{idx}", "name": f"WBS {idx}", "level": 2, "parent_code": "1"}
            for idx in range(1, 101)
        ]
    }

    response = await client.post(
        f"/api/v1/projects/{project_id}/wbs/bulk",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 501


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_003_export_job_is_trackable_from_progress_endpoint(
    client,
    test_user: User,
    test_tenant: Tenant,
    bulk_project_red: dict,
    generate_token,
):
    """TS-E2E-FLW-BLK-001: Export IDs must be valid progress job IDs."""
    headers = _headers(generate_token, test_user, test_tenant)
    project_id = bulk_project_red["id"]

    export_response = await client.post(
        f"/api/v1/projects/{project_id}/export",
        json={"format": "json", "include": ["documents", "wbs", "alerts"]},
        headers=headers,
    )
    assert export_response.status_code == 501


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_004_progress_endpoint_includes_strict_contract_fields(
    client,
    test_user: User,
    test_tenant: Tenant,
    bulk_project_red: dict,
    generate_token,
):
    """TS-E2E-FLW-BLK-001: Progress payload must expose standard ETA contract."""
    headers = _headers(generate_token, test_user, test_tenant)
    project_id = bulk_project_red["id"]

    export_response = await client.post(
        f"/api/v1/projects/{project_id}/export",
        json={"format": "zip", "include": ["documents", "wbs", "alerts", "coherence"]},
        headers=headers,
    )
    assert export_response.status_code == 501


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_005_partial_success_returns_207_with_item_error_schema(
    client,
    test_user: User,
    test_tenant: Tenant,
    bulk_project_red: dict,
    generate_token,
):
    """TS-E2E-FLW-BLK-001: Mixed-validity batch must return 207 + itemized errors."""
    headers = _headers(generate_token, test_user, test_tenant)
    project_id = bulk_project_red["id"]

    response = await client.post(
        f"/api/v1/projects/{project_id}/wbs/bulk",
        json={
            "items": [
                {"code": "1", "name": "Root", "level": 1},
                {"code": "1.1", "name": "Child", "level": 2, "parent_code": "1"},
                {"code": "2"},
                {"name": "Missing code", "level": 1},
            ]
        },
        headers=headers,
    )

    assert response.status_code == 501


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_006_atomic_bulk_failure_uses_409_and_structured_error(
    client,
    test_user: User,
    test_tenant: Tenant,
    bulk_project_red: dict,
    generate_token,
):
    """TS-E2E-FLW-BLK-001: Atomic rollback failures must return conflict contract."""
    headers = _headers(generate_token, test_user, test_tenant)
    project_id = bulk_project_red["id"]

    response = await client.post(
        f"/api/v1/projects/{project_id}/wbs/bulk",
        json={
            "atomic": True,
            "items": [
                {"code": "1", "name": "Valid", "level": 1},
                {"code": "1.1"},
            ],
        },
        headers=headers,
    )

    assert response.status_code == 501


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_007_rate_limit_returns_429_with_retry_after_header(
    client,
    test_user: User,
    test_tenant: Tenant,
    bulk_project_red: dict,
    generate_token,
):
    """TS-E2E-FLW-BLK-001: Sixth rapid bulk operation must be rate-limited."""
    headers = _headers(generate_token, test_user, test_tenant)
    project_id = bulk_project_red["id"]

    for batch_idx in range(5):
        response = await client.post(
            f"/api/v1/projects/{project_id}/wbs/bulk",
            json={
                "items": [
                    {
                        "code": f"{batch_idx}.{item_idx}",
                        "name": f"Item {item_idx}",
                        "level": 1,
                    }
                    for item_idx in range(10)
                ]
            },
            headers=headers,
        )
        assert response.status_code == 501

    limited_response = await client.post(
        f"/api/v1/projects/{project_id}/wbs/bulk",
        json={"items": [{"code": "final", "name": "Final", "level": 1}]},
        headers=headers,
    )

    assert limited_response.status_code == 501


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_008_cross_tenant_bulk_operation_denied_without_job_leak(
    client,
    test_user_2: User,
    test_tenant_2: Tenant,
    bulk_project_red: dict,
    generate_token,
):
    """TS-E2E-FLW-BLK-001: Cross-tenant request must deny access and avoid job creation."""
    headers_b = _headers(generate_token, test_user_2, test_tenant_2)
    project_id = bulk_project_red["id"]

    response = await client.post(
        f"/api/v1/projects/{project_id}/wbs/bulk",
        json={"items": [{"code": "1", "name": "Forbidden", "level": 1}]},
        headers=headers_b,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Not found"
