"""
E2E Resilience Tests (TDD - RED Phase)

Refers to Suite IDs: TS-E2E-ERR-TIM-001, TS-E2E-ERR-CON-001, TS-E2E-ERR-REC-001.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer


# ---------------------------------------------------------------------------
# Infrastructure: real DB container for optimistic locking tests
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def pg_engine():
    container = PostgresContainer("postgres:15-alpine")
    container.start()
    try:
        url = container.get_connection_url().replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False)
        yield engine
    finally:
        await engine.dispose()
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
    from src.procurement.application.use_cases.wbs_use_cases import UpdateWBSItemUseCase
    from src.procurement.ports.wbs_repository import IWBSRepository
    from src.procurement.application.dtos import WBSItemUpdate
    from src.core.exceptions import ConflictError

    # NOTE: Actual repository and versioning logic must be implemented.
    repo = IWBSRepository(session)  # Expected to be real adapter in GREEN phase

    # Seed WBS item (v1)
    wbs_id = uuid4()
    tenant_id = uuid4()
    project_id = uuid4()

    # User A fetches v1
    item_v1_a = await repo.get_by_id(wbs_id, tenant_id)
    # User B fetches v1
    item_v1_b = await repo.get_by_id(wbs_id, tenant_id)

    # User A updates -> v2
    use_case = UpdateWBSItemUseCase(repo)
    await use_case.execute(
        wbs_id=wbs_id,
        wbs_update=WBSItemUpdate(name="Updated by A"),
        tenant_id=tenant_id,
    )

    # User B tries to update v1 -> must fail
    with pytest.raises(ConflictError):
        await use_case.execute(
            wbs_id=wbs_id,
            wbs_update=WBSItemUpdate(name="Updated by B"),
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
    from src.core.events.dlq import DeadLetterQueue
    from src.core.events.replay import DLQReplayService

    dlq = DeadLetterQueue()
    task_id = str(uuid4())
    payload = {"document_id": str(uuid4()), "tenant_id": str(uuid4())}

    await dlq.enqueue(task_id=task_id, payload=payload, error="boom")

    assert await dlq.size() == 1

    replay_service = DLQReplayService(dlq=dlq)
    result = await replay_service.replay(task_id=task_id)

    assert result["status"] == "replayed"
    assert await dlq.size() == 0
