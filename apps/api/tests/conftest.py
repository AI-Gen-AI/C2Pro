"""
C2Pro - Test Configuration

Pytest fixtures for testing the C2Pro API.
Provides test database, authenticated clients, and test data.
"""

import asyncio
import os
import sys
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
import json
from types import SimpleNamespace
from typing import Callable
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
import jwt
from sqlalchemy import Column, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy import event, select

# ===========================================
# OPTIONAL DEPENDENCY STUBS
# ===========================================

if "celery" not in sys.modules:
    class _DummyConf(dict):
        def __getattr__(self, name):
            return self.get(name)

        def __setattr__(self, name, value):
            self[name] = value

    class _DummyCelery:
        def __init__(self, *args, **kwargs) -> None:
            self.conf = _DummyConf()

        def task(self, *args, **kwargs):
            def decorator(fn):
                fn.delay = lambda *a, **k: SimpleNamespace(id="test-task")
                return fn
            return decorator

        def start(self):
            return None

    sys.modules["celery"] = SimpleNamespace(Celery=_DummyCelery)

# ===========================================
# ENVIRONMENT SETUP
# ===========================================

# Fix for Windows asyncpg issues
# Use Selector event loop instead of Proactor on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Configurar variables de entorno antes de importar la app
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DEBUG", "true")

# Database
# Align default local test URL with docker-compose.test.yml credentials.
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/c2pro_test")

# Supabase
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test.mock")
os.environ.setdefault(
    "SUPABASE_SERVICE_ROLE_KEY", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test.mock.service"
)

# JWT
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-secret-key-min-32-chars-required-for-testing-purposes-only"
)
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")

# Anthropic (mock)
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-mock-key")

# Redis (opcional para tests)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

# Rate Limiting
os.environ.setdefault("RATE_LIMIT_ENABLED", "true")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "100")

# ===========================================
# IMPORTS AFTER ENV SETUP
# ===========================================

from src.config import settings
from src.core.database import Base, get_session
from src.main import create_application
from src.core.auth.models import Tenant, User, UserRole, SubscriptionPlan
from src.core.auth.service import hash_password


def _ensure_test_fk_stub_tables() -> None:
    """Register minimal stub tables required by cross-module FKs in test metadata."""
    if "wbs_items" not in Base.metadata.tables:
        # Stakeholder RACI model references this table via FK, but the canonical
        # table model is not part of Base metadata in this test layout.
        from sqlalchemy import Table

        Table(
            "wbs_items",
            Base.metadata,
            Column("id", PGUUID(as_uuid=True), primary_key=True),
            extend_existing=True,
        )


def _auth_schema_available(session: Session) -> bool:
    cached = session.info.get("auth_schema_available")
    if cached is not None:
        return cached
    try:
        result = session.execute(
            text("SELECT 1 FROM pg_namespace WHERE nspname = 'auth'")
        ).first()
        available = bool(result)
    except Exception:
        available = False
    session.info["auth_schema_available"] = available
    return available


def _auth_user_trigger_enabled(session: Session) -> bool:
    cached = session.info.get("auth_user_trigger_enabled")
    if cached is not None:
        return cached
    try:
        result = session.execute(
            text(
                """
                SELECT 1
                FROM pg_trigger t
                JOIN pg_class c ON c.oid = t.tgrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'auth'
                  AND c.relname = 'users'
                  AND t.tgname = 'on_auth_user_created'
                  AND t.tgenabled <> 'D'
                """
            )
        ).first()
        enabled = bool(result)
    except Exception:
        enabled = False
    session.info["auth_user_trigger_enabled"] = enabled
    return enabled


