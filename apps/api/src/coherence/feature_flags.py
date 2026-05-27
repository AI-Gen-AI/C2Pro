"""
Coherence-scoped feature-flag helpers (ADR-009 §D, Phase D).

Thin wrappers around ``TenantFlagsService`` that give the coherence module a
stable, domain-specific API without coupling it directly to the flags service
class.

Refers to Suite IDs: TS-UA-COH-FLAG-001 … TS-UA-COH-FLAG-004.
"""
from __future__ import annotations

from uuid import UUID

from src.core.feature_flags.tenant_flags_service import TenantFlagsService

_FLAG_COHERENCE_V2 = "coherence_v2_enabled"


async def coherence_v2_enabled_for_tenant(
    tenant_id: UUID,
    *,
    flags_service: TenantFlagsService,
) -> bool:
    """Return ``True`` when the v2 coherence scorer is active for *tenant_id*.

    Parameters
    ----------
    tenant_id:
        The tenant to check.
    flags_service:
        Injected ``TenantFlagsService`` instance.

    Returns
    -------
    bool
        Resolved value of the ``coherence_v2_enabled`` flag.
    """
    return await flags_service.is_enabled(tenant_id, _FLAG_COHERENCE_V2)


__all__ = ["coherence_v2_enabled_for_tenant"]
