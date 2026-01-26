"""
Configuración global de pytest para todos los tests.

Configura variables de entorno y fixtures compartidos.
"""

import os
import sys
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy import event

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

# Configurar variables de entorno antes de importar la app
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEBUG", "true")

# Database (usa PostgreSQL de test si está disponible, fallback a SQLite)
# IMPORTANT: Use nonsuperuser instead of test to properly enforce RLS in tests
os.environ.setdefault("DATABASE_URL", "postgresql://nonsuperuser:test@localhost:5433/c2pro_test")

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
# IMPORT ALL MODELS (CRITICAL FOR SQLALCHEMY)
# ===========================================
# Import all models here to ensure they are registered with SQLAlchemy
# before any tests try to use them. This prevents relationship resolution errors.
from src.modules.auth.models import Tenant, User


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
# Esto asegura que cada test tenga su propio event loop
pytest_plugins = ("pytest_asyncio",)


# ===========================================
# DATABASE FIXTURES
# ===========================================


@pytest.fixture(scope="function")
async def db_engine():
    """
    Crea engine de base de datos para tests.

    Usa SQLite en memoria si PostgreSQL no está disponible.

    Scope: function - evita problemas de event loop entre tests.
    Cada test recibe un engine limpio.
    """
    from sqlalchemy.exc import OperationalError

    from src.config import settings

    # Intentar conectar a PostgreSQL
    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    try:
        if database_url.startswith("sqlite"):
            engine = create_async_engine(
                database_url,
                echo=False,
            )
            # Crear tablas en SQLite in-memory
            from src.core.database import Base

            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        else:
            engine = create_async_engine(
                database_url,
                echo=False,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
            )

            # Test connection
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

        yield engine
        await engine.dispose()

    except (OperationalError, OSError):
        # Fallback to SQLite in memory
        print("\n⚠️  PostgreSQL no disponible, usando SQLite en memoria")
        print("   Para ejecutar TODOS los tests, inicia PostgreSQL con:")
        print("   docker-compose -f docker-compose.test.yml up -d\n")

        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
        )

        # Crear todas las tablas
        from src.core.database import Base

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield engine
        await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Crea sesión de base de datos para cada test.

    Usa transacciones anidadas con SAVEPOINT para aislar cada test.
    Al final hace rollback de todo, asegurando que los tests no interfieran entre sí.
    """
    # Crear conexión
    async with db_engine.connect() as connection:
        # Iniciar transacción externa
        transaction = await connection.begin()

        # Crear sesión enlazada a esta transacción
        async_session = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        async with async_session() as session:
            # Crear SAVEPOINT para transacción anidada
            nested = await connection.begin_nested()

            try:
                yield session
            finally:
                # Rollback de SAVEPOINT (descarta cambios del test)
                if nested.is_active:
                    await nested.rollback()

                # Rollback de transacción externa
                await transaction.rollback()


# ===========================================
# HTTP CLIENT FIXTURES
# ===========================================


@pytest.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Cliente HTTP AsyncClient para tests de API.

    Usa la app FastAPI sin inicializar BD (para tests unitarios).
    Para tests de integración, usar client_with_db.

    Scope: function - se crea un cliente nuevo para cada test.
    """
    from httpx import ASGITransport

    from src.main import create_application

    app = create_application()

    # LifespanManager maneja startup/shutdown events correctamente
    async with LifespanManager(app):
        # ASGITransport sin parámetro lifespan - manejado por LifespanManager
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,  # Timeout generoso para tests
        ) as ac:
            yield ac


# ===========================================
# AUTH FIXTURES
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


@pytest.fixture
def create_test_token():
    """
    Factory fixture para crear JWTs de test.

    Uso:
        token = create_test_token(user_id=user_id, tenant_id=tenant_id)
        refresh_token = create_test_token(user_id=user_id, tenant_id=tenant_id, token_type="refresh")
        token_expired = create_test_token(
            user_id=user_id,
            tenant_id=tenant_id,
            expires_delta=timedelta(seconds=-60)
        )
    """
    from jose import jwt

    from src.config import settings

    def _create_token(
        user_id: UUID,
        tenant_id: UUID,
        email: str = "test@example.com",
        role: str = "admin",
        secret_key: str | None = None,
        expires_delta: timedelta | None = None,
        token_type: str = "access",  # New parameter
    ) -> str:
        """
        Crea un JWT para tests.

        Args:
            user_id: ID del usuario
            tenant_id: ID del tenant
            email: Email del usuario
            role: Rol del usuario (admin, member)
            secret_key: Secret key custom (para tests de firma inválida)
            expires_delta: Delta de expiración (negativo para tokens expirados)
            token_type: Tipo de token (access o refresh)

        Returns:
            JWT string
        """
        if token_type == "access":
            if expires_delta is None:
                expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
        elif token_type == "refresh":
            if expires_delta is None:
                expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)
        else:
            raise ValueError("Invalid token_type. Must be 'access' or 'refresh'.")

        expire = datetime.utcnow() + expires_delta

        payload = {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "email": email,
            "role": role,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": token_type,  # Use the token_type parameter
        }

        key = secret_key or settings.jwt_secret_key

        return jwt.encode(payload, key, algorithm=settings.jwt_algorithm)

    return _create_token


