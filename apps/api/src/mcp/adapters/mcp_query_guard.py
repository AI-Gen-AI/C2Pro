
import abc
import asyncio
from typing import Any, List, NamedTuple, AsyncIterator

from pydantic import BaseModel, Field

# DTOs and Ports
class QueryGuardConfig(BaseModel):
    """Configuration for query guard limits."""
    max_execution_time_seconds: int = Field(5, gt=0, description="Maximum seconds a query is allowed to run.")
    max_rows_returned: int = Field(1000, gt=0, description="Maximum number of rows to return from a query.")

class QueryResult(NamedTuple):
    """Result of a guarded query execution."""
    data: List[Any]      # The list of results (rows)
    truncated: bool      # True if the results were truncated due to row limit
    timed_out: bool      # True if the query was cancelled due to timeout

class MCPQueryExecutor(abc.ABC):
    """
    Port for executing actual MCP queries.
    Concrete implementations will interact with the underlying query engine.
    """
    @abc.abstractmethod
    async def execute_query(self, query: str) -> AsyncIterator[Any] | List[Any]:
        """
        Executes a query and returns its results.
        Can return an AsyncIterator for streaming results or a complete List.
        """
        raise NotImplementedError

class AuditService(abc.ABC):
    """
    Port for auditing query guard actions.
    """
    @abc.abstractmethod
    async def log_query_timeout(self, tenant_id: str, query: str, timeout_seconds: int) -> None:
        """Logs that a query timed out."""
        raise NotImplementedError

    @abc.abstractmethod
    async def log_query_row_limit(self, tenant_id: str, query: str, row_limit: int) -> None:
        """Logs that a query hit the row limit and was truncated."""
        raise NotImplementedError

# Implementation
class MCPQueryGuard:
    """
    Guards MCP query execution by enforcing time and row limits.
    """
    def __init__(self, query_executor: MCPQueryExecutor, audit_service: AuditService):
        if not isinstance(query_executor, MCPQueryExecutor):
            raise TypeError("query_executor must be an implementation of MCPQueryExecutor")
        if not isinstance(audit_service, AuditService):
            raise TypeError("audit_service must be an implementation of AuditService")
            
        self.query_executor = query_executor
        self.audit_service = audit_service

    async def execute_query(self, tenant_id: str, query: str, config: QueryGuardConfig) -> QueryResult:
        """
        Executes a query, applying time and row limits.
        
        Args:
            tenant_id: The ID of the tenant initiating the query.
            query: The query string to execute.
            config: The QueryGuardConfig specifying limits for this query.
            
        Returns:
            A QueryResult object containing the data, and flags for truncation/timeout.
        """
        results: List[Any] = []
        timed_out = False
        truncated = False

        try:
            # Execute the query with a timeout
            query_task = self.query_executor.execute_query(query)

            # Check if query_task is an async generator or a direct awaitable
            if asyncio.iscoroutine(query_task) or asyncio.isfuture(query_task):
                # If it's a direct awaitable, wrap it to handle row limits
                raw_results = await asyncio.wait_for(query_task, timeout=config.max_execution_time_seconds)
                for item in raw_results:
                    if len(results) < config.max_rows_returned:
                        results.append(item)
                    else:
                        truncated = True
                        break
            elif hasattr(query_task, '__aiter__'): # It's an async generator
                async with asyncio.timeout(config.max_execution_time_seconds):
                    async for item in query_task:
                        if len(results) < config.max_rows_returned:
                            results.append(item)
                        else:
                            truncated = True
                            break
            else:
                raise TypeError("Unsupported return type from query_executor.execute_query")

        except asyncio.TimeoutError:
            timed_out = True
            await self.audit_service.log_query_timeout(tenant_id, query, config.max_execution_time_seconds)
        except Exception as e:
            # Handle other potential exceptions from query execution
            print(f"Error executing query: {e}")
            raise # Re-raise for now, or handle specifically

        if truncated:
            await self.audit_service.log_query_row_limit(tenant_id, query, config.max_rows_returned)

        return QueryResult(data=results, truncated=truncated, timed_out=timed_out)
