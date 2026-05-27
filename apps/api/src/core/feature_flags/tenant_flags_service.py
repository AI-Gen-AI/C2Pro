"""
Per-tenant feature flag read/write service (ADR-009 §D, Phase D).

Storage convention:  ``Tenant.settings["feature_flags"][flag_name]``
Global fallback:     ``getattr(app_settings, flag_name, False)``

Telemetry:           structlog event ``coherence.flag_changed`` on every
                     successful ``set_flag`` call.

Cache invalidation:  when ``coherence_v2_enabled`` is flipped, calls
                     ``cache_invalidation.on_flag_flip`` to clear stale
                     coherence cache entries for the tenant.

Refers to Suite IDs: TS-UA-COH-FLAG-001 … TS-UA-COH-FLAG-004.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

logger = structlog.get_logger()

_FLAG_COHERENCE_V2 = "coherence_v2_enabled"

# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------


class TenantFlagsService:
    """Read and write per-tenant feature flags.

    Parameters
    ----------
    tenant_repository:
        Any object that exposes:
          - ``async get_by_id(tenant_id: UUID) -> Tenant | None``
          - ``async update_settings(tenant_id: UUID, settings: dict) -> Tenant | None``
          - ``async commit() -> None``
    settings:
        Application-level settings object.  ``getattr(settings, flag_name, False)``
        is used as the global default when no per-tenant override exists.
    """

    def __init__(self, *, tenant_repository: Any, settings: Any) -> None:
        self._repo = tenant_repository
        self._settings = settings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def is_enabled(self, tenant_id: UUID, flag_name: str) -> bool:
        """Return the effective boolean value of *flag_name* for *tenant_id*.

        Resolution order:
        1. ``tenant.settings["feature_flags"][flag_name]`` when the tenant row
           exists and the flag is explicitly set.
        2. ``getattr(self._settings, flag_name, False)`` as the global fallback.

        Parameters
        ----------
        tenant_id:
            UUID of the tenant to query.
        flag_name:
            Dot-free flag identifier (e.g. ``"coherence_v2_enabled"``).

        Returns
        -------
        bool
            Resolved flag value.
        """
        tenant = await self._repo.get_by_id(tenant_id)
        if tenant is not None:
            flags: dict[str, bool] = (tenant.settings or {}).get("feature_flags", {})
            if flag_name in flags:
                return bool(flags[flag_name])

        return bool(getattr(self._settings, flag_name, False))

    async def set_flag(self, tenant_id: UUID, flag_name: str, value: bool) -> None:
        """Persist *flag_name = value* for *tenant_id* and emit a structlog event.

        The implementation is immutable: a NEW settings dict is constructed from
        the tenant's current settings (via ``dict.copy()`` / spread) rather than
        mutating the original dict in place.

        Parameters
        ----------
        tenant_id:
            UUID of the tenant to update.
        flag_name:
            Flag identifier.
        value:
            New flag value.

        Raises
        ------
        ValueError
            If the tenant row does not exist in the repository.
        """
        tenant = await self._repo.get_by_id(tenant_id)
        if tenant is None:
            raise ValueError(f"Tenant not found: {tenant_id}")

        current: dict[str, Any] = tenant.settings or {}
        old_value: bool = bool(
            current.get("feature_flags", {}).get(flag_name, False)
        )

        # Build immutable copies — never mutate the original dict.
        new_flags: dict[str, bool] = {
            **current.get("feature_flags", {}),
            flag_name: value,
        }
        new_settings: dict[str, Any] = {
            **current,
            "feature_flags": new_flags,
        }

        await self._repo.update_settings(tenant_id, new_settings)
        await self._repo.commit()

        logger.info(
            "coherence.flag_changed",
            tenant_id=str(tenant_id),
            flag_name=flag_name,
            old_value=old_value,
            new_value=value,
        )

        # Cache invalidation: when the coherence v2 flag flips, flush all
        # stale coherence cache keys for this tenant so the next request
        # recomputes with the newly active scorer.
        # Imports are deferred to avoid a core→coherence circular dependency
        # at module load time.
        if flag_name == _FLAG_COHERENCE_V2:
            from src.coherence import cache_invalidation  # noqa: PLC0415
            from src.core.cache import get_redis_client  # noqa: PLC0415

            redis = get_redis_client()
            if redis is not None:
                try:
                    await cache_invalidation.on_flag_flip(redis, tenant_id=tenant_id)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "coherence.flag_changed.cache_invalidation_failed",
                        tenant_id=str(tenant_id),
                        error=str(exc),
                    )


__all__ = ["TenantFlagsService"]
