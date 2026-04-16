from datetime import timezone
"""
E2E Resilience Tests (TDD - RED Phase)

Refers to Suite IDs: TS-E2E-ERR-TIM-001, TS-E2E-ERR-CON-001, TS-E2E-ERR-REC-001.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from docker.errors import DockerException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

# ---------------------------------------------------------------------------
# Infrastructure: real DB container for optimistic locking tests
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def pg_engine():
    from src.core.database import Base
    from src.procurement.adapters.persistence.models import Base as ProcurementBase
    from src.procurement.adapters.persistence.models import WBSItemORM
    from src.projects.adapters.persistence.models import ProjectORM

    engine = None
    container = None
    try:
        container = PostgresContainer("postgres:15-alpine")
        container.start()
    except DockerException as exc:
        pytest.skip(f"Docker unavailable for resilience DB tests: {exc}", allow_module_level=False)

    try:
        raw_url = container.get_connection_url()
        url = re.sub(r"^postgresql(\+\w+)?://", "postgresql+asyncpg://", raw_url, count=1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=[ProjectORM.__table__])
            await conn.run_sync(ProcurementBase.metadata.create_all, tables=[WBSItemORM.__table__])
        yield engine
    finally:
        if engine is not None:
            async with engine.begin() as conn:
                await conn.execute(text("DROP TABLE IF EXISTS procurement_wbs_items CASCADE"))
                await conn.run_sync(Base.metadata.drop_all, tables=[ProjectORM.__table__])
            await engine.dispose()
        if container is not None:
            container.stop()


@pytest_asyncio.fixture
async def session(pg_engine) -> AsyncSession:
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        yield db


# ---------------------------------------------------------------------------
# TS-E2E-ERR-TIM-001: Timeout & Fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_timeout_returns_fallback_status(mocker):
    """
    Simulate slow LLM (>30s) and assert fallback/retry response.
    """
    from src.core.ai.llm_timeout_handler import LLMTimeoutService

    llm_client = mocker.AsyncMock()

    async def slow_call(*_args, **_kwargs):
        await asyncio.sleep(31)
        return {"content": "late"}

    llm_client.generate.side_effect = slow_call

    service = LLMTimeoutService(llm_client=llm_client, timeout_seconds=30)
    result = await service.generate_with_fallback(prompt="hello")

    assert result["status"] == "fallback_retry"


# ---------------------------------------------------------------------------
# TS-E2E-ERR-CON-001: Concurrent Modifications (Optimistic Locking)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_optimistic_locking_on_wbs_item(session: AsyncSession):
    """
    User A updates v1 -> v2, User B tries v1 -> must fail with 409.
    """
    from src.core.exceptions import ConflictError
    from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
    from src.procurement.application.dtos import WBSItemUpdate
    from src.procurement.application.use_cases.wbs_use_cases import UpdateWBSItemUseCase
    from src.procurement.domain.models import WBSItem
    from src.projects.adapters.persistence.models import ProjectORM

    repo = SQLAlchemyWBSRepository(session)

    wbs_id = uuid4()
    tenant_id = uuid4()
    project_id = uuid4()
    root_code = f"1-{uuid4().hex[:6]}"

    project = ProjectORM(
        id=project_id,
        tenant_id=tenant_id,
        name="Concurrency Project",
        description=None,
        code=f"P-{uuid4().hex[:6]}",
        project_type="construction",
        status="draft",
        estimated_budget=1000.0,
        currency="EUR",
        start_date=None,
        end_date=None,
        coherence_score=None,
        last_analysis_at=None,
        metadata_json={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(project)
    await session.commit()

    seeded = await repo.create(
        WBSItem(
            id=wbs_id,
            project_id=project_id,
            code=root_code,
            name="Original WBS",
            level=1,
        )
    )

    # User A fetches v1
    item_v1_a = await repo.get_by_id(wbs_id, tenant_id)
    # User B fetches v1
    item_v1_b = await repo.get_by_id(wbs_id, tenant_id)

    assert item_v1_a is not None
    assert item_v1_b is not None
    assert seeded.id == wbs_id

    # User A updates -> v2
    use_case = UpdateWBSItemUseCase(repo)
    await use_case.execute(
        wbs_id=wbs_id,
        wbs_update=WBSItemUpdate(name="Updated by A", expected_version=item_v1_a.version),
        tenant_id=tenant_id,
    )

    # User B tries to update v1 -> must fail
    with pytest.raises(ConflictError):
        await use_case.execute(
            wbs_id=wbs_id,
            wbs_update=WBSItemUpdate(name="Updated by B", expected_version=item_v1_b.version),
            tenant_id=tenant_id,
        )


# ---------------------------------------------------------------------------
# TS-E2E-ERR-REC-001: Dead Letter Queue Replay
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dead_letter_queue_replay_flow():
    """
    Simulate a Celery task failure -> DLQ -> Replay success.
    """
    from src.core.events.dead_letter_queue import DeadLetterQueue
    from src.core.events.replay import DLQReplayService

    dlq = DeadLetterQueue()
    task_id = str(uuid4())
    payload = {"document_id": str(uuid4()), "tenant_id": str(uuid4())}

    await dlq.enqueue(task_id=task_id, payload=payload, error="boom")

    assert await dlq.size() == 1

    replay_service = DLQReplayService(dlq=dlq)
    result = await replay_service.replay_next()

    assert result["status"] == "replayed"
    assert await dlq.size() == 0
