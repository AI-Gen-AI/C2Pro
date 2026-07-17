"""Tenant identity types and guards used at hexagonal boundaries."""

from typing import NewType
from uuid import UUID

TenantId = NewType("TenantId", UUID)


def require_tenant_id(tenant_id: UUID | str | TenantId | None) -> TenantId:
    """Validate tenant id presence before invoking ports/use cases."""
    if tenant_id is None:
        raise ValueError("tenant_id is required")
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)
    return TenantId(tenant_id)
