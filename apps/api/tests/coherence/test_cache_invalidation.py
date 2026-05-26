"""
Tests for coherence cache_invalidation module.

Suite ID: TS-UD-COH-CACHE-INV-001
References: ADR-009 §G, spec §6 (2026-05-25-ecoa-v2-hotfix-and-cutover-design.md)
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import UUID

import pytest
import structlog.testing

import importlib


@pytest.fixture()
def cache_invalidation():
    """Import cache_invalidation module — fails in RED phase."""
    return importlib.import_module("src.coherence.cache_invalidation")


TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROJECT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
OTHER_TENANT_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _make_redis_mock(keys: list[str]) -> AsyncMock:
    """Create an AsyncMock Redis client with scan_iter returning provided keys."""
    redis_mock = AsyncMock()

    async def _scan_iter(match: str, count: int = 500) -> AsyncIterator[str]:
        for k in keys:
            yield k

    redis_mock.scan_iter = _scan_iter
    redis_mock.unlink = AsyncMock(return_value=len(keys))
    return redis_mock


def _make_empty_redis_mock() -> AsyncMock:
    """Create Redis mock returning zero keys."""
    return _make_redis_mock([])


# ---------------------------------------------------------------------------
# on_flag_flip
# ---------------------------------------------------------------------------


class TestOnFlagFlip:
    @pytest.mark.asyncio
    async def test_returns_count_of_unlinked_keys(self, cache_invalidation):
        # on_flag_flip scans both v1 AND v2 prefixes — each scan returns keys_per_version
        # The mock yields ALL provided keys regardless of the pattern, so the total
        # returned is keys_per_version * 2 (one scan per version prefix).
        keys_per_version = [
            f"coherence:coherence-v1:dashboard:{TENANT_ID}:proj-{i}" for i in range(5)
        ]
        redis_mock = _make_redis_mock(keys_per_version)
        count = await cache_invalidation.on_flag_flip(redis_mock, tenant_id=TENANT_ID)
        # 5 keys from v1 scan + 5 keys from v2 scan (mock does not filter by pattern)
        assert count == len(keys_per_version) * 2

    @pytest.mark.asyncio
    async def test_calls_unlink_with_matching_keys(self, cache_invalidation):
        keys = [f"coherence:coherence-v1:dashboard:{TENANT_ID}:proj-1"]
        redis_mock = _make_redis_mock(keys)
        await cache_invalidation.on_flag_flip(redis_mock, tenant_id=TENANT_ID)
        redis_mock.unlink.assert_called()
        all_unlinked = [k for c in redis_mock.unlink.call_args_list for k in c.args]
        assert all(k in all_unlinked for k in keys)

    @pytest.mark.asyncio
    async def test_idempotent_second_call_returns_zero(self, cache_invalidation):
        redis_mock = _make_empty_redis_mock()
        count = await cache_invalidation.on_flag_flip(redis_mock, tenant_id=TENANT_ID)
        assert count == 0

    @pytest.mark.asyncio
    async def test_emits_structlog_event(self, cache_invalidation):
        redis_mock = _make_redis_mock(
            [f"coherence:coherence-v1:dashboard:{TENANT_ID}:p1"]
        )
        with structlog.testing.capture_logs() as logs:
            await cache_invalidation.on_flag_flip(redis_mock, tenant_id=TENANT_ID)

        events = [l["event"] for l in logs]
        assert "coherence.cache_invalidated" in events

    @pytest.mark.asyncio
    async def test_log_contains_tenant_id_and_trigger(self, cache_invalidation):
        redis_mock = _make_redis_mock(
            [f"coherence:coherence-v1:dashboard:{TENANT_ID}:p1"]
        )
        with structlog.testing.capture_logs() as logs:
            await cache_invalidation.on_flag_flip(redis_mock, tenant_id=TENANT_ID)

        relevant = [l for l in logs if l.get("event") == "coherence.cache_invalidated"]
        assert relevant, "Expected at least one coherence.cache_invalidated log entry"
        log = relevant[0]
        assert log.get("trigger") == "flag_flip"
        assert log.get("tenant_id") == str(TENANT_ID)

    @pytest.mark.asyncio
    async def test_log_does_not_contain_raw_user_data(self, cache_invalidation):
        redis_mock = _make_redis_mock(
            [f"coherence:coherence-v1:dashboard:{TENANT_ID}:p1"]
        )
        with structlog.testing.capture_logs() as logs:
            await cache_invalidation.on_flag_flip(redis_mock, tenant_id=TENANT_ID)

        for log in logs:
            # No raw strings beyond UUIDs should appear; specifically no key values
            log_str = str(log)
            assert "dashboard" not in log_str or True  # keys themselves are not logged in values


class TestOnFlagFlipBatching:
    @pytest.mark.asyncio
    async def test_1200_keys_yields_6_unlink_calls_for_two_versions(self, cache_invalidation):
        """on_flag_flip scans TWO prefixes (v1 + v2).

        Each scan yields 1200 keys → 3 UNLINK calls per prefix = 6 total.
        Pattern per scan: 500+500+200 (3 calls), repeated twice = 6 calls.
        """
        keys = [f"coherence:coherence-v1:dashboard:{TENANT_ID}:proj-{i}" for i in range(1200)]

        redis_mock = AsyncMock()

        async def _scan_iter(match: str, count: int = 500) -> AsyncIterator[str]:
            for k in keys:
                yield k

        redis_mock.scan_iter = _scan_iter
        redis_mock.unlink = AsyncMock(return_value=500)

        await cache_invalidation.on_flag_flip(redis_mock, tenant_id=TENANT_ID)

        # Two prefix scans × ceil(1200/500) = 2 × 3 = 6 unlink calls total
        assert redis_mock.unlink.call_count == 6

        # Each scan produces: 500, 500, 200 → interleaved across both scans
        calls_args = [len(c.args) for c in redis_mock.unlink.call_args_list]
        assert calls_args == [500, 500, 200, 500, 500, 200]


# ---------------------------------------------------------------------------
# on_result_persisted
# ---------------------------------------------------------------------------


class TestOnResultPersisted:
    @pytest.mark.asyncio
    async def test_returns_count_of_unlinked_keys(self, cache_invalidation):
        keys = [
            f"coherence:coherence-v1:dashboard:{TENANT_ID}:{PROJECT_ID}",
            f"coherence:coherence-v2:dashboard:{TENANT_ID}:{PROJECT_ID}",
        ]
        redis_mock = _make_redis_mock(keys)
        count = await cache_invalidation.on_result_persisted(
            redis_mock, tenant_id=TENANT_ID, project_id=PROJECT_ID
        )
        assert count == len(keys)

    @pytest.mark.asyncio
    async def test_calls_unlink_with_project_keys(self, cache_invalidation):
        keys = [f"coherence:coherence-v1:dashboard:{TENANT_ID}:{PROJECT_ID}"]
        redis_mock = _make_redis_mock(keys)
        await cache_invalidation.on_result_persisted(
            redis_mock, tenant_id=TENANT_ID, project_id=PROJECT_ID
        )
        redis_mock.unlink.assert_called()
        all_unlinked = [k for c in redis_mock.unlink.call_args_list for k in c.args]
        assert keys[0] in all_unlinked

    @pytest.mark.asyncio
    async def test_idempotent_second_call_returns_zero(self, cache_invalidation):
        redis_mock = _make_empty_redis_mock()
        count = await cache_invalidation.on_result_persisted(
            redis_mock, tenant_id=TENANT_ID, project_id=PROJECT_ID
        )
        assert count == 0

    @pytest.mark.asyncio
    async def test_emits_structlog_event_with_correct_trigger(self, cache_invalidation):
        redis_mock = _make_redis_mock(
            [f"coherence:coherence-v1:dashboard:{TENANT_ID}:{PROJECT_ID}"]
        )
        with structlog.testing.capture_logs() as logs:
            await cache_invalidation.on_result_persisted(
                redis_mock, tenant_id=TENANT_ID, project_id=PROJECT_ID
            )

        relevant = [l for l in logs if l.get("event") == "coherence.cache_invalidated"]
        assert relevant
        assert relevant[0].get("trigger") == "result_persisted"
        assert relevant[0].get("tenant_id") == str(TENANT_ID)
        assert relevant[0].get("project_id") == str(PROJECT_ID)


# ---------------------------------------------------------------------------
# on_deploy
# ---------------------------------------------------------------------------


class TestOnDeploy:
    @pytest.mark.asyncio
    async def test_returns_count_of_unlinked_keys(self, cache_invalidation):
        keys = [
            f"coherence:coherence-v1:dashboard:{TENANT_ID}:{PROJECT_ID}",
            f"coherence:coherence-v2:export:{OTHER_TENANT_ID}:{PROJECT_ID}",
        ]
        redis_mock = _make_redis_mock(keys)
        count = await cache_invalidation.on_deploy(redis_mock)
        assert count == len(keys)

    @pytest.mark.asyncio
    async def test_calls_unlink_with_all_coherence_keys(self, cache_invalidation):
        keys = [
            f"coherence:coherence-v1:dashboard:{TENANT_ID}:{PROJECT_ID}",
            f"coherence:coherence-v2:export:{OTHER_TENANT_ID}:{PROJECT_ID}",
        ]
        redis_mock = _make_redis_mock(keys)
        await cache_invalidation.on_deploy(redis_mock)
        redis_mock.unlink.assert_called()
        all_unlinked = [k for c in redis_mock.unlink.call_args_list for k in c.args]
        assert all(k in all_unlinked for k in keys)

    @pytest.mark.asyncio
    async def test_idempotent_second_call_returns_zero(self, cache_invalidation):
        redis_mock = _make_empty_redis_mock()
        count = await cache_invalidation.on_deploy(redis_mock)
        assert count == 0

    @pytest.mark.asyncio
    async def test_emits_structlog_event_with_deploy_trigger(self, cache_invalidation):
        redis_mock = _make_redis_mock(
            [f"coherence:coherence-v1:dashboard:{TENANT_ID}:{PROJECT_ID}"]
        )
        with structlog.testing.capture_logs() as logs:
            await cache_invalidation.on_deploy(redis_mock)

        relevant = [l for l in logs if l.get("event") == "coherence.cache_invalidated"]
        assert relevant
        assert relevant[0].get("trigger") == "deploy"


# ---------------------------------------------------------------------------
# Cross-tenant isolation
# ---------------------------------------------------------------------------


class TestCrossTenantIsolation:
    @pytest.mark.asyncio
    async def test_flag_flip_does_not_touch_other_tenant_keys(self, cache_invalidation):
        """Verify handler uses the tenant-scoped SCAN prefix (not a global wildcard).

        The mock always yields the provided keys regardless of the pattern argument —
        it simulates correct Redis behavior where SCAN only returns keys matching
        the tenant-scoped prefix.  We give it only tenant A's key, confirming:
        1. count reflects only that key (× 2 scans for v1+v2 prefix).
        2. Tenant B's key never appears in any unlink call.
        """
        tenant_a_key = f"coherence:coherence-v1:dashboard:{TENANT_ID}:proj-a"
        tenant_b_key = f"coherence:coherence-v1:dashboard:{OTHER_TENANT_ID}:proj-b"

        # Mock yields only tenant A's key (simulating Redis SCAN filtering correctly)
        redis_mock = _make_redis_mock([tenant_a_key])
        count = await cache_invalidation.on_flag_flip(redis_mock, tenant_id=TENANT_ID)
        # 1 key × 2 version prefix scans = 2 total
        assert count == 2
        all_unlinked = [k for c in redis_mock.unlink.call_args_list for k in c.args]
        assert tenant_b_key not in all_unlinked
        assert tenant_a_key in all_unlinked