@pytest.fixture
def get_auth_headers(create_test_token, test_user_id, test_tenant_id):
    """
    Factory fixture para crear headers de autenticación.

    Uso:
        headers = get_auth_headers()
        headers_custom = get_auth_headers(user_id=custom_user_id)
    """

    def _get_headers(
        user_id: UUID | None = None,
        tenant_id: UUID | None = None,
        email: str = "test@example.com",
        role: str = "admin",
    ) -> dict[str, str]:
        """
        Genera headers de autenticación con JWT válido.

        Args:
            user_id: ID del usuario (usa test_user_id por defecto)
            tenant_id: ID del tenant (usa test_tenant_id por defecto)
            email: Email del usuario
            role: Rol del usuario

        Returns:
            Dict con headers incluyendo Authorization
        """
        token = create_test_token(
            user_id=user_id or test_user_id,
            tenant_id=tenant_id or test_tenant_id,
            email=email,
            role=role,
        )

        return {"Authorization": f"Bearer {token}"}

    return _get_headers


@pytest.fixture
async def create_test_user_and_tenant(db_session):
    """
    Factory fixture para crear un Tenant y un User asociados en la base de datos.

    Uso:
        user, tenant = await create_test_user_and_tenant("Test Tenant", "test@user.com")
        user2, tenant2 = await create_test_user_and_tenant("Another Tenant", "another@user.com")
    """

    async def _create(tenant_name: str, user_email: str) -> (User, Tenant):
        tenant_id = uuid4()
        user_id = uuid4()

        tenant = Tenant(id=tenant_id, name=tenant_name)
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        user = User(
            id=user_id,
            email=user_email,
            tenant_id=tenant_id,
            hashed_password="hashedpassword",  # Dummy password for test user
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        return user, tenant

    return _create


# ===========================================
# SUPERUSER CLEANUP FIXTURES (for RLS testing)
# ===========================================


@pytest.fixture(scope="function")
async def superuser_cleanup_engine():
    """
    Create a database engine using the SUPERUSER account for test cleanup.

    This engine is used ONLY for cleanup operations in finally blocks.
    It bypasses RLS policies to ensure complete cleanup of test data.

    IMPORTANT: Test execution uses 'nonsuperuser' to properly enforce RLS.
               Cleanup uses 'test' (superuser) to bypass RLS restrictions.

    Scope: function - created fresh for each test to avoid event loop issues
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
        pool_size=2,  # Small pool for cleanup only
        max_overflow=0,
    )

    yield cleanup_engine
    await cleanup_engine.dispose()


@pytest.fixture
async def cleanup_database(superuser_cleanup_engine):
    """
    Helper fixture to clean up test data using superuser connection.

    Usage in tests:
        async with cleanup_database() as cleanup:
            await cleanup(
                projects=[project_id],
                users=[user_a_id, user_b_id],
                tenants=[tenant_id]
            )

    Args:
        superuser_cleanup_engine: Engine with superuser permissions

    Yields:
        Async context manager for cleanup operations
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    async def _cleanup(**entity_ids):
        """
        Clean up test data by entity type.

        Args:
            **entity_ids: Dictionary of entity_type -> list of IDs
                          e.g., projects=[id1, id2], users=[id3]
        """
        async with AsyncSession(superuser_cleanup_engine) as session:
            # Cleanup order: respect foreign key constraints
            cleanup_order = ["documents", "projects", "users", "tenants"]

            for table in cleanup_order:
                ids = entity_ids.get(table, [])
                if ids:
                    # Convert single ID to list
                    if not isinstance(ids, list):
                        ids = [ids]

                    # Build parameterized query
                    if len(ids) == 1:
                        query = text(f"DELETE FROM {table} WHERE id = :id")
                        await session.execute(query, {"id": ids[0]})
                    else:
                        # Use ANY for multiple IDs
                        placeholders = ", ".join([f":id_{i}" for i in range(len(ids))])
                        query = text(f"DELETE FROM {table} WHERE id IN ({placeholders})")
                        params = {f"id_{i}": id_val for i, id_val in enumerate(ids)}
                        await session.execute(query, params)

            await session.commit()

    return _cleanup
