"""Cost governance for ADR-017 ProjectGraph tasks.

TS-UT-ADR017-GOV-001
"""

from __future__ import annotations

from uuid import UUID

from src.config import settings
from src.core.cache import NAMESPACE_RATE_LIMIT, build_rate_limit_key, get_cache_service


class ProjectGraphGovernance:
    def __init__(
        self,
        *,
        cache: object | None = None,
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
        key = self._project_pending_key(project_id)
        if await self._cache_get(key, default=None) is not None:
            return False
        await self._cache_set(key, "1", ttl=self.debounce_ttl_seconds)
        return True

    async def clear_project_pending(self, project_id: UUID) -> None:
        if self._cache is not None:
            await self._cache_delete(self._project_pending_key(project_id))

    async def current_tenant_slots(self, tenant_id: UUID) -> int:
        if self._cache is None:
            return 0
        value = await self._cache_get(self._tenant_slots_key(tenant_id), default=0)
        return int(value or 0)

    async def acquire_tenant_slot(self, tenant_id: UUID) -> bool:
        if self._cache is None:
            return True
        current = await self.current_tenant_slots(tenant_id)
        if current >= self.tenant_concurrency_limit:
            return False
        await self._cache_set(
            self._tenant_slots_key(tenant_id),
            current + 1,
            ttl=max(self.debounce_ttl_seconds, self.requeue_countdown_seconds),
        )
        return True

    async def release_tenant_slot(self, tenant_id: UUID) -> None:
        if self._cache is None:
            return
        key = self._tenant_slots_key(tenant_id)
        current = await self.current_tenant_slots(tenant_id)
        if current <= 1:
            await self._cache_delete(key)
            return
        await self._cache_set(
            key,
            current - 1,
            ttl=max(self.debounce_ttl_seconds, self.requeue_countdown_seconds),
        )

    async def _cache_get(self, key: str, *, default: object | None) -> object | None:
        return await self._cache.get(key, default=default)

    async def _cache_set(self, key: str, value: object, *, ttl: int) -> None:
        await self._cache.set(key, value, ttl=ttl)

    async def _cache_delete(self, key: str) -> None:
        await self._cache.delete(key)


def project_graph_governance_namespace() -> str:
    return NAMESPACE_RATE_LIMIT


__all__ = ["ProjectGraphGovernance", "project_graph_governance_namespace"]
