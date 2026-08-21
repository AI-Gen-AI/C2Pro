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
_FLAG_COHERENCE_CANARY = "coherence_canonical_canary"
_FLAG_COHERENCE_LLM_CROSSCHECK = "coherence_llm_crosscheck"


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


async def coherence_canonical_canary_enabled_for_tenant(
    tenant_id: UUID,
    *,
    flags_service: TenantFlagsService,
) -> bool:
    """Return ``True`` when the canonical-scorer canary is active for *tenant_id*.

    The ADR-017 canary flips only the SCORER: a canary tenant keeps v1's findings but
    receives the expert-calibrated canonical headline. Defaults off (no tenant enrolled)
    so the live ``/evaluate`` path is unchanged until deliberately enabled per tenant.
    """
    return await flags_service.is_enabled(tenant_id, _FLAG_COHERENCE_CANARY)


async def coherence_llm_crosscheck_enabled_for_tenant(
    tenant_id: UUID,
    *,
    flags_service: TenantFlagsService,
) -> bool:
    """Return ``True`` when the LLM cross-clause contradiction depth pass is active.

    Adds a bounded LLM call per evaluation to detect semantic contradictions between clause
    pairs (beyond the always-on deterministic floor). Defaults off (no tenant enrolled) so
    the live ``/evaluate`` path incurs no extra LLM cost until deliberately enabled per tenant.
    """
    return await flags_service.is_enabled(tenant_id, _FLAG_COHERENCE_LLM_CROSSCHECK)


__all__ = [
    "coherence_canonical_canary_enabled_for_tenant",
    "coherence_llm_crosscheck_enabled_for_tenant",
    "coherence_v2_enabled_for_tenant",
]
