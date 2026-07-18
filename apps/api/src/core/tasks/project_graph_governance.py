"""Cost governance for ADR-017 ProjectGraph tasks.

TS-UT-ADR017-GOV-001
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from src.config import settings
from src.core.cache import NAMESPACE_RATE_LIMIT, build_rate_limit_key, get_cache_service


class _CacheClient(Protocol):
    async def get(self, key: str, default: object | None = None) -> object | None: ...
    async def incr(
        self, key: str, *, ttl_seconds: int | None = ..., namespace: str | None = ...
    ) -> int: ...
    async def decr(self, key: str, *, amount: int = ..., namespace: str | None = ...) -> int: ...
    async def set_if_absent(
        self, key: str, value: Any, *, ttl_seconds: int, namespace: str | None = ...
    ) -> bool: ...
    async def delete(self, key: str) -> bool: ...


class ProjectGraphGovernance:
    def __init__(
        self,
        *,
        cache: _CacheClient | None = None,
        debounce_ttl_seconds: int | None = None,
        tenant_concurrency_limit: int | None = None,
        requeue_countdown_seconds: int | None = None,
    ) -> None:
        self._cache = cache if cache is not None else get_cache_service()
        self.debounce_ttl_seconds = (
            debounce_ttl_seconds
            if debounce_ttl_seconds is not None
            else settings.project_graph_debounce_ttl_seconds
        )
        self.tenant_concurrency_limit = (
            tenant_concurrency_limit
            if tenant_concurrency_limit is not None
            else settings.project_graph_tenant_concurrency_limit
        )
        self.requeue_countdown_seconds = (
            requeue_countdown_seconds
            if requeue_countdown_seconds is not None
            else settings.project_graph_requeue_countdown_seconds
        )

    def _project_pending_key(self, project_id: UUID) -> str:
        return build_rate_limit_key(str(project_id), "project_graph:pending")

    def _tenant_slots_key(self, tenant_id: UUID) -> str:
        return build_rate_limit_key(str(tenant_id), "project_graph:tenant_slots")

    async def should_enqueue_project(self, project_id: UUID) -> bool:
        if self._cache is None:
            return True
        return bool(
            await self._cache.set_if_absent(
                self._project_pending_key(project_id),
                "1",
                ttl_seconds=self.debounce_ttl_seconds,
            )
        )

    async def clear_project_pending(self, project_id: UUID) -> None:
        if self._cache is not None:
            await self._cache.delete(self._project_pending_key(project_id))

    async def current_tenant_slots(self, tenant_id: UUID) -> int:
        if self._cache is None:
            return 0
        raw = await self._cache.get(self._tenant_slots_key(tenant_id), default=0)
        return int(raw) if isinstance(raw, (int, str)) else 0

    async def acquire_tenant_slot(self, tenant_id: UUID) -> bool:
        if self._cache is None:
            return True
        slots_key = self._tenant_slots_key(tenant_id)
        new_value = int(
            await self._cache.incr(
                slots_key,
                ttl_seconds=max(
                    self.debounce_ttl_seconds,
                    self.requeue_countdown_seconds,
                ),
            )
        )
        if new_value > self.tenant_concurrency_limit:
            await self._cache.decr(slots_key)
            return False
        return True

    async def release_tenant_slot(self, tenant_id: UUID) -> None:
        if self._cache is None:
            return
        await self._cache.decr(self._tenant_slots_key(tenant_id))


def project_graph_governance_namespace() -> str:
    return NAMESPACE_RATE_LIMIT


__all__ = ["ProjectGraphGovernance", "project_graph_governance_namespace"]
