"""
Audit Repository Integration Tests (TDD - RED Phase)

Refers to Suite ID: TS-INT-DB-AUD-001.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from src.core import database as core_database
from src.core.database import Base, get_session_with_tenant
from src.core.security.audit_trail import AuditTrail
from src.core.security.adapters.persistence.audit_repository import SQLAlchemyAuditRepository
from src.core.security.adapters.persistence.models import AuditLogORM


@pytest_asyncio.fixture(scope="session")
async def pg_engine():
    container = PostgresContainer("postgres:15-alpine")
    container.start()
    engine = None
    try:
        url = container.get_connection_url()
        url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(
            url,
            echo=False,
            poolclass=NullPool,
            connect_args={"statement_cache_size": 0},
        )
        core_database._engine = engine
        core_database._session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
    finally:
        core_database._engine = None
        core_database._session_factory = None
        if engine is not None:
            await engine.dispose()
        container.stop()


@pytest_asyncio.fixture
async def session(pg_engine) -> AsyncSession:
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        yield db


@pytest.mark.asyncio
async def test_audit_repository_persists_and_filters_by_tenant(session: AsyncSession):
    """
    Audit repository should persist events and filter by tenant.
    """
    trail = AuditTrail(lambda: datetime(2026, 2, 7, 12, 0, tzinfo=timezone.utc))
    tenant_a = str(uuid4())
    tenant_b = str(uuid4())

    event_a = trail.record(
        tenant_id=tenant_a,
        actor_id="user-a",
        action="create_document",
        resource_type="document",
        resource_id=str(uuid4()),
        metadata={"ip": "127.0.0.1"},
    )
    event_b = trail.record(
        tenant_id=tenant_b,
        actor_id="user-b",
        action="delete_project",
        resource_type="project",
        resource_id=str(uuid4()),
        metadata={"ip": "10.0.0.2"},
    )

    repo = SQLAlchemyAuditRepository(session)
    created_a = await repo.create(event_a)
    created_b = await repo.create(event_b)
    await session.commit()

    assert created_a.event_id == event_a.event_id
    assert created_b.event_id == event_b.event_id

    events_a = await repo.list_by_tenant(tenant_a)
    assert len(events_a) == 1
    assert events_a[0].tenant_id == tenant_a
    assert events_a[0].action == "create_document"

    async with get_session_with_tenant(tenant_b) as tenant_b_session:
        tenant_b_repo = SQLAlchemyAuditRepository(tenant_b_session)
        events_b = await tenant_b_repo.list_by_tenant(tenant_b)
        assert len(events_b) == 1
        assert events_b[0].tenant_id == tenant_b
