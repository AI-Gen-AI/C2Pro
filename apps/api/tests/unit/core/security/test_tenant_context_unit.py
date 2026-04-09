from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.core.security.tenant_context import TenantContext, TenantIsolationError, TenantScopedCache


def test_tenant_context_set_get():
    """Prueba set y get en TenantContext."""
    ctx = TenantContext()
    tenant_id = uuid4()

    token = ctx.set_current_tenant(tenant_id)
    assert ctx.get_current_tenant() == tenant_id

    ctx.reset(token)
    assert ctx.get_current_tenant() is None

def test_tenant_context_require_success():
    """require_current_tenant debe devolver el tenant si está seteado."""
    ctx = TenantContext()
    tenant_id = uuid4()
    ctx.set_current_tenant(tenant_id)

    assert ctx.require_current_tenant() == tenant_id

def test_tenant_context_require_fail():
    """require_current_tenant debe lanzar error si no hay tenant."""
    ctx = TenantContext()
    # Ensure it's None
    token = ctx._current_tenant.set(None)
    try:
        with pytest.raises(TenantIsolationError) as exc:
            ctx.require_current_tenant()
        assert "No tenant in execution context" in str(exc.value)
    finally:
        ctx.reset(token)

def test_tenant_scoped_cache_get_success():
    """Cache debe permitir acceso al mismo tenant."""
    ctx = TenantContext()
    tenant_id = uuid4()
    ctx.set_current_tenant(tenant_id)

    mock_backend = MagicMock()
    mock_backend.get.return_value = "cached_value"

    cache = TenantScopedCache(context=ctx, backend=mock_backend)
    result = cache.get(tenant_id, "some_key")

    assert result == "cached_value"
    mock_backend.get.assert_called_once_with(f"{tenant_id}:some_key")

def test_tenant_scoped_cache_get_denied():
    """Cache debe denegar acceso a otro tenant."""
    ctx = TenantContext()
    tenant_id_1 = uuid4()
    tenant_id_2 = uuid4()
    ctx.set_current_tenant(tenant_id_1)

    mock_backend = MagicMock()
    cache = TenantScopedCache(context=ctx, backend=mock_backend)

    with pytest.raises(TenantIsolationError) as exc:
        cache.get(tenant_id_2, "some_key")

    assert "Cross-tenant access denied" in str(exc.value)
    mock_backend.get.assert_not_called()

def test_tenant_scoped_cache_set_success():
    """Cache debe permitir set para el mismo tenant."""
    ctx = TenantContext()
    tenant_id = uuid4()
    ctx.set_current_tenant(tenant_id)

    mock_backend = MagicMock()
    cache = TenantScopedCache(context=ctx, backend=mock_backend)

    cache.set(tenant_id, "key", "value", ttl_seconds=60)
    mock_backend.set.assert_called_once_with(f"{tenant_id}:key", "value", ttl_seconds=60)

def test_tenant_scoped_cache_delete_success():
    """Cache debe permitir delete para el mismo tenant."""
    ctx = TenantContext()
    tenant_id = uuid4()
    ctx.set_current_tenant(tenant_id)

    mock_backend = MagicMock()
    cache = TenantScopedCache(context=ctx, backend=mock_backend)

    cache.delete(tenant_id, "key")
    mock_backend.delete.assert_called_once_with(f"{tenant_id}:key")
