"""
Coherence cache key registry — single source of truth (ADR-009 §G, spec §6).

All coherence-related Redis cache keys MUST be built through this module.
No inline ``f"coherence:..."`` literals are permitted anywhere else in
``apps/api/src/``.  The CI guard step in ``.github/workflows/tests.yml``
enforces this rule on every pull request.

Format
------
    coherence:{version}:{namespace}:{tenant_id}:{project_id}[:{suffix}]

Examples
--------
    coherence:coherence-v1:dashboard:aaaa...:bbbb...
    coherence:coherence-v2:diagnostics:aaaa...:bbbb...:page:2

References
----------
- ADR-009 §G  (cache key namespacing)
- Spec §6     docs/superpowers/specs/2026-05-25-ecoa-v2-hotfix-and-cutover-design.md

Suite ID: TS-UD-COH-CACHE-KEYS-001
"""

from __future__ import annotations

from typing import Final, Literal
from uuid import UUID

from src.coherence.domain.v2_constants import SCORE_VERSION_V1, SCORE_VERSION_V2

# ---------------------------------------------------------------------------
# Public type aliases — use these in type annotations across the codebase
# ---------------------------------------------------------------------------

Namespace = Literal["dashboard", "diagnostics", "aggregate", "export"]
Version = Literal["coherence-v1", "coherence-v2"]

# ---------------------------------------------------------------------------
# Internal validation sets (frozensets for O(1) lookup, immutable by design)
# ---------------------------------------------------------------------------

_VALID_NAMESPACES: Final[frozenset[str]] = frozenset(
    {"dashboard", "diagnostics", "aggregate", "export"}
)

_VALID_VERSIONS: Final[frozenset[str]] = frozenset(
    {SCORE_VERSION_V1, SCORE_VERSION_V2}
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def key(
    *,
    namespace: Namespace,
    version: Version,
    tenant_id: UUID,
    project_id: UUID,
    suffix: str | None = None,
) -> str:
    """Build a canonical coherence cache key.

    Parameters
    ----------
    namespace:
        One of ``dashboard``, ``diagnostics``, ``aggregate``, ``export``.
    version:
        One of ``SCORE_VERSION_V1`` (``"coherence-v1"``) or
        ``SCORE_VERSION_V2`` (``"coherence-v2"``).
    tenant_id:
        Tenant UUID — ensures multi-tenant isolation.
    project_id:
        Project UUID.
    suffix:
        Optional additional segment (e.g. ``"page:2"``, ``"lang:es"``).
        Appended with a ``:`` separator when provided.

    Returns
    -------
    str
        Fully formed cache key:
        ``coherence:{version}:{namespace}:{tenant_id}:{project_id}[:{suffix}]``

    Raises
    ------
    ValueError
        If *namespace* or *version* is not one of the recognised values.
    """
    if namespace not in _VALID_NAMESPACES:
        raise ValueError(
            f"Unknown cache namespace: {namespace!r}. "
            f"Valid namespaces: {sorted(_VALID_NAMESPACES)}"
        )
    if version not in _VALID_VERSIONS:
        raise ValueError(
            f"Unknown score_version: {version!r}. "
            f"Valid versions: {sorted(_VALID_VERSIONS)}"
        )

    base = f"coherence:{version}:{namespace}:{tenant_id}:{project_id}"
    return f"{base}:{suffix}" if suffix else base


def tenant_prefix(*, version: Version, tenant_id: UUID) -> str:
    """Return a Redis SCAN/UNLINK glob prefix for all keys of one tenant+version.

    Use this to iterate and invalidate all coherence keys for a specific
    score version belonging to a tenant (e.g. on flag flip).

    Parameters
    ----------
    version:
        Score version to scope the prefix to.
    tenant_id:
        Target tenant UUID.

    Returns
    -------
    str
        Glob pattern: ``coherence:{version}:*:{tenant_id}:*``

    Raises
    ------
    ValueError
        If *version* is not recognised.
    """
    if version not in _VALID_VERSIONS:
        raise ValueError(
            f"Unknown score_version: {version!r}. "
            f"Valid versions: {sorted(_VALID_VERSIONS)}"
        )
    return f"coherence:{version}:*:{tenant_id}:*"


def tenant_all_versions_prefix(*, tenant_id: UUID) -> tuple[str, str]:
    """Return both v1 and v2 SCAN prefixes for a tenant.

    Used during flag flip to invalidate both version caches atomically.

    Parameters
    ----------
    tenant_id:
        Target tenant UUID.

    Returns
    -------
    tuple[str, str]
        ``(v1_prefix, v2_prefix)`` — both glob patterns.
    """
    return (
        tenant_prefix(version=SCORE_VERSION_V1, tenant_id=tenant_id),
        tenant_prefix(version=SCORE_VERSION_V2, tenant_id=tenant_id),
    )


def project_prefix(*, tenant_id: UUID, project_id: UUID) -> str:
    """Return a Redis SCAN/UNLINK glob prefix for all keys of one project.

    Spans across all versions and namespaces. Use this after persisting a
    new coherence result to invalidate all stale project-level cache entries.

    Parameters
    ----------
    tenant_id:
        Tenant UUID (ensures cross-tenant isolation even with wildcards).
    project_id:
        Project UUID.

    Returns
    -------
    str
        Glob pattern: ``coherence:*:*:{tenant_id}:{project_id}*``
    """
    return f"coherence:*:*:{tenant_id}:{project_id}*"


__all__ = [
    "Namespace",
    "Version",
    "key",
    "project_prefix",
    "tenant_all_versions_prefix",
    "tenant_prefix",
]
