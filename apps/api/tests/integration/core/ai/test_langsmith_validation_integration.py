"""TS-AI-LANGSMITH-VALIDATION-INTEGRATION: Integration tests for analytics + usage persistence."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from src.core.ai.feedback_router import get_feedback_client
from src.core.ai.models import AIUsageLogORM
from src.core.ai.usage_logger import AIUsageLogger, AIUsageLogRecord
from src.core.database import get_session


@pytest.mark.asyncio
async def test_usage_logger_persists_row_and_cost_analytics_reads_it(
    authenticated_client: AsyncClient,
    db,
    test_user,
) -> None:
    logger = AIUsageLogger()
    trace_id = "trace-integration-001"

    await logger.log_success(
        AIUsageLogRecord(
            tenant_id=test_user.tenant_id,
            project_id=None,
            model="claude-3-5-sonnet",
            operation="coherence",
            input_tokens=120,
            output_tokens=30,
            cost_usd=0.042,
            latency_ms=230,
            prompt_version="v2026-04",
            trace_id=trace_id,
            trace_url=f"https://smith.langchain.com/runs/{trace_id}",
            metadata={"prompt_tag": "coherence"},
        )
    )

    stmt = select(AIUsageLogORM).where(AIUsageLogORM.tenant_id == test_user.tenant_id, AIUsageLogORM.trace_id == trace_id)
    persisted = (await db.execute(stmt)).scalars().first()
    assert persisted is not None
    assert persisted.total_tokens == 150

    response = await authenticated_client.get("/api/v1/ai/analytics/cost?timeframe=30d")
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_requests"] >= 1
    assert any(item["prompt_version"] == "v2026-04" for item in payload["series"])


@pytest.mark.asyncio
async def test_feedback_endpoint_records_metadata_and_uses_mocked_langsmith_client(
    app,
    db,
    test_user,
    generate_token,
) -> None:
    trace_id = "trace-feedback-001"
    logger = AIUsageLogger()
    await logger.log_success(
        AIUsageLogRecord(
            tenant_id=test_user.tenant_id,
            project_id=None,
            model="claude-3-5-sonnet",
            operation="coherence",
            input_tokens=10,
            output_tokens=10,
            cost_usd=0.01,
            latency_ms=20,
            prompt_version="v-feedback",
            trace_id=trace_id,
        )
    )

    mocked_feedback = MagicMock()

    async def override_get_session():
        yield db

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_feedback_client] = lambda: mocked_feedback

    token = generate_token(
        user_id=test_user.id,
        tenant_id=test_user.tenant_id,
        email=test_user.email,
        role=test_user.role.value,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers={"Authorization": f"Bearer {token}"}) as client:
        response = await client.post(
            "/api/v1/ai/feedback",
            json={"trace_id": trace_id, "score": 0.9, "comment": "accurate"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    mocked_feedback.create_feedback.assert_called_once_with(run_id=trace_id, score=0.9, comment="accurate")

    persisted = (
        await db.execute(
            select(AIUsageLogORM).where(AIUsageLogORM.tenant_id == test_user.tenant_id, AIUsageLogORM.trace_id == trace_id)
        )
    ).scalars().one()
    assert persisted.log_metadata["feedback_score"] == pytest.approx(0.9)
    assert persisted.log_metadata["feedback_comment"] == "accurate"
