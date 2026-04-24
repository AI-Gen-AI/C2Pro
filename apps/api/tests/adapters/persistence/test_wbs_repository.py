
"""
WBS Repository Integration Tests (TDD - RED Phase)

Refers to Suite ID: TS-INT-DB-WBS-001.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from docker.errors import DockerException
from sqlalchemy import Column, Table
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from src.core import database as core_database
from src.core.database import Base, get_session_with_tenant
from src.procurement.adapters.persistence.models import Base as ProcurementBase
from src.procurement.adapters.persistence.models import WBSItemORM
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.domain.models import WBSItem
from src.projects.adapters.persistence.models import ProjectORM


def _ensure_test_fk_stub_tables() -> None:
    if "wbs_items" not in Base.metadata.tables:
        Table(
            "wbs_items",
            Base.metadata,
            Column("id", PGUUID(as_uuid=True), primary_key=True),
            extend_existing=True,
        )


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
            _ensure_test_fk_stub_tables()
            await conn.run_sync(Base.metadata.create_all, tables=[ProjectORM.__table__])
            await conn.run_sync(ProcurementBase.metadata.create_all, tables=[WBSItemORM.__table__])
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
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(project_a)
    await session.commit()

    # Seed ORM hierarchy directly to test repository tree building
    root_code = f"1-{uuid4().hex[:6]}"
    child_code = f"{root_code}.1"
    parent = WBSItemORM(
        id=uuid4(),
        project_id=project_a.id,
        code=root_code,
        name="Root",
        level=1,
    )
    child = WBSItemORM(
        id=uuid4(),
        project_id=project_a.id,
        code=child_code,
        name="Child",
        level=2,
        parent_code=root_code,
    )
    session.add_all([parent, child])
    await session.commit()

    repo = SQLAlchemyWBSRepository(session)
    tree = await repo.get_tree(project_id=project_a.id, tenant_id=tenant_a)
    assert len(tree) == 1
    assert tree[0].code == root_code
    assert len(tree[0].children) == 1
    assert tree[0].children[0].code == child_code

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

    project_a = ProjectORM(
        id=uuid4(),
        tenant_id=tenant_a,
        name="Tenant A Project",
        description=None,
        code="A-2",
        project_type="construction",
        status="draft",
        estimated_budget=1000.0,
        currency="EUR",
        start_date=None,
        end_date=None,
        coherence_score=None,
        last_analysis_at=None,
        metadata_json={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(project_a)
    await session.commit()

    repo = SQLAlchemyWBSRepository(session)
    items = [
        WBSItem(project_id=project_a.id, code="1", name="Root", level=1),
        WBSItem(project_id=project_a.id, code="1.1", name="Child", level=2, parent_code="1"),
    ]

    with pytest.raises(PermissionError, match="outside tenant"):
        await repo.bulk_create(items, tenant_b)
