from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.admin.adapters.http.router import DLQAdminOpsAdapter
from src.core.dlq.models import DLQFailedTask


@pytest.mark.asyncio
async def test_adapter_list_by_status() -> None:
    adapter = DLQAdminOpsAdapter()
    session_mock = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield session_mock

    adapter._admin_session = fake_session

    mock_task = DLQFailedTask(
        id=uuid4(),
        tenant_id=uuid4(),
        status="pending",
        task_type="document_analysis",
        retry_count=1,
        max_retries=3,
        created_at=datetime.now(UTC),
    )

    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = [mock_task]
    session_mock.execute.return_value = execute_result

    res = await adapter.list_by_status("pending", limit=10, offset=5)

    assert len(res) == 1
    assert res[0] is mock_task
    session_mock.execute.assert_called_once()


@pytest.mark.asyncio
async def test_adapter_count_by_status() -> None:
    adapter = DLQAdminOpsAdapter()
    session_mock = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield session_mock

    adapter._admin_session = fake_session

    execute_result = MagicMock()
    execute_result.scalar_one.return_value = 42
    session_mock.execute.return_value = execute_result

    count = await adapter.count_by_status("pending")
    assert count == 42
    session_mock.execute.assert_called_once()


@pytest.mark.asyncio
async def test_adapter_get_by_id_existing() -> None:
    adapter = DLQAdminOpsAdapter()
    session_mock = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield session_mock

    adapter._admin_session = fake_session

    dlq_id = uuid4()
    mock_task = DLQFailedTask(
        id=dlq_id,
        tenant_id=uuid4(),
        status="pending",
        task_type="document_analysis",
        retry_count=1,
        max_retries=3,
        created_at=datetime.now(UTC),
    )

    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = mock_task
    session_mock.execute.return_value = execute_result

    entry = await adapter.get_by_id(dlq_id)
    assert entry is mock_task
    session_mock.execute.assert_called_once()


@pytest.mark.asyncio
async def test_adapter_get_by_id_missing() -> None:
    adapter = DLQAdminOpsAdapter()
    session_mock = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield session_mock

    adapter._admin_session = fake_session

    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    session_mock.execute.return_value = execute_result

    entry = await adapter.get_by_id(uuid4())
    assert entry is None
    session_mock.execute.assert_called_once()


@pytest.mark.asyncio
async def test_adapter_retry_below_max_retry() -> None:
    adapter = DLQAdminOpsAdapter()
    session_mock = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield session_mock

    adapter._admin_session = fake_session

    dlq_id = uuid4()
    mock_task = DLQFailedTask(
        id=dlq_id,
        tenant_id=uuid4(),
        status="pending",
        task_type="document_analysis",
        retry_count=1,
        max_retries=3,
        created_at=datetime.now(UTC),
    )

    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = mock_task
    session_mock.execute.return_value = execute_result

    await adapter.retry(dlq_id)

    assert mock_task.retry_count == 2
    assert mock_task.status == "retrying"
    assert mock_task.next_retry_at is not None
    time_diff = mock_task.next_retry_at - datetime.now(UTC)
    assert timedelta(minutes=3) < time_diff < timedelta(minutes=5)
    session_mock.commit.assert_called_once()


@pytest.mark.asyncio
async def test_adapter_retry_exhausted() -> None:
    adapter = DLQAdminOpsAdapter()
    session_mock = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield session_mock

    adapter._admin_session = fake_session

    dlq_id = uuid4()
    mock_task = DLQFailedTask(
        id=dlq_id,
        tenant_id=uuid4(),
        status="pending",
        task_type="document_analysis",
        retry_count=2,
        max_retries=3,
        created_at=datetime.now(UTC),
    )

    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = mock_task
    session_mock.execute.return_value = execute_result

    await adapter.retry(dlq_id)

    assert mock_task.retry_count == 3
    assert mock_task.status == "exhausted"
    assert mock_task.next_retry_at is None
    session_mock.commit.assert_called_once()


@pytest.mark.asyncio
async def test_adapter_retry_not_found() -> None:
    adapter = DLQAdminOpsAdapter()
    session_mock = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield session_mock

    adapter._admin_session = fake_session

    dlq_id = uuid4()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    session_mock.execute.return_value = execute_result

    with pytest.raises(ValueError, match=f"DLQ record {dlq_id} not found"):
        await adapter.retry(dlq_id)

    session_mock.commit.assert_not_called()
