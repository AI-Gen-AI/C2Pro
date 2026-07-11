"""
Integration tests for flag-toggle coherence cache invalidation.

Suite ID: TS-INT-COH-CACHE-FLAG-007
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from fnmatch import fnmatch
from uuid import UUID

import pytest

from src.coherence.cache_invalidation import on_flag_flip
from src.coherence.cache_keys import key
from src.coherence.domain.v2_constants import SCORE_VERSION_V1, SCORE_VERSION_V2


TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PROJECT_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


class InMemoryAsyncRedis:
    """Redis scan/unlink double for TS-INT-COH-CACHE-FLAG-007."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    async def set(self, redis_key: str, value: str) -> None:
        self._values[redis_key] = value

    async def get(self, redis_key: str) -> str | None:
        return self._values.get(redis_key)

    async def scan_iter(self, *, match: str, count: int = 500) -> AsyncIterator[str]:
        _ = count
        for redis_key in list(self._values):
            if fnmatch(redis_key, match):
                yield redis_key

    async def unlink(self, *keys: str) -> int:
        deleted = 0
        for redis_key in keys:
            if redis_key in self._values:
                deleted += 1
                del self._values[redis_key]
        return deleted

    def remaining_keys(self) -> set[str]:
        return set(self._values)


def _dashboard_key(*, tenant_id: UUID, project_id: UUID, enabled: bool) -> str:
    version = SCORE_VERSION_V2 if enabled else SCORE_VERSION_V1
    return key(
        namespace="dashboard",
        version=version,
        tenant_id=tenant_id,
        project_id=project_id,
    )


@pytest.mark.asyncio
async def test_flag_toggle_flushes_v1_cache_before_v2_cutover_and_back_again() -> None:
    """TS-INT-COH-CACHE-FLAG-007: toggling flag never reuses opposite-version keys."""
    redis_client = InMemoryAsyncRedis()
    v1_key = _dashboard_key(tenant_id=TENANT_ID, project_id=PROJECT_ID, enabled=False)
    v2_key = _dashboard_key(tenant_id=TENANT_ID, project_id=PROJECT_ID, enabled=True)

    await redis_client.set(v1_key, '{"score_version":"coherence-v1","score":0.71}')
    assert await redis_client.get(v1_key) is not None
    assert await redis_client.get(v2_key) is None

    deleted_on_v2_cutover = await on_flag_flip(redis_client, tenant_id=TENANT_ID)

    assert deleted_on_v2_cutover == 1
    assert await redis_client.get(v1_key) is None
    assert await redis_client.get(v2_key) is None

    await redis_client.set(v2_key, '{"score_version":"coherence-v2","score":0.83}')
    assert await redis_client.get(v2_key) is not None

    deleted_on_v1_rollback = await on_flag_flip(redis_client, tenant_id=TENANT_ID)

    assert deleted_on_v1_rollback == 1
    assert await redis_client.get(v1_key) is None
    assert await redis_client.get(v2_key) is None


@pytest.mark.asyncio
async def test_flag_toggle_invalidates_both_versions_only_for_target_tenant() -> None:
    """TS-INT-COH-CACHE-FLAG-007: tenant cutover invalidation is tenant scoped."""
    redis_client = InMemoryAsyncRedis()
    target_v1 = _dashboard_key(tenant_id=TENANT_ID, project_id=PROJECT_ID, enabled=False)
    target_v2 = _dashboard_key(tenant_id=TENANT_ID, project_id=PROJECT_ID, enabled=True)
    other_tenant_v1 = _dashboard_key(
        tenant_id=OTHER_TENANT_ID,
        project_id=PROJECT_ID,
        enabled=False,
    )

    await redis_client.set(target_v1, "target-v1")
    await redis_client.set(target_v2, "target-v2")
    await redis_client.set(other_tenant_v1, "other-tenant-v1")

    deleted = await on_flag_flip(redis_client, tenant_id=TENANT_ID)

    assert deleted == 2
    assert redis_client.remaining_keys() == {other_tenant_v1}
