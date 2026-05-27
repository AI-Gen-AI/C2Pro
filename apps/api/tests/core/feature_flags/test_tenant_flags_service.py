"""
Tests for TenantFlagsService — per-tenant feature flag read/write.

Suite IDs:
  TS-UA-COH-FLAG-001  is_enabled returns tenant override if set; global fallback
  TS-UA-COH-FLAG-002  set_flag mutates tenant.settings["feature_flags"] and commits
  TS-UA-COH-FLAG-003  set_flag emits coherence.flag_changed event
  TS-UA-COH-FLAG-004  Concurrent set_flag on different tenants do not interfere
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

# ─── test subjects ──────────────────────────────────────────────────────────
# Import will fail until GREEN — that is expected (RED phase).
from src.core.feature_flags.tenant_flags_service import TenantFlagsService

# ─── helpers ────────────────────────────────────────────────────────────────

TENANT_A = uuid4()
TENANT_B = uuid4()


def _make_tenant(tenant_id: UUID, feature_flags: dict[str, bool] | None = None) -> MagicMock:
    """Return a mock Tenant ORM object with preset settings."""
    tenant = MagicMock()
    tenant.id = tenant_id
    tenant.settings = {}
    if feature_flags is not None:
        tenant.settings = {"feature_flags": dict(feature_flags)}
    return tenant


def _make_repo(tenant: Any | None) -> AsyncMock:
    """Return a mock ITenantRepository."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=tenant)
    repo.update_settings = AsyncMock(return_value=tenant)
    repo.commit = AsyncMock()
    return repo


def _make_settings(**kwargs: bool) -> MagicMock:
    """Return a mock Settings object with arbitrary flag attributes."""
    s = MagicMock()
    for name, value in kwargs.items():
        setattr(s, name, value)
    # Ensure getattr on unknown flags returns False
    s.__class__ = type("Settings", (), {"__getattr__": lambda self, name: False})
    return s


# ============================================================================
# TS-UA-COH-FLAG-001  is_enabled — tenant override / global fallback
# ============================================================================


class TestIsEnabled:
    @pytest.mark.asyncio
    async def test_returns_tenant_override_true_when_set(self) -> None:
        """TS-UA-COH-FLAG-001 — tenant flag=True beats global flag=False."""
        tenant = _make_tenant(TENANT_A, feature_flags={"coherence_v2_enabled": True})
        repo = _make_repo(tenant)
        settings = _make_settings(coherence_v2_enabled=False)

        service = TenantFlagsService(tenant_repository=repo, settings=settings)
        result = await service.is_enabled(TENANT_A, "coherence_v2_enabled")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_tenant_override_false_when_set(self) -> None:
        """TS-UA-COH-FLAG-001 — tenant flag=False beats global flag=True."""
        tenant = _make_tenant(TENANT_A, feature_flags={"coherence_v2_enabled": False})
        repo = _make_repo(tenant)
        settings = _make_settings(coherence_v2_enabled=True)

        service = TenantFlagsService(tenant_repository=repo, settings=settings)
        result = await service.is_enabled(TENANT_A, "coherence_v2_enabled")

        assert result is False

    @pytest.mark.asyncio
    async def test_falls_back_to_global_when_no_tenant_override(self) -> None:
        """TS-UA-COH-FLAG-001 — no tenant entry → use global True."""
        tenant = _make_tenant(TENANT_A)  # no feature_flags sub-key
        repo = _make_repo(tenant)
        settings = _make_settings(coherence_v2_enabled=True)

        service = TenantFlagsService(tenant_repository=repo, settings=settings)
        result = await service.is_enabled(TENANT_A, "coherence_v2_enabled")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_tenant_not_found_and_global_false(self) -> None:
        """TS-UA-COH-FLAG-001 — missing tenant row → global False."""
        repo = _make_repo(None)  # get_by_id returns None
        settings = _make_settings(coherence_v2_enabled=False)

        service = TenantFlagsService(tenant_repository=repo, settings=settings)
        result = await service.is_enabled(TENANT_A, "coherence_v2_enabled")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_tenant_not_found_and_global_true(self) -> None:
        """TS-UA-COH-FLAG-001 — missing tenant row → global True."""
        repo = _make_repo(None)
        settings = _make_settings(coherence_v2_enabled=True)

        service = TenantFlagsService(tenant_repository=repo, settings=settings)
        result = await service.is_enabled(TENANT_A, "coherence_v2_enabled")

        assert result is True

    @pytest.mark.asyncio
    async def test_feature_flags_key_absent_falls_back_to_global(self) -> None:
        """TS-UA-COH-FLAG-001 — settings dict present but no feature_flags sub-key."""
        tenant = _make_tenant(TENANT_A)
        tenant.settings = {"alerts_workspace": {"some": "value"}}  # no feature_flags
        repo = _make_repo(tenant)
        settings = _make_settings(coherence_v2_enabled=True)

        service = TenantFlagsService(tenant_repository=repo, settings=settings)
        result = await service.is_enabled(TENANT_A, "coherence_v2_enabled")

        assert result is True

    @pytest.mark.asyncio
    async def test_unknown_flag_falls_back_to_false(self) -> None:
        """TS-UA-COH-FLAG-001 — flag not in tenant or global → False."""
        tenant = _make_tenant(TENANT_A)
        repo = _make_repo(tenant)
        settings_obj = MagicMock(spec=[])  # no attributes at all

        service = TenantFlagsService(tenant_repository=repo, settings=settings_obj)
        result = await service.is_enabled(TENANT_A, "some_unknown_flag")

        assert result is False


