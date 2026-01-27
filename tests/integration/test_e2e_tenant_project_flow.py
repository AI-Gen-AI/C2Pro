"""
C2Pro - End-to-End Test: Tenant and Project Creation Flow

This test covers the complete cycle from tenant creation to project setup:
1. Register new user (creates tenant and admin user)
2. Login to get authentication token
3. Create a project
4. Create additional users at project level
5. Verify tenant isolation and user roles
"""

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.main import app
from src.core import database as db_module
from src.core.database import Base, get_session
from src.modules.auth.models import Tenant, User, UserRole
from src.projects.adapters.persistence.models import ProjectORM


async def _override_get_session():
    if db_module._session_factory is None:
        raise RuntimeError("Database session factory not initialized.")
    async with db_module._session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest.mark.asyncio
async def test_tenant_project_creation_flow():
    """
    E2E test for tenant creation, user registration, project creation, and user management.
    """
    # Setup test client with lifespan
    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Get database session
            db = await anext(_override_get_session())
            try:
                await _run_test_flow(client, db)
            finally:
                await db.close()


async def _run_test_flow(client: AsyncClient, db: AsyncSession):
    """Run the actual test flow."""
    # Test data
    tenant_name = "Test Construction Corp"
    admin_email = "admin@testcorp.com"
    admin_password = "SecurePass123!"
    project_name = "Highway Project Alpha"

    # Step 1: Register new user (creates tenant and admin user)
    register_payload = {
        "email": admin_email,
        "password": admin_password,
        "first_name": "John",
        "last_name": "Admin",
        "company_name": tenant_name,
        "phone": "+1234567890",
        "accept_terms": True
    }

    register_response = await client.post("/api/v1/auth/register", json=register_payload)
    assert register_response.status_code == 201

    register_data = register_response.json()
    assert "user" in register_data
    assert "tenant" in register_data
    assert register_data["user"]["email"] == admin_email
    assert register_data["user"]["role"] == "admin"
    assert register_data["tenant"]["name"] == tenant_name

    tenant_id = register_data["tenant"]["id"]
    user_id = register_data["user"]["id"]

    # Verify tenant and user created in database
    tenant = await db.get(Tenant, tenant_id)
    assert tenant is not None
    assert tenant.name == tenant_name
    assert len(tenant.users) == 1

    user = await db.get(User, user_id)
    assert user is not None
    assert user.email == admin_email
    assert user.role == UserRole.ADMIN
    assert user.tenant_id == tenant_id

    # Step 2: Login to get authentication token
    login_payload = {
        "email": admin_email,
        "password": admin_password
    }

    login_response = await client.post("/api/v1/auth/login", json=login_payload)
    assert login_response.status_code == 200

    login_data = login_response.json()
    assert "access_token" in login_data
    assert "token_type" in login_data
    assert login_data["token_type"] == "bearer"

    access_token = login_data["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Step 3: Create a project
    project_payload = {
        "name": project_name,
        "description": "Major highway construction project",
        "code": "HWY-001",
        "project_type": "construction"
    }

    project_response = await client.post("/api/v1/projects", json=project_payload, headers=headers)
    assert project_response.status_code == 201

    project_data = project_response.json()
    assert project_data["name"] == project_name
    assert project_data["tenant_id"] == tenant_id

    project_id = project_data["id"]

    # Verify project created in database
    project = await db.get(ProjectORM, project_id)
    assert project is not None
    assert project.name == project_name
    assert project.tenant_id == tenant_id

    # Step 4: Create additional users at project level
    # Note: Since there's no API endpoint for user creation yet,
    # we'll simulate by creating users directly in the database
    # In a real scenario, this would be done via an invite endpoint

    # Create project manager user
    pm_user = User(
        tenant_id=tenant_id,
        email="pm@testcorp.com",
        hashed_password="hashed_password",  # In real app, this would be hashed
        first_name="Jane",
        last_name="Manager",
        role=UserRole.USER,
        is_active=True,
        is_verified=True
    )
    db.add(pm_user)

    # Create viewer user
    viewer_user = User(
        tenant_id=tenant_id,
        email="viewer@testcorp.com",
        hashed_password="hashed_password",
        first_name="Bob",
        last_name="Viewer",
        role=UserRole.VIEWER,
        is_active=True,
        is_verified=True
    )
    db.add(viewer_user)

    await db.commit()

    # Verify users created
    users_query = select(User).where(User.tenant_id == tenant_id)
    result = await db.execute(users_query)
    tenant_users = result.scalars().all()

    assert len(tenant_users) == 3  # admin + pm + viewer

    roles = [u.role for u in tenant_users]
    assert UserRole.ADMIN in roles
    assert UserRole.USER in roles
    assert UserRole.VIEWER in roles

    # Step 5: Verify tenant isolation
    # Create another tenant to ensure isolation
    other_tenant = Tenant(
        name="Other Corp",
        slug="other-corp",
        subscription_plan="free"
    )
    db.add(other_tenant)

    other_user = User(
        tenant_id=other_tenant.id,
        email="other@test.com",
        hashed_password="hashed_password",
        role=UserRole.ADMIN
    )
    db.add(other_user)

    await db.commit()

    # Verify that users from different tenants are isolated
    tenant_users_query = select(User).where(User.tenant_id == tenant_id)
    tenant_result = await db.execute(tenant_users_query)
    tenant_users_only = tenant_result.scalars().all()

    assert len(tenant_users_only) == 3
    assert all(u.tenant_id == tenant_id for u in tenant_users_only)

    # Step 6: Test project access (as admin)
    projects_response = await client.get("/api/v1/projects", headers=headers)
    assert projects_response.status_code == 200

    projects_data = projects_response.json()
    assert len(projects_data) == 1
    assert projects_data[0]["id"] == project_id
    assert projects_data[0]["name"] == project_name

    # Cleanup: Delete test data
    await db.delete(project)
    for u in tenant_users:
        await db.delete(u)
    await db.delete(tenant)
    await db.delete(other_user)
    await db.delete(other_tenant)
    await db.commit()

    print("✅ E2E test completed successfully: Tenant creation → User registration → Project creation → User management")