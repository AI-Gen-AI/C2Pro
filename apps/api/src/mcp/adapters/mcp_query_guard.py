"""
TS-UC-SEC-MCP-003: MCP Gateway query guard adapter.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, AsyncIterator, NamedTuple, Protocol

from pydantic import BaseModel, Field


class QueryGuardConfig(BaseModel):
    """Refers to Suite ID: TS-UC-SEC-MCP-003."""

    max_execution_time_seconds: float = Field(5.0, gt=0)
    max_rows_returned: int = Field(1000, gt=0)


class QueryResult(NamedTuple):
    """Refers to Suite ID: TS-UC-SEC-MCP-003."""

    data: list[Any]
    truncated: bool
    timed_out: bool


class MCPQueryExecutor(Protocol):
    """Refers to Suite ID: TS-UC-SEC-MCP-003."""

    async def execute_query(self, query: str) -> AsyncIterator[Any] | list[Any]: ...


class AuditService(Protocol):
    """Refers to Suite ID: TS-UC-SEC-MCP-003."""

    async def log_query_timeout(self, tenant_id: str, query: str, timeout_seconds: float) -> None: ...

    async def log_query_row_limit(self, tenant_id: str, query: str, row_limit: int) -> None: ...


class MCPQueryGuard:
    """Refers to Suite ID: TS-UC-SEC-MCP-003."""

    def __init__(self, query_executor: MCPQueryExecutor, audit_service: AuditService) -> None:
        self.query_executor = query_executor
        self.audit_service = audit_service

    async def execute_query(self, tenant_id: str, query: str, config: QueryGuardConfig) -> QueryResult:
        if not tenant_id:
            raise ValueError("Tenant ID cannot be empty or None")
        if not query:
            raise ValueError("Query cannot be empty or None")

        try:
            raw_result = self.query_executor.execute_query(query)
            if inspect.isawaitable(raw_result):
                resolved = await asyncio.wait_for(
                    raw_result, timeout=config.max_execution_time_seconds
                )
                if hasattr(resolved, "__aiter__"):
                    data, truncated, timed_out = await self._collect_from_stream(
                        resolved, config.max_execution_time_seconds, config.max_rows_returned
                    )
                else:
                    data, truncated = self._truncate_rows(list(resolved), config.max_rows_returned)
                    timed_out = False
            elif hasattr(raw_result, "__aiter__"):
                data, truncated, timed_out = await self._collect_from_stream(
                    raw_result, config.max_execution_time_seconds, config.max_rows_returned
                )
            else:
                data, truncated = self._truncate_rows(list(raw_result), config.max_rows_returned)
                timed_out = False
        except asyncio.TimeoutError:
            await self.audit_service.log_query_timeout(
                tenant_id, query, config.max_execution_time_seconds
            )
            return QueryResult(data=[], truncated=False, timed_out=True)

        if timed_out:
            await self.audit_service.log_query_timeout(
                tenant_id, query, config.max_execution_time_seconds
            )
        if truncated:
            await self.audit_service.log_query_row_limit(
                tenant_id, query, config.max_rows_returned
            )
        return QueryResult(data=data, truncated=truncated, timed_out=timed_out)

    @staticmethod
    def _truncate_rows(rows: list[Any], max_rows: int) -> tuple[list[Any], bool]:
        if len(rows) <= max_rows:
            return rows, False
        return rows[:max_rows], True

    async def _collect_from_stream(
        self,
        stream: AsyncIterator[Any],
        timeout_seconds: float,
        max_rows: int,
    ) -> tuple[list[Any], bool, bool]:
        data: list[Any] = []
        truncated = False
        iterator = stream.__aiter__()
        deadline = asyncio.get_running_loop().time() + timeout_seconds

        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return data, truncated, True
            try:
                item = await asyncio.wait_for(anext(iterator), timeout=remaining)
            except StopAsyncIteration:
                return data, truncated, False
            except asyncio.TimeoutError:
                return data, truncated, True

            if len(data) < max_rows:
                data.append(item)
            else:
                truncated = True
                return data, truncated, False