# ============================================================================
# TS-UA-COH-FLAG-002  set_flag — mutates settings and commits
# ============================================================================


class TestSetFlag:
    @pytest.mark.asyncio
    async def test_set_flag_creates_feature_flags_key_if_absent(self) -> None:
        """TS-UA-COH-FLAG-002 — tenant.settings gains feature_flags dict."""
        tenant = _make_tenant(TENANT_A)
        tenant.settings = {}
        repo = _make_repo(tenant)
        settings = _make_settings()

        service = TenantFlagsService(tenant_repository=repo, settings=settings)
        await service.set_flag(TENANT_A, "coherence_v2_enabled", True)

        # update_settings must have been called with the merged dict
        repo.update_settings.assert_awaited_once()
        call_args = repo.update_settings.call_args
        new_settings: dict = call_args[0][1]  # positional arg[1] = settings dict
        assert new_settings["feature_flags"]["coherence_v2_enabled"] is True

    @pytest.mark.asyncio
    async def test_set_flag_merges_with_existing_feature_flags(self) -> None:
        """TS-UA-COH-FLAG-002 — existing flags preserved, target flag updated."""
        tenant = _make_tenant(TENANT_A, feature_flags={"other_flag": True})
        repo = _make_repo(tenant)
        settings = _make_settings()

        service = TenantFlagsService(tenant_repository=repo, settings=settings)
        await service.set_flag(TENANT_A, "coherence_v2_enabled", False)

        call_args = repo.update_settings.call_args
        new_settings: dict = call_args[0][1]
        assert new_settings["feature_flags"]["other_flag"] is True
        assert new_settings["feature_flags"]["coherence_v2_enabled"] is False

    @pytest.mark.asyncio
    async def test_set_flag_calls_commit(self) -> None:
        """TS-UA-COH-FLAG-002 — commit is always called after update."""
        tenant = _make_tenant(TENANT_A)
        repo = _make_repo(tenant)
        settings = _make_settings()

        service = TenantFlagsService(tenant_repository=repo, settings=settings)
        await service.set_flag(TENANT_A, "coherence_v2_enabled", True)

        repo.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_set_flag_raises_when_tenant_not_found(self) -> None:
        """TS-UA-COH-FLAG-002 — ValueError if tenant does not exist."""
        repo = _make_repo(None)
        settings = _make_settings()

        service = TenantFlagsService(tenant_repository=repo, settings=settings)
        with pytest.raises(ValueError, match="Tenant not found"):
            await service.set_flag(TENANT_A, "coherence_v2_enabled", True)

    @pytest.mark.asyncio
    async def test_set_flag_does_not_mutate_original_tenant_settings(self) -> None:
        """TS-UA-COH-FLAG-002 — immutability: original settings dict is not mutated."""
        original_settings = {"alerts_workspace": {"x": 1}}
        tenant = _make_tenant(TENANT_A)
        tenant.settings = original_settings
        repo = _make_repo(tenant)
        settings_cfg = _make_settings()

        service = TenantFlagsService(tenant_repository=repo, settings=settings_cfg)
        await service.set_flag(TENANT_A, "coherence_v2_enabled", True)

        # The dict passed into update_settings must be a NEW object (copy)
        call_args = repo.update_settings.call_args
        passed_settings: dict = call_args[0][1]
        assert passed_settings is not original_settings


