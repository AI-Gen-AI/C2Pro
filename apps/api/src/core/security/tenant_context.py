"""
Tenant context and cache isolation helpers.

Refers to Suite ID: TS-UC-SEC-TNT-001.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


class TenantIsolationError(PermissionError):
    """
    Raised when code tries to access data from a tenant outside current context.
    """


class CacheBackend(Protocol):
    """Minimal cache backend protocol for tenant-scoped wrapper."""

    def get(self, key: str) -> Any: ...

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None: ...

    def delete(self, key: str) -> None: ...


@dataclass(slots=True)
class TenantContext:
    """
    Holds the current tenant in a ContextVar for request/task-level isolation.
    """

    _current_tenant: ContextVar[UUID | None] = ContextVar(
        "c2pro_current_tenant",
        default=None,
    )

    def set_current_tenant(self, tenant_id: UUID) -> Token[UUID | None]:
        return self._current_tenant.set(tenant_id)

    def get_current_tenant(self) -> UUID | None:
        return self._current_tenant.get()

    def require_current_tenant(self) -> UUID:
        tenant_id = self.get_current_tenant()
        if tenant_id is None:
            raise TenantIsolationError("No tenant in execution context.")
        return tenant_id

    def reset(self, token: Token[UUID | None]) -> None:
        self._current_tenant.reset(token)


@dataclass(slots=True)
class TenantScopedCache:
    """
    Cache adapter that enforces tenant ownership before backend reads/writes.
    """

    context: TenantContext
    backend: CacheBackend

    def _assert_tenant_scope(self, tenant_id: UUID) -> None:
        current_tenant = self.context.require_current_tenant()
        if tenant_id != current_tenant:
            raise TenantIsolationError(
                f"Cross-tenant access denied. expected={current_tenant}, got={tenant_id}",
            )

    def _scoped_key(self, tenant_id: UUID, key: str) -> str:
        return f"{tenant_id}:{key}"

    def get(self, tenant_id: UUID, key: str) -> Any:
        self._assert_tenant_scope(tenant_id)
        return self.backend.get(self._scoped_key(tenant_id, key))

    def set(self, tenant_id: UUID, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        self._assert_tenant_scope(tenant_id)
        self.backend.set(self._scoped_key(tenant_id, key), value, ttl_seconds=ttl_seconds)

    def delete(self, tenant_id: UUID, key: str) -> None:
        self._assert_tenant_scope(tenant_id)
        self.backend.delete(self._scoped_key(tenant_id, key))
