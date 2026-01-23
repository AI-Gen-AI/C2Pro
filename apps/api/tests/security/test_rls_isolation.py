from uuid import uuid4

import pytest
from httpx import AsyncClient

from src.modules.auth.models import Tenant, User
from src.modules.documents.models import DocumentType
from src.modules.projects.models import Project


@pytest.mark.asyncio
@pytest.mark.security
async def test_tenant_cannot_access_other_tenant_projects(
    client: AsyncClient, get_auth_headers, cleanup_database
):
    """
    Ensures a user from Tenant B cannot access projects belonging to Tenant A.
    This validates the Row Level Security (RLS) policies on the 'projects' table.
    """
    # === Arrange ===
    # Create test data directly in database
    from src.core.database import _session_factory

    tenant_a_id = uuid4()
    tenant_b_id = uuid4()
    user_a_id = uuid4()
    user_b_id = uuid4()
    project_a_id = uuid4()

    # Create tenants, users, and project in actual database
    async with _session_factory() as session:
        tenant_a = Tenant(id=tenant_a_id, name="Tenant A")
        tenant_b = Tenant(id=tenant_b_id, name="Tenant B")
        session.add_all([tenant_a, tenant_b])
        await session.flush()

        user_a = User(
            id=user_a_id,
            email="user_a@example.com",
            tenant_id=tenant_a_id,
            hashed_password="hashedpassword",
        )
        user_b = User(
            id=user_b_id,
            email="user_b@example.com",
            tenant_id=tenant_b_id,
            hashed_password="hashedpassword",
        )
        session.add_all([user_a, user_b])
        await session.flush()

        project_a = Project(id=project_a_id, name="Project for Tenant A", tenant_id=tenant_a_id)
        session.add(project_a)
        await session.commit()

    try:
        headers_a = get_auth_headers(user_id=user_a_id, tenant_id=tenant_a_id)
        headers_b = get_auth_headers(user_id=user_b_id, tenant_id=tenant_b_id)

        # === Act ===
        # User B attempts to access Project A
        response = await client.get(f"/api/v1/projects/{project_a_id}", headers=headers_b)

        # === Assert ===
        # The request should fail, as RLS prevents User B from seeing Project A.
        # A 404 Not Found is the expected response because from User B's perspective,
        # the project does not exist.
        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

    finally:
        # Clean up: delete the test data using superuser connection
        await cleanup_database(
            projects=[project_a_id],
            users=[user_a_id, user_b_id],
            tenants=[tenant_a_id, tenant_b_id],
        )


@pytest.mark.asyncio
@pytest.mark.security
async def test_user_cannot_upload_document_to_other_tenant_project(
    client: AsyncClient, get_auth_headers, cleanup_database
):
    """
    Ensures a user from Tenant B cannot upload a document to a project in Tenant A.
    This validates RLS on the 'documents' table via the 'project_id' check.
    """
    # === Arrange ===
    # Create test data directly in database
    from src.core.database import _session_factory

    tenant_a_id = uuid4()
    tenant_b_id = uuid4()
    user_a_id = uuid4()
    user_b_id = uuid4()
    project_a_id = uuid4()

    # Create tenants, users, and project in actual database
    async with _session_factory() as session:
        tenant_a = Tenant(id=tenant_a_id, name="Tenant A")
        tenant_b = Tenant(id=tenant_b_id, name="Tenant B")
        session.add_all([tenant_a, tenant_b])
        await session.flush()

        user_a = User(
            id=user_a_id,
            email="user_a_doc@example.com",
            tenant_id=tenant_a_id,
            hashed_password="hashedpassword",
        )
        user_b = User(
            id=user_b_id,
            email="user_b_doc@example.com",
            tenant_id=tenant_b_id,
            hashed_password="hashedpassword",
        )
        session.add_all([user_a, user_b])
        await session.flush()

        project_a = Project(
            id=project_a_id, name="Document Project for Tenant A", tenant_id=tenant_a_id
        )
        session.add(project_a)
        await session.commit()

    try:
        headers_a = get_auth_headers(user_id=user_a_id, tenant_id=tenant_a_id)
        headers_b = get_auth_headers(user_id=user_b_id, tenant_id=tenant_b_id)

        # === Act ===
        # User B attempts to upload a document to Project A.
        upload_data = {
            "project_id": str(project_a_id),
            "document_type": DocumentType.CONTRACT.value,
        }
        files = {"file": ("contract.pdf", b"dummy pdf content", "application/pdf")}
        response = await client.post(
            f"/api/v1/documents/projects/{project_a_id}/upload",
            data=upload_data,
            files=files,
            headers=headers_b,
        )

        # === Assert ===
        # The request should be rejected. The API should respond with a 404 Not Found
        # because the project is not visible to User B, thus DocumentService._get_project_tenant_id fails.
        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

    finally:
        # Clean up: delete the test data using superuser connection
        await cleanup_database(
            projects=[project_a_id],
            users=[user_a_id, user_b_id],
            tenants=[tenant_a_id, tenant_b_id],
        )


