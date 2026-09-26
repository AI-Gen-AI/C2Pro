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

    # Strengthen: prove actual SQLAlchemy statement semantics
    assert session_mock.execute.call_count == 1
    stmt = session_mock.execute.call_args[0][0]

    # 1. LIMIT is the requested limit
    assert stmt._limit == 10
    # 2. OFFSET is the requested offset
    assert stmt._offset == 5

    # 3. status predicate is present and binds requested status
    where_clauses = list(stmt._where_criteria)
    assert len(where_clauses) == 1
    clause = where_clauses[0]
    assert clause.left.name == "status"
    assert clause.right.value == "pending"

    # 4. ordering contract is present (created_at DESC)
    order_clauses = list(stmt._order_by_clauses)
    assert len(order_clauses) == 1
    order_clause = order_clauses[0]
    assert order_clause.element.name == "created_at"
    assert "desc" in str(order_clause.modifier).lower()


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

    # Strengthen: prove actual SQLAlchemy statement semantics
    assert session_mock.execute.call_count == 1
    stmt = session_mock.execute.call_args[0][0]

    # 1. count query semantics are correct (selected columns/functions and tables)
    selected = list(stmt.selected_columns)
    assert len(selected) == 1
    assert str(selected[0]) == "count(*)"

    froms = list(stmt.get_final_froms())
    assert len(froms) == 1
    assert froms[0].name == "dlq_failed_tasks"

    # 2. status predicate is present
    where_clauses = list(stmt._where_criteria)
    assert len(where_clauses) == 1
    clause = where_clauses[0]
    assert clause.left.name == "status"
    assert clause.right.value == "pending"


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

    # Strengthen: prove actual SQLAlchemy statement semantics
    assert session_mock.execute.call_count == 1
    stmt = session_mock.execute.call_args[0][0]

    # 1. ID predicate is present and uses requested dlq_id
    where_clauses = list(stmt._where_criteria)
    assert len(where_clauses) == 1
    clause = where_clauses[0]
    assert clause.left.name == "id"
    assert clause.right.value == dlq_id

    # 2. Selecting DLQFailedTask
    froms = list(stmt.get_final_froms())
    assert len(froms) == 1
    assert froms[0].name == "dlq_failed_tasks"


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

    dlq_id = uuid4()
    entry = await adapter.get_by_id(dlq_id)
    assert entry is None

    # Strengthen: prove actual SQLAlchemy statement semantics
    assert session_mock.execute.call_count == 1
    stmt = session_mock.execute.call_args[0][0]

    # 1. ID predicate is present and uses requested dlq_id
    where_clauses = list(stmt._where_criteria)
    assert len(where_clauses) == 1
    clause = where_clauses[0]
    assert clause.left.name == "id"
    assert clause.right.value == dlq_id


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

    # MEDIUM 2: Prove that the SELECT used to locate the DLQ row is constrained by the requested ID
    assert session_mock.execute.call_count == 1
    stmt = session_mock.execute.call_args[0][0]
    where_clauses = list(stmt._where_criteria)
    assert len(where_clauses) == 1
    clause = where_clauses[0]
    assert clause.left.name == "id"
    assert clause.right.value == dlq_id


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

    # MEDIUM 2: Prove that the SELECT used to locate the DLQ row is constrained by the requested ID
    assert session_mock.execute.call_count == 1
    stmt = session_mock.execute.call_args[0][0]
    where_clauses = list(stmt._where_criteria)
    assert len(where_clauses) == 1
    clause = where_clauses[0]
    assert clause.left.name == "id"
    assert clause.right.value == dlq_id


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

    # MEDIUM 2: Prove that the SELECT used to locate the DLQ row is constrained by the requested ID
    assert session_mock.execute.call_count == 1
    stmt = session_mock.execute.call_args[0][0]
    where_clauses = list(stmt._where_criteria)
    assert len(where_clauses) == 1
    clause = where_clauses[0]
    assert clause.left.name == "id"
    assert clause.right.value == dlq_id
