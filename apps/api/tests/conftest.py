"""
C2Pro - Test Configuration

Pytest fixtures for testing the C2Pro API.
Provides test database, authenticated clients, and test data.
"""

import asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator, Callable
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from jose import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.core.database import Base, get_session
from src.main import create_application
from src.modules.auth.models import Tenant, User, UserRole, SubscriptionPlan
from src.modules.auth.service import hash_password


# ===========================================
# EVENT LOOP CONFIGURATION
# ===========================================

@pytest.fixture(scope="session")
def event_loop():
    """
    Create an instance of the event loop for the entire test session.
    This ensures all async tests share the same event loop.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ===========================================
# DATABASE FIXTURES
# ===========================================

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """
    Create a test database engine.
    Uses a separate test database to avoid polluting development data.
    """
    # Use test database URL
    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Create test database engine
    engine = create_async_engine(
        database_url,
        echo=False,  # Disable SQL logging in tests
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup: Drop all tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
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

    Usage:
        async def test_example(db: AsyncSession):
            user = User(...)
            db.add(user)
            await db.commit()
    """
    async with test_session_factory() as session:
        # Start a transaction
        async with session.begin():
            yield session
            # Rollback is automatic when exiting the context
            await session.rollback()


# ===========================================
# TEST DATA FIXTURES
# ===========================================

@pytest_asyncio.fixture
async def test_tenant(db: AsyncSession) -> Tenant:
    """
    Creates a test tenant for multi-tenant testing.

    Returns:
        Tenant object with default test configuration
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

    Returns:
        User object
    """
    user = User(
        id=uuid4(),
        tenant_id=test_tenant.id,
        email="test@example.com",
        password_hash=hash_password("TestPassword123!"),
        name="Test User",
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

    Returns:
        Tenant object (different from test_tenant)
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

    Returns:
        User object in test_tenant_2
    """
    user = User(
        id=uuid4(),
        tenant_id=test_tenant_2.id,
        email="test2@example.com",
        password_hash=hash_password("TestPassword123!"),
        name="Test User 2",
        role=UserRole.USER,
        is_active=True,
        is_verified=True,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


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

    Usage:
        def test_expired_token(generate_token):
            token = generate_token(expires_delta_seconds=-60)
            # Use expired token in test

    Returns:
        Function that generates JWT tokens
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
    ) -> str:
        """
        Generate a JWT token with custom properties.

        Args:
            user_id: User ID (generates random if None)
            tenant_id: Tenant ID (generates random if None)
            email: User email
            role: User role
            expires_delta_seconds: Expiry in seconds (None = default, negative = expired)
            secret_key: Custom secret key (for testing invalid signatures)
            algorithm: JWT algorithm (default: HS256)
            extra_claims: Additional claims to include in payload

        Returns:
            JWT token string
        """
        if user_id is None:
            user_id = uuid4()
        if tenant_id is None:
            tenant_id = uuid4()

        # Calculate expiration
        if expires_delta_seconds is None:
            # Default expiration (24 hours)
            expire = datetime.utcnow() + timedelta(hours=24)
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
            "type": "access"
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


@pytest_asyncio.fixture
async def get_auth_headers(test_user: User, test_tenant: Tenant, generate_token: Callable) -> Callable:
    """
    Factory fixture to generate authentication headers for API requests.

    Creates valid JWT tokens for the test user.

    Usage:
        async def test_authenticated_endpoint(client, get_auth_headers):
            headers = await get_auth_headers()
            response = await client.get("/projects/", headers=headers)
            assert response.status_code == 200

    Returns:
        Async function that returns auth headers dict
    """
    async def _get_headers(
        user: User | None = None,
        tenant: Tenant | None = None,
    ) -> dict[str, str]:
        """
        Generate authentication headers.

        Args:
            user: User object (defaults to test_user)
            tenant: Tenant object (defaults to test_tenant)

        Returns:
            Dictionary with Authorization header
        """
        u = user or test_user
        t = tenant or test_tenant

        token = generate_token(
            user_id=u.id,
            tenant_id=t.id,
            email=u.email,
            role=u.role.value,
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

    Returns:
        FastAPI application instance
    """
    return create_application()


@pytest_asyncio.fixture
async def client(app, db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Creates an HTTP client for testing API endpoints.

    The client is configured to use the test database session.

    Usage:
        async def test_endpoint(client: AsyncClient):
            response = await client.get("/health")
            assert response.status_code == 200

    Returns:
        AsyncClient configured for testing
    """
    # Override the database dependency to use test database
    async def override_get_session():
        yield db

    app.dependency_overrides[get_session] = override_get_session

    # Create async client
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver"
    ) as test_client:
        yield test_client

    # Clean up overrides
    app.dependency_overrides.clear()


# ===========================================
# UTILITY FIXTURES
# ===========================================

@pytest.fixture
def clean_tables() -> list[str]:
    """
    Returns list of tables to clean between tests.

    Useful for tests that need explicit cleanup.
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

    Usage:
        async def test_with_clean_db(clean_db, db):
            # Database is clean before this test
            pass
    """
    for table in clean_tables:
        try:
            await db.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            await db.commit()
        except Exception:
            # Table might not exist yet
            await db.rollback()
            pass