# ============================================================================
# TS-UA-COH-FLAG-003  set_flag — emits coherence.flag_changed event
# ============================================================================


class TestSetFlagEmitsEvent:
    @pytest.mark.asyncio
    async def test_emits_flag_changed_event_via_structlog(self) -> None:
        """TS-UA-COH-FLAG-003 — coherence.flag_changed structlog event emitted."""
        tenant = _make_tenant(TENANT_A, feature_flags={"coherence_v2_enabled": False})
        repo = _make_repo(tenant)
        settings = _make_settings()

        events: list[dict] = []

        with patch(
            "src.core.feature_flags.tenant_flags_service.logger"
        ) as mock_logger:
            service = TenantFlagsService(tenant_repository=repo, settings=settings)
            await service.set_flag(TENANT_A, "coherence_v2_enabled", True)

        mock_logger.info.assert_called()
        call_kwargs = mock_logger.info.call_args
        # First positional arg is the event name
        event_name = call_kwargs[0][0]
        assert event_name == "coherence.flag_changed"

    @pytest.mark.asyncio
    async def test_event_includes_tenant_id_and_flag_values(self) -> None:
        """TS-UA-COH-FLAG-003 — event carries tenant_id, flag_name, old/new values."""
        tenant = _make_tenant(TENANT_A, feature_flags={"coherence_v2_enabled": False})
        repo = _make_repo(tenant)
        settings = _make_settings()

        with patch(
            "src.core.feature_flags.tenant_flags_service.logger"
        ) as mock_logger:
            service = TenantFlagsService(tenant_repository=repo, settings=settings)
            await service.set_flag(TENANT_A, "coherence_v2_enabled", True)

        call_kwargs = mock_logger.info.call_args[1]  # keyword args
        assert call_kwargs["tenant_id"] == str(TENANT_A)
        assert call_kwargs["flag_name"] == "coherence_v2_enabled"
        assert call_kwargs["old_value"] is False
        assert call_kwargs["new_value"] is True


# ============================================================================
# TS-UA-COH-FLAG-004  Concurrent set_flag on different tenants
# ============================================================================


class TestConcurrentSetFlag:
    @pytest.mark.asyncio
    async def test_concurrent_set_flag_different_tenants_do_not_interfere(self) -> None:
        """TS-UA-COH-FLAG-004 — concurrent flag flips on two tenants are isolated."""
        tenant_a = _make_tenant(TENANT_A)
        tenant_b = _make_tenant(TENANT_B)

        repo_a = _make_repo(tenant_a)
        repo_b = _make_repo(tenant_b)

        settings = _make_settings()

        svc_a = TenantFlagsService(tenant_repository=repo_a, settings=settings)
        svc_b = TenantFlagsService(tenant_repository=repo_b, settings=settings)

        await asyncio.gather(
            svc_a.set_flag(TENANT_A, "coherence_v2_enabled", True),
            svc_b.set_flag(TENANT_B, "coherence_v2_enabled", False),
        )

        # Both repos committed once each
        repo_a.commit.assert_awaited_once()
        repo_b.commit.assert_awaited_once()

        # Tenant A got True
        a_settings = repo_a.update_settings.call_args[0][1]
        assert a_settings["feature_flags"]["coherence_v2_enabled"] is True

        # Tenant B got False
        b_settings = repo_b.update_settings.call_args[0][1]
        assert b_settings["feature_flags"]["coherence_v2_enabled"] is False
