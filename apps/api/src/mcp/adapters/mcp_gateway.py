"""
TS-UC-SEC-MCP-001: MCP Gateway allowlist adapter.
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any, Protocol
from uuid import UUID

from fastapi import HTTPException

from src.core.exceptions import RateLimitExceededError, SecurityException


class OperationAllowlistRepository(Protocol):
    """
    Port for fetching operation allowlists for a given tenant.
    Refers to Suite ID: TS-UC-SEC-MCP-001.
    """

    def get_allowlist_for_tenant(self, tenant_id: str) -> list[str]:
        """
        Retrieves the list of allowed operation names for a specific tenant.
        """


# Default operations that are always allowed
_DEFAULT_ALLOWLIST: set[str] = {
    "projects_summary",
    "project_details",
    "document_list",
    "document_details",
    "coherence_check",
    "alert_list",
    "alert_details",
}

# Operations that are always blocked
_DESTRUCTIVE_OPERATIONS: set[str] = {
    "delete_all",
    "drop_table",
    "drop_database",
}


class MCPGateway:
    """
    Gateway to the Master Control Program (MCP).
    Refers to Suite ID: TS-UC-SEC-MCP-001.
    """

    def __init__(
        self,
        config: Any = None,
        audit_logger: Any = None,
        allowlist_repo: OperationAllowlistRepository | None = None,
        time_provider: Callable[[], float] | None = None,
    ):
        self.config = config
        self.audit_logger = audit_logger
        self.allowlist_repo = allowlist_repo
        self._time_provider = time_provider or time.time
        # Track requests per tenant: {tenant_id: [timestamps]}
        self._request_log: dict[str, list[float]] = defaultdict(list)

    @property
    def _rate_limit(self) -> int:
        return getattr(self.config, 'rate_limit_per_minute', 60)

    @property
    def _max_rows(self) -> int:
        return getattr(self.config, 'max_rows', 1000)

    @property
    def _timeout_seconds(self) -> float:
        return getattr(self.config, 'timeout_seconds', 5.0)

    async def validate_operation(
        self,
        operation: str,
        tenant_id: UUID | str,
    ) -> bool:
        """
        Validates if a tenant is allowed to perform a given operation.

        Returns True if allowed, raises SecurityException if blocked,
        raises RateLimitExceededError if rate limit exceeded.
        """
        tenant_key = str(tenant_id)
        normalized_op = operation.strip().lower()

        # Check if operation is destructive / not allowlisted
        if normalized_op in _DESTRUCTIVE_OPERATIONS or normalized_op not in _DEFAULT_ALLOWLIST:
            if self.audit_logger:
                self.audit_logger.log_blocked_attempt(
                    tenant_id=tenant_id,
                    operation=operation,
                    reason="operation_not_allowlisted",
                )
            raise SecurityException(f"Operation '{operation}' is not allowed")

        # Check rate limit
        now = self._time_provider()
        window_start = now - 60.0
        # Clean old entries
        self._request_log[tenant_key] = [
            t for t in self._request_log[tenant_key] if t > window_start
        ]

        if len(self._request_log[tenant_key]) >= self._rate_limit:
            if self.audit_logger:
                self.audit_logger.log_blocked_attempt(
                    tenant_id=tenant_id,
                    operation=operation,
                    reason="rate_limit_exceeded",
                )
            raise RateLimitExceededError()

        self._request_log[tenant_key].append(now)
        return True

    async def authorize_tool_call(
        self,
        operation: str,
        tenant_id: UUID | str,
    ) -> bool:
        """
        Authorizes a tool call. Raises HTTPException 403 for unauthorized operations.

        Checks tenant-specific allowlist first, then falls back to default allowlist.
        """
        tenant_key = str(tenant_id)
        normalized_op = operation.strip().lower()

        # Block destructive operations unconditionally
        if normalized_op in _DESTRUCTIVE_OPERATIONS:
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: destructive operation '{operation}' is not allowed",
            )

        # Check tenant-specific allowlist if repository is configured
        if self.allowlist_repo:
            tenant_allowlist = self.allowlist_repo.get_allowlist_for_tenant(tenant_key)
            normalized_allowlist = {op.strip().lower() for op in tenant_allowlist}
            if normalized_op not in normalized_allowlist:
                raise HTTPException(
                    status_code=403,
                    detail=f"Forbidden: operation '{operation}' is not allowed for tenant",
                )
        elif normalized_op not in _DEFAULT_ALLOWLIST:
            # Only check default allowlist if no tenant-specific allowlist exists
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: operation '{operation}' is not authorized",
            )

        return True

    async def enforce_query_limits(
        self,
        row_count: int,
        duration_seconds: float,
    ) -> bool:
        """
        Enforces query result limits (max rows and timeout).

        Raises SecurityException if limits are exceeded.
        """
        if row_count > self._max_rows:
            raise SecurityException(
                f"Query returned {row_count} rows, exceeding limit of {self._max_rows}",
            )

        if duration_seconds > self._timeout_seconds:
            raise SecurityException(
                f"Query took {duration_seconds}s, exceeding limit of {self._timeout_seconds}s",
            )

        return True

    async def is_operation_allowed(self, tenant_id: str | None, operation_name: str | None) -> bool:
        """
        Validates if a tenant is allowed to perform a given operation.
        Legacy interface.
        """
        if not tenant_id:
            raise ValueError("Tenant ID cannot be empty or None")
        if not operation_name:
            raise ValueError("Operation name cannot be empty or None")

        normalized_operation = operation_name.strip().lower()

        if normalized_operation in _DESTRUCTIVE_OPERATIONS:
            return False

        if self.allowlist_repo:
            tenant_allowlist = self.allowlist_repo.get_allowlist_for_tenant(tenant_id)
            normalized_allowlist = {op.strip().lower() for op in tenant_allowlist}
            return normalized_operation in normalized_allowlist

        return normalized_operation in _DEFAULT_ALLOWLIST
