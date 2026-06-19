"""Feature gates for ADR-016 semantic diff.

TS-UT-CI-SEM-001
"""

from __future__ import annotations

from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)


async def is_change_semantic_llm_enabled(tenant_id: UUID) -> bool:
    """Resolve the per-tenant L2 semantic LLM gate, failing closed."""

    try:
        from src.alerts.adapters.persistence.tenant_repository import (
            SqlAlchemyTenantRepository,
        )
        from src.config import settings
        from src.core.database import get_raw_session
        from src.core.feature_flags import TenantFlagsService

        async with get_raw_session() as session:
            return await TenantFlagsService(
                tenant_repository=SqlAlchemyTenantRepository(session),
                settings=settings,
            ).is_enabled(tenant_id, "feature_v3_change_semantic_llm")
    except Exception as exc:  # noqa: BLE001 - feature flag resolution must fail closed.
        logger.warning(
            "feature_v3_change_semantic_llm_resolution_failed",
            tenant_id=str(tenant_id),
            error=str(exc),
        )
        return False


__all__ = ["is_change_semantic_llm_enabled"]
