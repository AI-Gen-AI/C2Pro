"""
Refers to Suite ID: TS-E2E-ERR-CON-001

E2E RED tests for concurrent modification scenarios.
These tests define strict optimistic-locking and conflict contracts.
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
import pytest_asyncio

from src.core.auth.models import Tenant, User


@pytest_asyncio.fixture
async def concurrency_project(test_tenant: Tenant) -> dict:
    """Create fake project for concurrent-modification tests."""
    from src.projects.adapters.http.router import _add_fake_project

    project = {
        "id": uuid4(),
        "tenant_id": test_tenant.id,
        "name": "Concurrent Project",
        "code": "CON-001",
        "project_type": "construction",
        "estimated_budget": 1000000.0,
        "currency": "EUR",
        "version": 1,
    }
    _add_fake_project(project)
    return project


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
async def test_001_concurrent_patch_requires_optimistic_lock_contract(
    client,
    test_user: User,
    test_tenant: Tenant,
    concurrency_project: dict,
    generate_token,
) -> None:
    """TS-E2E-ERR-CON-001: two concurrent updates with same expected_version must conflict."""
    headers = _headers(generate_token, test_user, test_tenant)
    project_id = concurrency_project["id"]

    async def update_a():
        return await client.patch(
            f"/api/v1/projects/{project_id}",
            json={"name": "Update A", "expected_version": 1},
            headers=headers,
        )

    async def update_b():
        return await client.patch(
            f"/api/v1/projects/{project_id}",
            json={"name": "Update B", "expected_version": 1},
            headers=headers,
        )

    response_a, response_b = await asyncio.gather(update_a(), update_b())
    statuses = {response_a.status_code, response_b.status_code}

    assert statuses == {200, 409}


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_002_successful_update_returns_version_increment(
    client,
    test_user: User,
    test_tenant: Tenant,
    concurrency_project: dict,
    generate_token,
) -> None:
    """TS-E2E-ERR-CON-001: successful update must increment version field."""
    headers = _headers(generate_token, test_user, test_tenant)
    project_id = concurrency_project["id"]

    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Versioned Update", "expected_version": 1},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 2


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_003_get_project_returns_etag_header(
    client,
    test_user: User,
    test_tenant: Tenant,
    concurrency_project: dict,
    generate_token,
) -> None:
    """TS-E2E-ERR-CON-001: GET must return ETag for conditional writes."""
    headers = _headers(generate_token, test_user, test_tenant)
    project_id = concurrency_project["id"]

    response = await client.get(f"/api/v1/projects/{project_id}", headers=headers)

    assert response.status_code == 200
    assert "ETag" in response.headers


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_004_patch_without_if_match_is_rejected(
    client,
    test_user: User,
    test_tenant: Tenant,
    concurrency_project: dict,
    generate_token,
) -> None:
    """TS-E2E-ERR-CON-001: missing If-Match must return precondition-required."""
    headers = _headers(generate_token, test_user, test_tenant)
    project_id = concurrency_project["id"]

    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "No If-Match"},
        headers=headers,
    )

    if os.getenv("C2PRO_TEST_LIGHT") == "1" and response.status_code == 200:
        pytest.xfail("RED contract pending in light mode: PATCH without If-Match is not yet rejected.")

    assert response.status_code == 428


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_005_patch_with_stale_if_match_returns_412(
    client,
    test_user: User,
    test_tenant: Tenant,
    concurrency_project: dict,
    generate_token,
) -> None:
    """TS-E2E-ERR-CON-001: stale If-Match must fail with 412."""
    headers = _headers(generate_token, test_user, test_tenant)
    project_id = concurrency_project["id"]

    first = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "First update", "expected_version": 1},
        headers={**headers, "If-Match": '"v1"'},
    )
    assert first.status_code == 200

    second = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Stale update", "expected_version": 1},
        headers={**headers, "If-Match": '"v1"'},
    )

    assert second.status_code == 412


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_006_conflict_payload_contains_machine_readable_code(
    client,
    test_user: User,
    test_tenant: Tenant,
    concurrency_project: dict,
    generate_token,
) -> None:
    """TS-E2E-ERR-CON-001: conflict response must include detail.code."""
    headers = _headers(generate_token, test_user, test_tenant)
    project_id = concurrency_project["id"]

    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Conflict update", "expected_version": 999},
        headers={**headers, "If-Match": '"v999"'},
    )

    assert response.status_code == 409
    body = response.json()
    assert body["detail"]["code"] == "CONCURRENT_MODIFICATION"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_007_concurrent_cross_tenant_update_isolation_holds_under_race(
    client,
    test_user: User,
    test_tenant: Tenant,
    test_user_2: User,
    test_tenant_2: Tenant,
    concurrency_project: dict,
    generate_token,
) -> None:
    """TS-E2E-ERR-CON-001: cross-tenant concurrent write attempts must be denied."""
    headers_a = _headers(generate_token, test_user, test_tenant)
    headers_b = _headers(generate_token, test_user_2, test_tenant_2)
    project_id = concurrency_project["id"]

    async def tenant_a_update():
        return await client.patch(
            f"/api/v1/projects/{project_id}",
            json={"name": "Tenant A write", "expected_version": 1},
            headers=headers_a,
        )

    async def tenant_b_update():
        return await client.patch(
            f"/api/v1/projects/{project_id}",
            json={"name": "Tenant B write", "expected_version": 1},
            headers=headers_b,
        )

    response_a, response_b = await asyncio.gather(tenant_a_update(), tenant_b_update())
    assert response_a.status_code == 200
    assert response_b.status_code == 404


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_008_duplicate_idempotency_key_rejected_for_mutating_requests(
    client,
    test_user: User,
    test_tenant: Tenant,
    concurrency_project: dict,
    generate_token,
) -> None:
    """TS-E2E-ERR-CON-001: duplicate Idempotency-Key must reject second mutation."""
    headers = {
        **_headers(generate_token, test_user, test_tenant),
        "Idempotency-Key": "fixed-key-001",
    }
    project_id = concurrency_project["id"]

    first = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "First idempotent update", "expected_version": 1},
        headers=headers,
    )
    assert first.status_code == 200

    second = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Duplicate idempotent update", "expected_version": 1},
        headers=headers,
    )

    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "DUPLICATE_REQUEST"

