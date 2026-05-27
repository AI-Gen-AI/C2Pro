"""Per-tenant feature flags module.

Exposes ``TenantFlagsService`` for reading and writing feature flags stored
in ``Tenant.settings["feature_flags"]`` with a global-settings fallback.
"""
from __future__ import annotations

from src.core.feature_flags.tenant_flags_service import TenantFlagsService

__all__ = ["TenantFlagsService"]
