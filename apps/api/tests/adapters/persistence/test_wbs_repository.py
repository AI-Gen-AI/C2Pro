
"""
WBS Repository Integration Tests (TDD - RED Phase)

The repository reads and writes the canonical Project Controls WBS (``wbs_nodes``, ADR-025).

Refers to Suite ID: TS-INT-DB-WBS-001.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from docker.errors import DockerException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from src.core import database as core_database
from src.core.database import Base, get_session_with_tenant
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.domain.models import WBSItem
from src.projects.adapters.persistence.models import ProjectORM
from src.wbs.adapters.persistence.models import WBSNodeORM


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
            await conn.run_sync(Base.metadata.create_all, tables=[ProjectORM.__table__])
            # Minimal FK-target stubs for WBSNodeORM.tenant_id -> tenants.id and
            # WBSNodeORM.source_document_id -> documents.id.
            await conn.execute(text("CREATE TABLE IF NOT EXISTS tenants (id uuid PRIMARY KEY)"))
            await conn.execute(text("CREATE TABLE IF NOT EXISTS documents (id uuid PRIMARY KEY)"))
            await conn.run_sync(Base.metadata.create_all, tables=[WBSNodeORM.__table__])
        yield engine
    finally:
        core_database._engine = None
        core_database._session_factory = None
        if engine is not None:
            await engine.dispose()
        if container is not None:
            container.stop()


@pytest_asyncio.fixture
async def session(pg_engine) -> AsyncSession:
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        yield db


def _project(tenant_id, code: str) -> ProjectORM:
    return ProjectORM(
        id=uuid4(),
        tenant_id=tenant_id,
        name="Tenant A Project",
        description=None,
        code=code,
        project_type="construction",
        status="draft",
        estimated_budget=1000.0,
        currency="EUR",
        start_date=None,
        end_date=None,
        coherence_score=None,
        last_analysis_at=None,
        metadata_json={},
        created_at=datetime.now(UTC).replace(tzinfo=None),
        updated_at=datetime.now(UTC).replace(tzinfo=None),
    )


async def _seed_tenants(session: AsyncSession, *tenant_ids) -> None:
    for tenant_id in tenant_ids:
        await session.execute(text("INSERT INTO tenants (id) VALUES (:id)"), {"id": tenant_id})


@pytest.mark.asyncio
async def test_wbs_tree_hierarchy_and_tenant_filtering(session: AsyncSession):
    """
    WBS tree retrieval should include parent/child and enforce tenant isolation.
    """
    tenant_a = uuid4()
    tenant_b = uuid4()
    await _seed_tenants(session, tenant_a, tenant_b)
    project_a = _project(tenant_a, f"A-{uuid4().hex[:6]}")
    session.add(project_a)
    await session.commit()

    # Seed the canonical nested-set hierarchy directly to test repository tree building
    root_code = f"1-{uuid4().hex[:6]}"
    child_code = f"{root_code}.1"
    parent = WBSNodeORM(
        id=uuid4(),
        project_id=project_a.id,
        tenant_id=tenant_a,
        code=root_code,
        name="Root",
        lft=1,
        rgt=4,
        depth=0,
    )
    session.add(parent)
    await session.commit()
    child = WBSNodeORM(
        id=uuid4(),
        project_id=project_a.id,
        tenant_id=tenant_a,
        parent_id=parent.id,
        code=child_code,
        name="Child",
        lft=2,
        rgt=3,
        depth=1,
    )
    session.add(child)
    await session.commit()

    repo = SQLAlchemyWBSRepository(session)
    tree = await repo.get_tree(project_id=project_a.id, tenant_id=tenant_a)
    assert len(tree) == 1
    assert tree[0].code == root_code
    assert tree[0].level == 1
    assert len(tree[0].children) == 1
    assert tree[0].children[0].code == child_code
    assert tree[0].children[0].parent_code == root_code
    assert tree[0].children[0].level == 2

    # Critical security test: tenant isolation via RLS/session context
    async with get_session_with_tenant(tenant_b) as tenant_b_session:
        tenant_b_repo = SQLAlchemyWBSRepository(tenant_b_session)
        tree_b = await tenant_b_repo.get_tree(project_id=project_a.id, tenant_id=tenant_b)
        assert tree_b == []


@pytest.mark.asyncio
async def test_wbs_bulk_create_rejects_project_outside_tenant(session: AsyncSession):
    """
    WBS bulk_create should reject writes when the project is outside the caller tenant.
    """
    tenant_a = uuid4()
    tenant_b = uuid4()
    await _seed_tenants(session, tenant_a, tenant_b)
    project_a = _project(tenant_a, f"A-{uuid4().hex[:6]}")
    session.add(project_a)
    await session.commit()

    repo = SQLAlchemyWBSRepository(session)
    items = [
        WBSItem(project_id=project_a.id, code="1", name="Root", level=1),
        WBSItem(project_id=project_a.id, code="1.1", name="Child", level=2, parent_code="1"),
    ]

    with pytest.raises(PermissionError, match="outside tenant"):
        await repo.bulk_create(items, tenant_b)
