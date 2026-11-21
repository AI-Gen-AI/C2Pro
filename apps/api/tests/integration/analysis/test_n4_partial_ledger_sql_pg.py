"""Real-PostgreSQL billing and tenant-isolation proof, relocated from the pure unit lane.

Never runs in unit CI without a real disposable PostgreSQL service.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.ai.tools.risk_extraction_tool import RiskExtractionInput
from src.core.ai.tools.metadata import ToolStatus
from tests.unit.analysis.test_n4_partial_ledger_p0 import _billed_error, _tool


@pytest.mark.asyncio
async def test_n4_partial_failure_with_real_isolated_postgres_tenant_ledger(
    db: AsyncSession,
    test_tenant,
    test_tenant_2,
    monkeypatch,
) -> None:
    """Real SQL UPDATE/COMMIT via existing CostControllerService, two tenants."""
    original = _billed_error()
    tool, generate = _tool(original)
    from sqlalchemy import select

    from src.core.auth.models import Tenant

    tenant_a = test_tenant.id
    tenant_b = test_tenant_2.id
    before_a = float(test_tenant.ai_spend_current)
    before_b = float(test_tenant_2.ai_spend_current)

    @asynccontextmanager
    async def isolated_tenant_session(requested_tenant):
        assert requested_tenant == tenant_a
        yield db

    monkeypatch.setattr("src.core.database.get_session_with_tenant", isolated_tenant_session)
    result = await tool.execute(
        RiskExtractionInput(document_text="EPC contract"),
        tenant_id=tenant_a,
    )
    assert result.status is ToolStatus.FAILED
    assert generate.await_count == 1
    db.expire_all()
    current_a = (await db.execute(select(Tenant).where(Tenant.id == tenant_a))).scalar_one()
    current_b = (await db.execute(select(Tenant).where(Tenant.id == tenant_b))).scalar_one()
    assert current_a.ai_spend_current == pytest.approx(before_a + original.cost_usd)
    assert current_b.ai_spend_current == pytest.approx(before_b)

