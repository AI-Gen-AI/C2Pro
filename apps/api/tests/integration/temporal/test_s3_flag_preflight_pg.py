"""Regression: fresh real-AI S3 guard initializes its DB session in this process.

The test runner supplies an isolated PostgreSQL database; there are no AI calls,
no workflow dispatches, and no production data.
"""

from uuid import UUID

import pytest

from src.alerts.adapters.persistence.tenant_repository import SqlAlchemyTenantRepository
from src.config import settings
from src.core.database import get_raw_session, init_db
from src.core.feature_flags import TenantFlagsService


@pytest.mark.asyncio
async def test_s3_flag_guard_can_read_seeded_tenant_after_process_db_init(
    db, test_tenant, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "feature_v3_coherence_llm", True)
    monkeypatch.setattr(settings, "feature_v3_project_graph", True)
    monkeypatch.setattr(settings, "skip_hitl", False)
    monkeypatch.setattr(settings, "ai_mock", False)

    await init_db()
    async with get_raw_session() as session:
        assert await TenantFlagsService(
            tenant_repository=SqlAlchemyTenantRepository(session),
            settings=settings,
        ).is_enabled(UUID(str(test_tenant.id)), "feature_v3_coherence_llm")
