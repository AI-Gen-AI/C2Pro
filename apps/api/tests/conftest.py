"""
C2Pro - Test Configuration  (TASK-QA-206: refactored to ≤ 700 LOC)

Heavy fixtures are split into separate plugin modules loaded via pytest_plugins:
  - tests._bootstrap          DB helpers, engine/session/db fixtures, markers
  - tests.fixtures.sdk_isolators  autouse SDK-isolation + Prometheus cleanup
  - tests.fixtures.auth       JWT helpers, simple ID fixtures
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncGenerator, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# =============================================================
# ENVIRONMENT SETUP  (must run before any src.* import)
# =============================================================

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/c2pro_test"
)
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test.mock")
os.environ.setdefault(
    "SUPABASE_SERVICE_ROLE_KEY", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test.mock.service"
)
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-secret-key-min-32-chars-required-for-testing-purposes-only"
)
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-mock-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RATE_LIMIT_ENABLED", "true")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "100")
os.environ.setdefault("AUTH_BOOTSTRAP_ALLOW_FALLBACK_EMERGENCY", "true")

# =============================================================
# SRC IMPORTS  (after env setup)
# =============================================================

from src.analysis.adapters.persistence import models as analysis_models  # noqa: F401, E402
from src.coherence.adapters.persistence import models as coherence_models  # noqa: F401, E402
from src.config import settings  # noqa: E402
from src.core.ai import models as ai_models  # noqa: F401, E402
from src.core.auth.models import SubscriptionPlan, Tenant, User, UserRole  # noqa: E402
from src.core.auth.service import AuthService, hash_password  # noqa: F401, E402
from src.core.database import Base, get_session  # noqa: E402
from src.core.security import get_current_user_id  # noqa: E402
from src.core.security.adapters.persistence import models as security_models  # noqa: F401, E402
from src.documents.adapters.persistence import models as document_models  # noqa: F401, E402
from src.procurement.adapters.persistence import models as procurement_models  # noqa: F401, E402
from src.project_state.adapters.persistence import (
    models as project_state_models,  # noqa: F401, E402
)
from src.projects.adapters.persistence import models as project_models  # noqa: F401, E402
from src.stakeholders.adapters.persistence import models as stakeholder_models  # noqa: F401, E402
from src.temporal.adapters.persistence import models as temporal_models  # noqa: F401, E402
from tests._bootstrap import _ensure_test_fk_stub_tables  # noqa: E402
from tests.support.postgres_bootstrap import ensure_pgvector_extension  # noqa: E402
from tests.support.seeded_identity_guard import assert_seeded_identity_isolation_safe  # noqa: E402

# =============================================================
# CONSTANTS
# =============================================================

TEST_PASSWORD_HASH = hash_password("TestPassword123!")

# =============================================================
# PLUGIN LOADING — heavy fixtures live in these modules
# =============================================================

pytest_plugins = (
    "pytest_asyncio",
    "tests._bootstrap",
    "tests.fixtures.sdk_isolators",
    "tests.fixtures.auth",
)

# =============================================================
# TENANT / USER FIXTURES
# =============================================================


@pytest_asyncio.fixture(scope="function")
async def test_tenant(db: AsyncSession) -> Tenant:
    tenant = Tenant(
        id=uuid4(),
        name="Test Company",
        slug=f"test-company-{uuid4().hex[:8]}",
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


@pytest_asyncio.fixture(scope="function")
async def test_user(db: AsyncSession, test_tenant: Tenant) -> User:
    user = User(
        id=uuid4(),
        tenant_id=test_tenant.id,
        email=f"test-{uuid4().hex[:8]}@example.com",
        hashed_password=TEST_PASSWORD_HASH,
        first_name="Test",
        last_name="User",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
        last_login=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_tenant_2(db: AsyncSession) -> Tenant:
    tenant = Tenant(
        id=uuid4(),
        name="Test Company 2",
        slug=f"test-company-2-{uuid4().hex[:8]}",
        subscription_plan=SubscriptionPlan.STARTER,
        subscription_status="active",
        ai_budget_monthly=50.0,
        ai_spend_current=0.0,
        max_projects=10,
        max_users=5,
        max_storage_gb=50,
        is_active=True,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


@pytest_asyncio.fixture(scope="function")
async def test_user_2(db: AsyncSession, test_tenant_2: Tenant) -> User:
    user = User(
        id=uuid4(),
        tenant_id=test_tenant_2.id,
        email=f"test2-{uuid4().hex[:8]}@example.com",
        hashed_password=TEST_PASSWORD_HASH,
        first_name="Test",
        last_name="User 2",
        role=UserRole.USER,
        is_active=True,
        is_verified=True,
        last_login=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# =============================================================
# SEEDED AUTH FIXTURES  (TS-I13-E2E-REAL-001)
# =============================================================


@pytest_asyncio.fixture(scope="function")
async def seeded_auth_context() -> dict[str, str]:
    """Deterministic tenant/user seed for real E2E auth (TS-I13-E2E-REAL-001)."""
    tenant_id = UUID("00000000-0000-0000-0000-00000000a113")
    user_id = UUID("00000000-0000-0000-0000-00000000b113")

    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    root_database_url = database_url.rsplit("/", 1)[0] + "/postgres"

    assert_seeded_identity_isolation_safe(database_url)

    engine = create_async_engine(
        root_database_url,
        echo=False,
        pool_pre_ping=True,
        isolation_level="AUTOCOMMIT",
        connect_args={"statement_cache_size": 0},
    )
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    _ensure_test_fk_stub_tables()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL search_path TO public"))
        await ensure_pgvector_extension(conn)
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        tenant_result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = tenant_result.scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(
                id=tenant_id,
                name="I13 Real E2E Tenant",
                slug="i13-real-e2e-tenant",
                subscription_plan=SubscriptionPlan.PROFESSIONAL,
                subscription_status="active",
                ai_budget_monthly=100.0,
                ai_spend_current=0.0,
                max_projects=100,
                max_users=25,
                max_storage_gb=100,
                is_active=True,
            )
            session.add(tenant)
        else:
            tenant.is_active = True
            tenant.subscription_status = "active"

        user_result = await session.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if user is None:
            user = User(
                id=user_id,
                tenant_id=tenant_id,
                email="i13-real-e2e-user@c2pro.test",
                hashed_password=TEST_PASSWORD_HASH,
                first_name="I13",
                last_name="E2E",
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
                last_login=datetime.now(UTC).replace(tzinfo=None),
            )
            session.add(user)
        else:
            user.tenant_id = tenant_id
            user.email = "i13-real-e2e-user@c2pro.test"
            user.role = UserRole.ADMIN
            user.is_active = True
            user.is_verified = True

        await session.commit()
        await session.refresh(tenant)
        await session.refresh(user)

        payload = {
            "tenant_id": str(tenant.id),
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        }

    try:
        yield payload
    finally:
        async with session_factory() as cleanup:
            seeded_user = await cleanup.get(User, user_id)
            if seeded_user is not None:
                await cleanup.delete(seeded_user)
            seeded_tenant = await cleanup.get(Tenant, tenant_id)
            if seeded_tenant is not None:
                await cleanup.delete(seeded_tenant)
            await cleanup.commit()
        await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def seeded_auth_headers(
    seeded_auth_context: dict[str, str],
    generate_token: Callable,
) -> dict[str, str]:
    """Auth headers for the deterministic seeded identity (TS-I13-E2E-REAL-001)."""
    token = generate_token(
        user_id=UUID(seeded_auth_context["user_id"]),
        tenant_id=UUID(seeded_auth_context["tenant_id"]),
        email=seeded_auth_context["email"],
        role=seeded_auth_context["role"],
    )
    return {"Authorization": f"Bearer {token}"}


# =============================================================
# HTTP CLIENT FIXTURES
# =============================================================


@pytest_asyncio.fixture(scope="function")
async def app():
    from src.main import create_application

    return create_application()


@pytest_asyncio.fixture(scope="function")
async def client(app, db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_session():
        yield db

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", timeout=30.0) as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def authenticated_client(
    app,
    db: AsyncSession,
    test_user: User,
    generate_token: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient, None]:
    """Authenticated client for protected endpoint tests (TASK-BCK-030)."""

    async def override_get_session():
        yield db

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user_id] = lambda: test_user.id

    token = generate_token(
        user_id=test_user.id,
        tenant_id=test_user.tenant_id,
        email=test_user.email,
        role=test_user.role.value,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=30.0,
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        yield c
    app.dependency_overrides.clear()


# =============================================================
# CLEANUP FIXTURES
# =============================================================


@pytest.fixture(scope="function")
async def superuser_cleanup_engine():
    from sqlalchemy.ext.asyncio import create_async_engine as _eng

    cleanup_url = settings.database_url
    if cleanup_url.startswith("postgresql://"):
        cleanup_url = cleanup_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = _eng(cleanup_url, echo=False, pool_pre_ping=True, pool_size=2, max_overflow=0)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def cleanup_database(superuser_cleanup_engine):
    async def _cleanup(**entity_ids):
        async with AsyncSession(superuser_cleanup_engine) as session:
            order = [
                "users",
                "tenants",
                "projects",
                "documents",
                "clauses",
                "analyses",
                "alerts",
                "extractions",
                "stakeholders",
                "wbs_items",
                "bom_items",
                "stakeholder_wbs_raci",
                "ai_usage_logs",
                "audit_logs",
            ]
            for table in order:
                ids = entity_ids.get(table, [])
                if not ids:
                    continue
                if not isinstance(ids, list):
                    ids = [ids]
                if len(ids) == 1:
                    await session.execute(
                        text(f"DELETE FROM {table} WHERE id = :id"), {"id": ids[0]}
                    )
                else:
                    placeholders = ", ".join(f":id_{i}" for i in range(len(ids)))
                    await session.execute(
                        text(f"DELETE FROM {table} WHERE id IN ({placeholders})"),
                        {f"id_{i}": v for i, v in enumerate(ids)},
                    )
            await session.commit()

    return _cleanup


# =============================================================
# UTILITY FIXTURES
# =============================================================


@pytest.fixture(scope="function")
def mocker():
    """Minimal compatibility fixture for suites expecting pytest-mock's `mocker`."""
    from unittest import mock as _mock

    patchers: list = []

    class _Mocker:
        Mock = _mock.Mock
        AsyncMock = _mock.AsyncMock
        MagicMock = _mock.MagicMock
        call = _mock.call
        ANY = _mock.ANY

        @staticmethod
        def patch(target, *args, **kwargs):
            patcher = _mock.patch(target, *args, **kwargs)
            patchers.append(patcher)
            return patcher.start()

    yield _Mocker()
    for patcher in reversed(patchers):
        patcher.stop()


@pytest.fixture(scope="function")
def clean_tables() -> list[str]:
    return [
        "users",
        "tenants",
        "projects",
        "documents",
        "clauses",
        "analyses",
        "inconsistencies",
        "procurement_budget_items",
        "stakeholder_alerts",
    ]


@pytest_asyncio.fixture(scope="function")
async def clean_db(db: AsyncSession, clean_tables: list[str]):
    for table in clean_tables:
        try:
            await db.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            await db.commit()
        except Exception:
            await db.rollback()


@pytest.fixture(scope="function")
async def create_test_user_and_tenant(db):
    async def _create(tenant_name: str, user_email: str):
        t_id = uuid4()
        u_id = uuid4()
        tenant = Tenant(id=t_id, name=tenant_name)
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        user = User(id=u_id, email=user_email, tenant_id=t_id, hashed_password="hashedpassword")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user, tenant

    return _create
