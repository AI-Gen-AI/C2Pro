"""
Fail-closed auth bootstrap smoke tests.
TS-E2E-SEC-TNT-001
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.core.auth.bootstrap_lookup import BootstrapFallbackBlockedError
from src.core.auth.dependencies import _provision_clerk_user
from src.core.auth.schemas import LoginRequest, RegisterRequest
from src.core.auth.service import AuthService

ADMIN_URL = os.getenv(
    "C2PRO_RLS_ADMIN_URL",
    "postgresql://supabase_admin:postgres@localhost:54322/c2pro_migration_check",
)
APP_USER_URL = os.getenv(
    "C2PRO_RLS_APP_USER_URL",
    "postgresql+asyncpg://nonsuperuser:test@localhost:54322/c2pro_migration_check",
)
ROLE_NAME = os.getenv("C2PRO_RLS_ROLE_NAME", "nonsuperuser")
ROLE_PASSWORD = os.getenv("C2PRO_RLS_ROLE_PASSWORD", "test")


@pytest_asyncio.fixture
async def admin_conn():
    try:
        conn = await asyncpg.connect(ADMIN_URL, statement_cache_size=0)
    except Exception as exc:
        pytest.skip(f"Admin bootstrap smoke database unavailable: {exc}")
    try:
        yield conn
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def fail_closed_app_session(admin_conn: asyncpg.Connection, monkeypatch):
    db_name = ADMIN_URL.rsplit("/", 1)[-1]

    await admin_conn.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE_NAME}') THEN
                CREATE USER {ROLE_NAME} WITH PASSWORD '{ROLE_PASSWORD}';
            END IF;
        END $$;
        """
    )
    await admin_conn.execute(f"GRANT CONNECT ON DATABASE {db_name} TO {ROLE_NAME}")
    await admin_conn.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE_NAME}")
    await admin_conn.execute(f"GRANT USAGE ON SCHEMA auth_bootstrap TO {ROLE_NAME}")
    await admin_conn.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {ROLE_NAME}")
    await admin_conn.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {ROLE_NAME}")
    await admin_conn.execute(f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA auth_bootstrap TO {ROLE_NAME}")

    monkeypatch.setattr(settings, "database_url", APP_USER_URL)

    engine = create_async_engine(APP_USER_URL, connect_args={"statement_cache_size": 0})
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_register_and_login_work_under_fail_closed_policies(
    fail_closed_app_session: AsyncSession,
):
    """Public auth should still work when rows are protected by fail-closed RLS."""
    email = f"bootstrap-{uuid4()}@example.com"
    password = "SecurePass123!"

    register_response = await AuthService.register(
        fail_closed_app_session,
        RegisterRequest(
            email=email,
            password=password,
            password_confirm=password,
            first_name="Bootstrap",
            last_name="User",
            company_name=f"Bootstrap Co {uuid4()}",
            accept_terms=True,
        ),
    )

    assert register_response.user.email == email

    login_response = await AuthService.login(
        fail_closed_app_session,
        LoginRequest(email=email, password=password),
    )

    assert login_response.user.email == email
    assert login_response.tenant.id == register_response.tenant.id


@pytest.mark.asyncio
async def test_clerk_bootstrap_lookup_works_under_fail_closed_policies(
    fail_closed_app_session: AsyncSession,
):
    """Clerk provisioning should resolve the existing user via bootstrap helpers."""
    clerk_user_id = f"clerk-user-{uuid4().hex[:8]}"
    clerk_org_id = f"org_{uuid4().hex[:8]}"
    email = f"{clerk_user_id}@example.com"

    first_user = await _provision_clerk_user(
        fail_closed_app_session,
        clerk_user_id=clerk_user_id,
        clerk_org_id=clerk_org_id,
        email=email,
        first_name="Clerk",
        last_name="Bootstrap",
    )

    second_user = await _provision_clerk_user(
        fail_closed_app_session,
        clerk_user_id=clerk_user_id,
        clerk_org_id=clerk_org_id,
        email=email,
        first_name="Clerk",
        last_name="Bootstrap",
    )

    assert second_user.id == first_user.id
    assert second_user.tenant_id == first_user.tenant_id


@pytest.mark.asyncio
async def test_clerk_bootstrap_policy_denies_fallback_under_fail_closed_policies(
    fail_closed_app_session: AsyncSession,
    monkeypatch,
):
    """Provisioning should fail closed when bootstrap fallback is denied by policy."""
    clerk_user_id = f"clerk-user-{uuid4().hex[:8]}"
    clerk_org_id = f"org_{uuid4().hex[:8]}"

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "auth_bootstrap_allow_fallback_emergency", False)
    monkeypatch.setattr(
        "src.core.auth.dependencies.lookup_user_by_clerk_user_id",
        AsyncMock(side_effect=BootstrapFallbackBlockedError("Auth bootstrap fallback blocked by policy")),
        raising=False,
    )

    with pytest.raises(BootstrapFallbackBlockedError):
        await _provision_clerk_user(
            fail_closed_app_session,
            clerk_user_id=clerk_user_id,
            clerk_org_id=clerk_org_id,
            email=f"{clerk_user_id}@example.com",
            first_name="Clerk",
            last_name="Blocked",
        )
