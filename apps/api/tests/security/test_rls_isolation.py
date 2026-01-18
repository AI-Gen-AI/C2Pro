"""
C2Pro - Row Level Security (RLS) Isolation Tests

Tests for multi-tenant data isolation using PostgreSQL Row Level Security.
Validates that users from one tenant cannot access data from another tenant.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.projects.models import Project
from src.modules.auth.models import Tenant, User


@pytest.mark.asyncio
@pytest.mark.security
async def test_tenant_cannot_access_other_tenant_projects(
    client: AsyncClient,
    db: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
    test_tenant_2: Tenant,
    test_user_2: User,
    get_auth_headers,
):
    """
    Ensures a user from Tenant B cannot access projects belonging to Tenant A.
    This validates the Row Level Security (RLS) policies on the 'projects' table.
    """
    # === Arrange ===
    # 1. Get auth headers for both users
    headers_a = await get_auth_headers(test_user, test_tenant)
    headers_b = await get_auth_headers(test_user_2, test_tenant_2)

    # 2. Create a project for Tenant A
    project_data = {
        "name": "Project for Tenant A",
        "code": "PROJ-A-001",
        "description": "Test project for tenant isolation",
        "type": "construction",
    }
    response = await client.post("/projects/", json=project_data, headers=headers_a)
    assert response.status_code in [200, 201], f"Failed to create project: {response.text}"
    project_a_id = response.json()["id"]

    # === Act ===
    # 3. User B attempts to access Project A
    response = await client.get(f"/projects/{project_a_id}", headers=headers_b)

    # === Assert ===
    # 4. The request should fail, as RLS prevents User B from seeing Project A.
    # A 404 Not Found is the expected response because from User B's perspective,
    # the project does not exist.
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
@pytest.mark.security
async def test_user_cannot_upload_document_to_other_tenant_project(
    client: AsyncClient,
    db: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
    test_tenant_2: Tenant,
    test_user_2: User,
    get_auth_headers,
):
    """
    Ensures a user from Tenant B cannot upload a document to a project in Tenant A.
    This validates RLS on the 'documents' table via project access control.
    """
    # === Arrange ===
    # 1. Create a project for Tenant A
    headers_a = await get_auth_headers(test_user, test_tenant)
    project_data = {
        "name": "Document Project for Tenant A",
        "code": "DOC-PROJ-001",
        "type": "construction",
    }
    response = await client.post("/projects/", json=project_data, headers=headers_a)
    assert response.status_code in [200, 201]
    project_a_id = response.json()["id"]

    # 2. Get auth headers for User B
    headers_b = await get_auth_headers(test_user_2, test_tenant_2)

    # === Act ===
    # 3. User B attempts to upload a document to Project A
    # Note: This endpoint might not be implemented yet, so we test with project access
    upload_data = {
        "project_id": project_a_id,
        "document_type": "contract",
        "name": "Test Document",
    }

    # Try to create a document reference (if endpoint exists)
    response = await client.post("/documents/", json=upload_data, headers=headers_b)

    # === Assert ===
    # 4. The request should be rejected. The API should respond with a 404 Not Found
    # because the project is not visible to User B, or 403 Forbidden
    assert response.status_code in [403, 404]


@pytest.mark.asyncio
@pytest.mark.security
async def test_user_cannot_access_clauses_from_other_tenant(
    client: AsyncClient,
    db: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
    test_tenant_2: Tenant,
    test_user_2: User,
    get_auth_headers,
):
    """
    Ensures a user from Tenant B cannot access clauses from a document in Tenant A.
    This validates the RLS policy on the 'clauses' table (when implemented).
    """
    # === Arrange ===
    # 1. Create a project for Tenant A
    headers_a = await get_auth_headers(test_user, test_tenant)
    project_data = {
        "name": "Clause Project",
        "code": "CLAUSE-001",
        "type": "construction",
    }
    response = await client.post("/projects/", json=project_data, headers=headers_a)
    assert response.status_code in [200, 201]
    project_a_id = response.json()["id"]

    # 2. Get auth headers for User B
    headers_b = await get_auth_headers(test_user_2, test_tenant_2)

    # === Act ===
    # 3. User B attempts to access analyses/clauses for Project A
    # (Testing with analysis endpoint as clauses might not have direct endpoint)
    response = await client.get(f"/projects/{project_a_id}/analyses", headers=headers_b)

    # === Assert ===
    # 4. The request should fail with a 404 Not Found (project not visible to User B)
    assert response.status_code in [403, 404]


@pytest.mark.asyncio
@pytest.mark.security
async def test_user_can_only_list_own_tenant_projects(
    client: AsyncClient,
    db: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
    test_tenant_2: Tenant,
    test_user_2: User,
    get_auth_headers,
):
    """
    Ensures that when listing projects, users only see projects from their own tenant.
    """
    # === Arrange ===
    headers_a = await get_auth_headers(test_user, test_tenant)
    headers_b = await get_auth_headers(test_user_2, test_tenant_2)

    # 1. Create projects for both tenants
    project_a_data = {
        "name": "Tenant A Project",
        "code": "TA-001",
        "type": "construction",
    }
    response_a = await client.post("/projects/", json=project_a_data, headers=headers_a)
    assert response_a.status_code in [200, 201]

    project_b_data = {
        "name": "Tenant B Project",
        "code": "TB-001",
        "type": "construction",
    }
    response_b = await client.post("/projects/", json=project_b_data, headers=headers_b)
    assert response_b.status_code in [200, 201]

    # === Act ===
    # 2. User A lists projects
    response_a_list = await client.get("/projects/", headers=headers_a)
    assert response_a_list.status_code == 200

    # 3. User B lists projects
    response_b_list = await client.get("/projects/", headers=headers_b)
    assert response_b_list.status_code == 200

    # === Assert ===
    # 4. Each user should only see their own tenant's projects
    data_a = response_a_list.json()
    data_b = response_b_list.json()

    # Handle both list and paginated responses
    items_a = data_a if isinstance(data_a, list) else data_a.get("items", [])
    items_b = data_b if isinstance(data_b, list) else data_b.get("items", [])

    # User A should see at least their project
    assert len(items_a) >= 1
    # All projects should belong to tenant A
    for project in items_a:
        assert project["code"] == "TA-001" or "Tenant A" in project["name"]

    # User B should see at least their project
    assert len(items_b) >= 1
    # All projects should belong to tenant B
    for project in items_b:
        assert project["code"] == "TB-001" or "Tenant B" in project["name"]

    # Tenant B should not see Tenant A's project
    tenant_a_project_ids = [p["id"] for p in items_a]
    tenant_b_project_ids = [p["id"] for p in items_b]
    assert not set(tenant_a_project_ids).intersection(set(tenant_b_project_ids))