@event.listens_for(Session, "before_flush")
def _ensure_auth_users(session: Session, _flush_context, _instances) -> None:
    if session.bind is None or session.bind.dialect.name != "postgresql":
        return
    if not _auth_schema_available(session):
        return
    new_users = [obj for obj in session.new if isinstance(obj, User)]
    if not new_users:
        return
    for user in new_users:
        if user.role is None:
            role_value = "user"
        else:
            role_value = user.role.value if hasattr(user.role, "value") else str(user.role)
        meta = json.dumps({"tenant_id": str(user.tenant_id), "role": role_value})
        trigger_enabled = _auth_user_trigger_enabled(session)
        if trigger_enabled:
            try:
                session.execute(text("SET LOCAL session_replication_role = replica"))
            except Exception:
                trigger_enabled = False
        session.execute(
            text(
                """
                INSERT INTO auth.users (id, email, raw_user_meta_data, created_at, updated_at)
                VALUES (:id, :email, CAST(:meta AS jsonb), NOW(), NOW())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"id": user.id, "email": user.email, "meta": meta},
        )
        if trigger_enabled:
            session.execute(text("SET LOCAL session_replication_role = origin"))

# ===========================================
# PYTEST CONFIGURATION
# ===========================================


def pytest_configure(config):
    """Registrar custom markers."""
    config.addinivalue_line("markers", "security: marca tests de seguridad críticos")
    # CTO Gates verification markers
    config.addinivalue_line("markers", "gate_verification: CTO security gates verification tests")
    config.addinivalue_line("markers", "gate1_rls: Gate 1 - Row Level Security verification")
    config.addinivalue_line(
        "markers", "gate2_identity: Gate 2 - Identity & Authentication verification"
    )
    config.addinivalue_line("markers", "gate3_mcp: Gate 3 - MCP Security verification")
    config.addinivalue_line(
        "markers", "gate4_traceability: Gate 4 - Traceability & Audit Logging verification"
    )


@pytest.fixture(scope="session")
def anyio_backend():
    """Configura backend para pytest-anyio."""
    return "asyncio"


# Configuración de pytest-asyncio para estabilidad
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="function")
def event_loop():
    """
    Create an instance of the event loop for each test function.
    This avoids issues with event loop reuse and futures attached to different loops.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# ===========================================
# DATABASE FIXTURES
# ===========================================


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """
    Create a test database engine.
    Uses a separate test database to avoid polluting development data.
    """
    from sqlalchemy.exc import OperationalError

    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        # Use asyncpg for async PostgreSQL operations (already in requirements.txt)
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    try:
        engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            connect_args={"statement_cache_size": 0},  # asyncpg config for test isolation
        )

        # Test connection and create tables
        _ensure_test_fk_stub_tables()
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.run_sync(Base.metadata.create_all)

        yield engine

        # Cleanup: Drop all tables after tests
        async with engine.begin() as conn:
            try:
                await conn.run_sync(Base.metadata.drop_all)
            except Exception as exc:
                # Avoid hard failing test teardown when metadata is incomplete
                print(f"\n[WARNING] Teardown drop_all skipped: {exc}")

        await engine.dispose()

    except (OperationalError, OSError):
        # Fallback to SQLite in memory
        print("\n[WARNING] PostgreSQL no disponible, usando SQLite en memoria")
        print("   Para ejecutar TODOS los tests, inicia PostgreSQL con:")
        print("   docker-compose -f docker-compose.test.yml up -d\n")

        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
        )

        _ensure_test_fk_stub_tables()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield engine
        await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session_factory(test_engine):
    """
    Create a session factory for tests.
    """
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture
async def db(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a database session for tests with automatic rollback.

    Each test gets a fresh session that is rolled back after the test,
    ensuring test isolation.
    """
    async with test_session_factory() as session:
        try:
            yield session
        finally:
            # Ensure any open transaction is rolled back between tests
            await session.rollback()


# Alias for compatibility
@pytest_asyncio.fixture
async def db_session(db) -> AsyncGenerator[AsyncSession, None]:
    """Alias for db fixture for compatibility."""
    yield db


# ===========================================
# TEST DATA FIXTURES
# ===========================================


@pytest_asyncio.fixture
async def test_tenant(db: AsyncSession) -> Tenant:
    """
    Creates a test tenant for multi-tenant testing.
    """
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


@pytest_asyncio.fixture
async def test_user(db: AsyncSession, test_tenant: Tenant) -> User:
    """
    Creates a test user associated with test_tenant.

    Default credentials:
        - Email: test@example.com
        - Password: TestPassword123!
    """
    user = User(
        id=uuid4(),
        tenant_id=test_tenant.id,
        email="test@example.com",
        hashed_password=hash_password("TestPassword123!"),
        first_name="Test",
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
async def test_tenant_2(db: AsyncSession) -> Tenant:
    """
    Creates a second test tenant for testing tenant isolation.
    """
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


@pytest_asyncio.fixture
async def test_user_2(db: AsyncSession, test_tenant_2: Tenant) -> User:
    """
    Creates a user in the second tenant for isolation testing.
    """
    user = User(
        id=uuid4(),
        tenant_id=test_tenant_2.id,
        email="test2@example.com",
        hashed_password=hash_password("TestPassword123!"),
        first_name="Test",
        last_name="User 2",
        role=UserRole.USER,
        is_active=True,
        is_verified=True,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


@pytest_asyncio.fixture
async def seeded_auth_context() -> dict[str, str]:
    """
    Deterministic tenant/user seed for real E2E auth.

    Refers to Suite ID: TS-I13-E2E-REAL-001.
    """
    tenant_id = UUID("00000000-0000-0000-0000-00000000a113")
    user_id = UUID("00000000-0000-0000-0000-00000000b113")

    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0},
    )
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

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
                hashed_password=hash_password("TestPassword123!"),
                first_name="I13",
                last_name="E2E",
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
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

    await engine.dispose()

    return {
        "tenant_id": str(tenant.id),
        "user_id": str(user.id),
        "email": user.email,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
    }


@pytest_asyncio.fixture
async def seeded_auth_headers(
    seeded_auth_context: dict[str, str],
    generate_token: Callable,
) -> dict[str, str]:
    """
    Build deterministic auth headers aligned with seeded tenant/user IDs.

    Refers to Suite ID: TS-I13-E2E-REAL-001.
    """
    token = generate_token(
        user_id=UUID(seeded_auth_context["user_id"]),
        tenant_id=UUID(seeded_auth_context["tenant_id"]),
        email=seeded_auth_context["email"],
        role=seeded_auth_context["role"],
    )
    return {"Authorization": f"Bearer {token}"}


# ===========================================
# SIMPLE ID FIXTURES (for unit tests)
# ===========================================


@pytest.fixture
def test_tenant_id():
    """Genera un tenant_id para tests."""
    return uuid4()


@pytest.fixture
def test_user_id():
    """Genera un user_id para tests."""
    return uuid4()


@pytest.fixture
def test_project_id():
    """Genera un project_id para tests."""
    return uuid4()


@pytest.fixture
def test_document_id():
    """Genera un document_id para tests."""
    return uuid4()


# ===========================================
# JWT TOKEN UTILITIES
# ===========================================


@pytest.fixture
def generate_token() -> Callable:
    """
    Factory fixture to generate JWT tokens with custom properties.

    Useful for testing various token scenarios:
    - Expired tokens
    - Invalid signatures
    - Missing claims
    - Tokens for non-existent tenants
    """
    def _generate_token(
        user_id: UUID | None = None,
        tenant_id: UUID | None = None,
        email: str = "test@example.com",
        role: str = "admin",
        expires_delta_seconds: int | None = None,
        secret_key: str | None = None,
        algorithm: str | None = None,
        extra_claims: dict | None = None,
        token_type: str = "access",
    ) -> str:
        """
        Generate a JWT token with custom properties.
        """
        if user_id is None:
            user_id = uuid4()
        if tenant_id is None:
            tenant_id = uuid4()

        # Calculate expiration
        if expires_delta_seconds is None:
            if token_type == "access":
                expire = datetime.utcnow() + timedelta(hours=24)
            else:
                expire = datetime.utcnow() + timedelta(days=7)
        else:
            expire = datetime.utcnow() + timedelta(seconds=expires_delta_seconds)

        # Build payload
        payload = {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "email": email,
            "role": role,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": token_type,
        }

        # Add extra claims if provided
        if extra_claims:
            payload.update(extra_claims)

        # Use custom or default secret key
        key = secret_key if secret_key is not None else settings.jwt_secret_key
        algo = algorithm if algorithm is not None else settings.jwt_algorithm

        # Encode token
        encoded_jwt = jwt.encode(payload, key, algorithm=algo)
        return encoded_jwt

    return _generate_token


# Alias for compatibility
@pytest.fixture
def create_test_token(generate_token) -> Callable:
    """Alias for generate_token for compatibility."""
    def _create_token(
        user_id: UUID,
        tenant_id: UUID,
        email: str = "test@example.com",
        role: str = "admin",
        secret_key: str | None = None,
        expires_delta: timedelta | None = None,
        token_type: str = "access",
    ) -> str:
        expires_seconds = int(expires_delta.total_seconds()) if expires_delta else None
        return generate_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            role=role,
            secret_key=secret_key,
            expires_delta_seconds=expires_seconds,
            token_type=token_type,
        )
    return _create_token


@pytest_asyncio.fixture
async def get_auth_headers(test_user: User, test_tenant: Tenant, generate_token: Callable) -> Callable:
    """
    Factory fixture to generate authentication headers for API requests.
    """
    async def _get_headers(
        user: User | None = None,
        tenant: Tenant | None = None,
    ) -> dict[str, str]:
        u = user or test_user
        t = tenant or test_tenant

        token = generate_token(
            user_id=u.id,
            tenant_id=t.id,
            email=u.email,
            role=u.role.value if hasattr(u.role, 'value') else u.role,
        )

        return {"Authorization": f"Bearer {token}"}

    return _get_headers


# Simple sync version for unit tests
@pytest.fixture
def get_auth_headers_simple(generate_token, test_user_id, test_tenant_id):
    """
    Simple sync factory fixture for auth headers (unit tests).
    """
    def _get_headers(
        user_id: UUID | None = None,
        tenant_id: UUID | None = None,
        email: str = "test@example.com",
        role: str = "admin",
    ) -> dict[str, str]:
        token = generate_token(
            user_id=user_id or test_user_id,
            tenant_id=tenant_id or test_tenant_id,
            email=email,
            role=role,
        )
        return {"Authorization": f"Bearer {token}"}

    return _get_headers


# ===========================================
# HTTP CLIENT FIXTURES
# ===========================================


@pytest_asyncio.fixture
async def app():
    """
    Creates a FastAPI application for testing.
    """
    return create_application()


@pytest_asyncio.fixture
async def client(app, db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Creates an HTTP client for testing API endpoints.
    """
    async def override_get_session(*args, **kwargs):
        yield db

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=30.0,
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ===========================================
# SUPERUSER CLEANUP FIXTURES (for RLS testing)
# ===========================================


@pytest.fixture(scope="function")
async def superuser_cleanup_engine():
    """
    Create a database engine using the SUPERUSER account for test cleanup.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from src.config import settings

    cleanup_url = settings.database_url
    if cleanup_url.startswith("postgresql://"):
        cleanup_url = cleanup_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    cleanup_engine = create_async_engine(
        cleanup_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0,
    )

    yield cleanup_engine
    await cleanup_engine.dispose()


@pytest.fixture
async def cleanup_database(superuser_cleanup_engine):
    """
    Helper fixture to clean up test data using superuser connection.
    """
    async def _cleanup(**entity_ids):
        async with AsyncSession(superuser_cleanup_engine) as session:
            cleanup_order = ["documents", "projects", "users", "tenants"]

            for table in cleanup_order:
                ids = entity_ids.get(table, [])
                if ids:
                    if not isinstance(ids, list):
                        ids = [ids]

                    if len(ids) == 1:
                        query = text(f"DELETE FROM {table} WHERE id = :id")
                        await session.execute(query, {"id": ids[0]})
                    else:
                        placeholders = ", ".join([f":id_{i}" for i in range(len(ids))])
                        query = text(f"DELETE FROM {table} WHERE id IN ({placeholders})")
                        params = {f"id_{i}": id_val for i, id_val in enumerate(ids)}
                        await session.execute(query, params)

            await session.commit()

    return _cleanup


# ===========================================
# UTILITY FIXTURES
# ===========================================


@pytest.fixture
def clean_tables() -> list[str]:
    """
    Returns list of tables to clean between tests.
    """
    return [
        "users",
        "tenants",
        "projects",
        "documents",
        "clauses",
        "analyses",
        "inconsistencies",
    ]


@pytest_asyncio.fixture
async def clean_db(db: AsyncSession, clean_tables: list[str]):
    """
    Cleans specified tables before test execution.
    """
    for table in clean_tables:
        try:
            await db.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            await db.commit()
        except Exception:
            await db.rollback()
            pass


@pytest.fixture
async def create_test_user_and_tenant(db):
    """
    Factory fixture para crear un Tenant y un User asociados en la base de datos.
    """
    async def _create(tenant_name: str, user_email: str):
        tenant_id = uuid4()
        user_id = uuid4()

        tenant = Tenant(id=tenant_id, name=tenant_name)
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)

        user = User(
            id=user_id,
            email=user_email,
            tenant_id=tenant_id,
            hashed_password="hashedpassword",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        return user, tenant

    return _create
