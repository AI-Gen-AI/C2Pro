"""
Feature flag dependency for FastAPI endpoints.

Provides ``require_feature`` — a dependency factory that returns HTTP 404
when a feature flag is disabled, keeping unreleased endpoints invisible.

Usage::

    from src.core.middleware.feature_flags import require_feature

    router = APIRouter(dependencies=[Depends(require_feature("feature_coherence_analysis"))])

    # Or on a single endpoint:
    @router.get("/foo", dependencies=[Depends(require_feature("feature_raci_generation"))])
    async def foo(): ...
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import HTTPException, status


def require_feature(flag_name: str) -> Callable[[], None]:
    """Return a FastAPI dependency that blocks requests when *flag_name* is ``False``."""

    def _guard() -> None:
        from src.config import settings

        if not getattr(settings, flag_name, False):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Not Found",
            )

    return _guard
