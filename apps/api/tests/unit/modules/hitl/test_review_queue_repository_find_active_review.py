"""
Unit coverage for SqlAlchemyReviewQueueRepository.find_active_review
(C2PRO P0b HITL resume hotfix idempotency lookup), against a mocked
AsyncSession -- exercises both the tenant-scoped and tenant-less branches
directly, without a real database.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.modules.hitl.adapters.persistence.repository import (
    SqlAlchemyReviewQueueRepository,
)


def _session_returning(orm_row: object | None) -> AsyncMock:
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalars.return_value.first.return_value = orm_row
    session.execute = AsyncMock(return_value=execute_result)
    return session


async def test_find_active_review_scopes_by_tenant_when_tenant_id_is_set() -> None:
    session = _session_returning(None)
    repo = SqlAlchemyReviewQueueRepository(session=session, tenant_id=uuid4())

    result = await repo.find_active_review(document_id=uuid4(), review_type="analysis_critique")

    assert result is None
    session.execute.assert_awaited_once()


async def test_find_active_review_skips_tenant_filter_when_tenant_id_is_none() -> None:
    """Admin/cross-tenant callers (tenant_id=None) must still query cleanly."""
    session = _session_returning(None)
    repo = SqlAlchemyReviewQueueRepository(session=session, tenant_id=None)

    result = await repo.find_active_review(document_id=uuid4(), review_type="analysis_critique")

    assert result is None
    session.execute.assert_awaited_once()
