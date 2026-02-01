"""
Tenant Context & Isolation Tests (TDD - RED Phase)

Refers to Suite ID: TS-UC-SEC-TNT-001.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.core.security.tenant_context import (
    TenantContext,
    TenantIsolationError,
    TenantScopedCache,
)


class TestTenantContextIsolation:
    """Refers to Suite ID: TS-UC-SEC-TNT-001."""

    def test_accessing_other_tenant_cache_raises(self, mocker):
        """
        When ContextVar is set to tenant B, accessing tenant A data must fail.
        """
        tenant_a = uuid4()
        tenant_b = uuid4()
        backend_cache = mocker.Mock()
        backend_cache.get.return_value = {"secret": "value"}

        context = TenantContext()
        cache = TenantScopedCache(context=context, backend=backend_cache)

        token = context.set_current_tenant(tenant_b)
        try:
            with pytest.raises(TenantIsolationError):
                cache.get(tenant_id=tenant_a, key="project:summary")
        finally:
            context.reset(token)
