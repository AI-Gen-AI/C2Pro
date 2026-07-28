"""Tests for AI usage log persistence (TASK-FRT-128)."""

from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from src.core.ai.model_router import TaskType
from src.core.ai.service import AIService


@pytest.fixture
def tenant_id() -> UUID:
    return uuid4()


@pytest.fixture
def service(tenant_id: UUID) -> AIService:
    """Create AIService with mocked dependencies."""
    with (
        patch("src.core.ai.service.get_model_router"),
        patch("src.core.ai.service.get_prompt_cache_service"),
        patch("src.core.ai.anthropic_wrapper.get_anthropic_wrapper"),
    ):
        return AIService(
            anthropic_api_key="sk-ant-test-key",
            tenant_id=tenant_id,
            budget_remaining_usd=100.0,
        )


class TestSaveUsageLog:
    @pytest.mark.asyncio
    async def test_saves_log_entry(self, service: AIService, tenant_id: UUID):
        log_success = AsyncMock()
        service.usage_logger.log_success = log_success
        with patch("src.core.ai.service.get_session_with_tenant"):
            await service._save_usage_log(
                tenant_id=tenant_id,
                project_id=None,
                model="claude-sonnet-4-20250514",
                operation=TaskType.SIMPLE_EXTRACTION,
                prompt_version="1.0",
                input_tokens=500,
                output_tokens=200,
                cost_usd=0.0035,
                cached=False,
                latency_ms=1234.56,
            )

        assert log_success.await_count == 1
        record = log_success.await_args.args[0]
        assert record.tenant_id == tenant_id
        assert record.model == "claude-sonnet-4-20250514"
        assert record.operation == TaskType.SIMPLE_EXTRACTION.value
        assert record.input_tokens == 500
        assert record.output_tokens == 200
        assert record.cost_usd == pytest.approx(0.0035)
        assert record.latency_ms == pytest.approx(1234.56)
        assert record.cached is False

    @pytest.mark.asyncio
    async def test_cached_status(self, service: AIService, tenant_id: UUID):
        log_success = AsyncMock()
        service.usage_logger.log_success = log_success
        await service._save_usage_log(
            tenant_id=tenant_id,
            project_id=None,
            model="claude-haiku-3-20241022",
            operation="custom_task",
            prompt_version=None,
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.0,
            cached=True,
            latency_ms=5.0,
        )
        assert log_success.await_count == 1
        record = log_success.await_args.args[0]
        assert record.cached is True
        assert record.operation == "custom_task"

    @pytest.mark.asyncio
    async def test_skips_when_no_tenant_id(self, service: AIService):
        with patch.object(service.usage_logger, "log_success", new=AsyncMock()) as log_success:
            await service._save_usage_log(
                tenant_id=None,
                project_id=None,
                model="claude-sonnet-4-20250514",
                operation=TaskType.SIMPLE_EXTRACTION,
                prompt_version="1.0",
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.001,
                cached=False,
                latency_ms=500.0,
            )
        assert log_success.await_count == 0

    @pytest.mark.asyncio
    async def test_db_error_does_not_propagate(self, service: AIService, tenant_id: UUID):
        with patch.object(
            service.usage_logger,
            "log_success",
            new=AsyncMock(side_effect=RuntimeError("DB connection failed")),
        ):
            # Should NOT raise
            await service._save_usage_log(
                tenant_id=tenant_id,
                project_id=None,
                model="claude-sonnet-4-20250514",
                operation=TaskType.COMPLEX_EXTRACTION,
                prompt_version="2.0",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.01,
                cached=False,
                latency_ms=2000.0,
            )

    @pytest.mark.asyncio
    async def test_project_id_and_trace_passed_through(self, service: AIService, tenant_id: UUID):
        project_id = uuid4()
        log_success = AsyncMock()
        service.usage_logger.log_success = log_success
        await service._save_usage_log(
            tenant_id=tenant_id,
            project_id=project_id,
            model="claude-opus-4-20250514",
            operation=TaskType.COMPLEX_EXTRACTION,
            prompt_version="3.0",
            input_tokens=2000,
            output_tokens=1000,
            cost_usd=0.05,
            cached=False,
            latency_ms=5000.0,
            trace_id="run-123",
            trace_url="https://smith.langchain.com/runs/run-123",
        )
        record = log_success.await_args.args[0]
        assert record.project_id == project_id
        assert record.trace_id == "run-123"
        assert record.trace_url == "https://smith.langchain.com/runs/run-123"

    @pytest.mark.asyncio
    async def test_string_operation_type(self, service: AIService, tenant_id: UUID):
        log_success = AsyncMock()
        service.usage_logger.log_success = log_success
        await service._save_usage_log(
            tenant_id=tenant_id,
            project_id=None,
            model="claude-sonnet-4-20250514",
            operation="stakeholder_extraction",
            prompt_version="1.0",
            input_tokens=300,
            output_tokens=150,
            cost_usd=0.002,
            cached=False,
            latency_ms=800.0,
        )
        record = log_success.await_args.args[0]
        assert record.operation == "stakeholder_extraction"