@pytest.mark.asyncio
@pytest.mark.security
async def test_tenant_can_only_list_their_own_projects(
    client: AsyncClient, get_auth_headers, cleanup_database
):
    """
    Ensures that when listing projects, a user only sees projects belonging to their own tenant.
    """
    # === Arrange ===
    # Create test data directly in database
    from src.core.database import _session_factory

    tenant_1_id = uuid4()
    tenant_2_id = uuid4()
    user_1_id = uuid4()
    user_2_id = uuid4()
    project_1_a_id = uuid4()
    project_1_b_id = uuid4()
    project_2_a_id = uuid4()

    # Create tenants, users, and projects in actual database
    async with _session_factory() as session:
        tenant_1 = Tenant(id=tenant_1_id, name="Tenant 1")
        tenant_2 = Tenant(id=tenant_2_id, name="Tenant 2")
        session.add_all([tenant_1, tenant_2])
        await session.flush()

        user_1 = User(
            id=user_1_id,
            email="user1@example.com",
            tenant_id=tenant_1_id,
            hashed_password="hashedpassword",
        )
        user_2 = User(
            id=user_2_id,
            email="user2@example.com",
            tenant_id=tenant_2_id,
            hashed_password="hashedpassword",
        )
        session.add_all([user_1, user_2])
        await session.flush()

        # Create projects for Tenant 1
        project_1_a = Project(id=project_1_a_id, name="T1 Project A", tenant_id=tenant_1_id)
        project_1_b = Project(id=project_1_b_id, name="T1 Project B", tenant_id=tenant_1_id)
        session.add_all([project_1_a, project_1_b])
        await session.flush()

        # Create projects for Tenant 2
        project_2_a = Project(id=project_2_a_id, name="T2 Project A", tenant_id=tenant_2_id)
        session.add(project_2_a)
        await session.commit()

    try:
        headers_1 = get_auth_headers(user_id=user_1_id, tenant_id=tenant_1_id)
        headers_2 = get_auth_headers(user_id=user_2_id, tenant_id=tenant_2_id)

        # === Act ===
        # User from Tenant 1 lists projects
        response_1 = await client.get("/api/v1/projects/", headers=headers_1)

        # User from Tenant 2 lists projects
        response_2 = await client.get("/api/v1/projects/", headers=headers_2)

        # === Assert ===
        assert response_1.status_code == 200
        data_1 = response_1.json()
        # Response is paginated, so we need to get the items
        assert "items" in data_1
        projects_user_1 = data_1["items"]
        assert len(projects_user_1) == 2
        assert {p["id"] for p in projects_user_1} == {str(project_1_a_id), str(project_1_b_id)}

        assert response_2.status_code == 200
        data_2 = response_2.json()
        assert "items" in data_2
        projects_user_2 = data_2["items"]
        assert len(projects_user_2) == 1
        assert {p["id"] for p in projects_user_2} == {str(project_2_a_id)}

    finally:
        # Clean up: delete the test data using superuser connection
        await cleanup_database(
            projects=[project_1_a_id, project_1_b_id, project_2_a_id],
            users=[user_1_id, user_2_id],
            tenants=[tenant_1_id, tenant_2_id],
        )
