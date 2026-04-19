"""Tests for AI usage log persistence (TASK-FRT-128)."""

from unittest.mock import AsyncMock, MagicMock, patch
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
        patch("src.core.ai.service.Anthropic"),
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
        mock_session = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.core.ai.service.get_session_with_tenant", return_value=mock_ctx):
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

        mock_session.add.assert_called_once()
        log_entry = mock_session.add.call_args[0][0]
        assert log_entry.tenant_id == tenant_id
        assert log_entry.model_name == "claude-sonnet-4-20250514"
        assert log_entry.operation_type == TaskType.SIMPLE_EXTRACTION.value
        assert log_entry.input_tokens == 500
        assert log_entry.output_tokens == 200
        assert log_entry.total_tokens == 700
        assert float(log_entry.estimated_cost) == pytest.approx(0.0035)
        assert log_entry.duration_ms == 1235
        assert log_entry.status == "success"
        assert log_entry.log_metadata == {"prompt_version": "1.0", "cached": False}

    @pytest.mark.asyncio
    async def test_cached_status(self, service: AIService, tenant_id: UUID):
        mock_session = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.core.ai.service.get_session_with_tenant", return_value=mock_ctx):
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

        log_entry = mock_session.add.call_args[0][0]
        assert log_entry.status == "cached"
        assert log_entry.operation_type == "custom_task"
        assert log_entry.log_metadata == {"prompt_version": None, "cached": True}

    @pytest.mark.asyncio
    async def test_skips_when_no_tenant_id(self, service: AIService):
        with patch("src.core.ai.service.get_session_with_tenant") as mock_get_session:
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

        mock_get_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_error_does_not_propagate(self, service: AIService, tenant_id: UUID):
        with patch(
            "src.core.ai.service.get_session_with_tenant",
            side_effect=RuntimeError("DB connection failed"),
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
    async def test_project_id_passed_through(self, service: AIService, tenant_id: UUID):
        project_id = uuid4()
        mock_session = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.core.ai.service.get_session_with_tenant", return_value=mock_ctx):
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
            )

        log_entry = mock_session.add.call_args[0][0]
        assert log_entry.project_id == project_id

    @pytest.mark.asyncio
    async def test_string_operation_type(self, service: AIService, tenant_id: UUID):
        mock_session = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.core.ai.service.get_session_with_tenant", return_value=mock_ctx):
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

        log_entry = mock_session.add.call_args[0][0]
        assert log_entry.operation_type == "stakeholder_extraction"
