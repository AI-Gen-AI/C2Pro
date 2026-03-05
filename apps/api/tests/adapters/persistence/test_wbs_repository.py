"""
WBS Repository Integration Tests (TDD - RED Phase)

Refers to Suite ID: TS-INT-DB-WBS-001.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from docker.errors import DockerException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from src.core.database import Base
from src.core.database import get_session_with_tenant
from src.core import database as core_database
from src.projects.adapters.persistence.models import ProjectORM
from src.procurement.adapters.persistence.models import Base as ProcurementBase, WBSItemORM
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.domain.models import WBSItem


@pytest_asyncio.fixture(scope="session")
async def pg_engine():
    try:
        container = PostgresContainer("postgres:15-alpine")
        container.start()
    except DockerException as exc:
        pytest.skip(f"Docker unavailable for testcontainers: {exc}")
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
            await conn.run_sync(ProcurementBase.metadata.create_all)
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
async def test_wbs_tree_hierarchy_and_tenant_filtering(session: AsyncSession):
    """
    WBS tree retrieval should include parent/child and enforce tenant isolation.
    """
    tenant_a = uuid4()
    tenant_b = uuid4()
    project_a = ProjectORM(
        id=uuid4(),
        tenant_id=tenant_a,
        name="Tenant A Project",
        description=None,
        code="A-1",
        project_type="construction",
        status="draft",
        estimated_budget=1000.0,
        currency="EUR",
        start_date=None,
        end_date=None,
        coherence_score=None,
        last_analysis_at=None,
        metadata_json={},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(project_a)
    await session.commit()

    # Seed ORM hierarchy directly to test repository tree building
    parent = WBSItemORM(
        id=uuid4(),
        project_id=project_a.id,
        code="1",
        name="Root",
        level=1,
    )
    child = WBSItemORM(
        id=uuid4(),
        project_id=project_a.id,
        code="1.1",
        name="Child",
        level=2,
        parent_code="1",
    )
    session.add_all([parent, child])
    await session.commit()

    repo = SQLAlchemyWBSRepository(session)
    tree = await repo.get_tree(project_id=project_a.id, tenant_id=tenant_a)
    assert len(tree) == 1
    assert tree[0].code == "1"
    assert len(tree[0].children) == 1
    assert tree[0].children[0].code == "1.1"

    # Critical security test: tenant isolation via RLS/session context
    async with get_session_with_tenant(tenant_b) as tenant_b_session:
        tenant_b_repo = SQLAlchemyWBSRepository(tenant_b_session)
        tree_b = await tenant_b_repo.get_tree(project_id=project_a.id, tenant_id=tenant_b)
        assert tree_b == []
