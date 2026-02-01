"""
MCP Gateway Security Tests (TDD - RED Phase)

Refers to Suite ID: TS-UC-SEC-MCP-001.
Refers to Suite ID: TS-UC-SEC-MCP-002.
Refers to Suite ID: TS-UC-SEC-MCP-004.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.core.exceptions import RateLimitExceededError, SecurityException
from src.core.security.mcp_gateway import MCPGateway, MCPGatewayConfig
from src.core.security.tenant_context import (
    TenantContext,
    TenantIsolationError,
    TenantScopedCache,
)


@pytest.mark.security
@pytest.mark.gate3_mcp
class TestMCPGatewaySecurity:
    """
    Refers to Suite ID: TS-UC-SEC-MCP-001.
    Refers to Suite ID: TS-UC-SEC-MCP-002.
    Refers to Suite ID: TS-UC-SEC-MCP-004.
    """

    @pytest.mark.asyncio
    async def test_allows_valid_operation(self, mocker):
        """
        Test A: Valid allowlisted operation should pass.
        """
        audit_logger = mocker.Mock()
        gateway = MCPGateway(
            config=MCPGatewayConfig(),
            audit_logger=audit_logger,
        )
        tenant_id = uuid4()

        result = await gateway.validate_operation(
            operation="projects_summary",
            tenant_id=tenant_id,
        )

        assert result is True
        audit_logger.log_blocked_attempt.assert_not_called()

    @pytest.mark.asyncio
    async def test_blocks_invalid_operation_and_audits(self, mocker):
        """
        Test B: Invalid operation should raise SecurityException and be audited.
        """
        audit_logger = mocker.Mock()
        gateway = MCPGateway(
            config=MCPGatewayConfig(),
            audit_logger=audit_logger,
        )
        tenant_id = uuid4()

        with pytest.raises(SecurityException):
            await gateway.validate_operation(
                operation="drop_database",
                tenant_id=tenant_id,
            )

        audit_logger.log_blocked_attempt.assert_called_once()
        call_kwargs = audit_logger.log_blocked_attempt.call_args.kwargs
        assert call_kwargs["tenant_id"] == tenant_id
        assert call_kwargs["operation"] == "drop_database"
        assert call_kwargs["reason"] == "operation_not_allowlisted"

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_blocks_and_audits(self, mocker):
        """
        Test C: Exceeding 60 req/min per tenant should raise RateLimitExceededError.
        """
        audit_logger = mocker.Mock()
        time_provider = mocker.Mock(return_value=1_700_000_000.0)
        gateway = MCPGateway(
            config=MCPGatewayConfig(rate_limit_per_minute=60),
            audit_logger=audit_logger,
            time_provider=time_provider,
        )
        tenant_id = uuid4()

        for _ in range(60):
            assert await gateway.validate_operation(
                operation="projects_summary",
                tenant_id=tenant_id,
            ) is True

        with pytest.raises(RateLimitExceededError):
            await gateway.validate_operation(
                operation="projects_summary",
                tenant_id=tenant_id,
            )

        audit_logger.log_blocked_attempt.assert_called_once()
        call_kwargs = audit_logger.log_blocked_attempt.call_args.kwargs
        assert call_kwargs["tenant_id"] == tenant_id
        assert call_kwargs["operation"] == "projects_summary"
        assert call_kwargs["reason"] == "rate_limit_exceeded"

    @pytest.mark.asyncio
    async def test_unauthorized_tool_call_returns_403(self, mocker):
        """
        RED: Unauthorized MCP tool call should raise 403 Forbidden.
        """
        audit_logger = mocker.Mock()
        gateway = MCPGateway(
            config=MCPGatewayConfig(),
            audit_logger=audit_logger,
        )
        tenant_id = uuid4()

        with pytest.raises(HTTPException) as exc_info:
            await gateway.authorize_tool_call(
                operation="drop_table",
                tenant_id=tenant_id,
            )

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_query_limit_blocks_over_row_limit(self, mocker):
        """
        Enforce max 1000 rows.
        """
        gateway = MCPGateway(
            config=MCPGatewayConfig(max_rows=1000),
            audit_logger=mocker.Mock(),
        )

        with pytest.raises(SecurityException):
            await gateway.enforce_query_limits(row_count=1001, duration_seconds=1.0)

    @pytest.mark.asyncio
    async def test_query_limit_blocks_timeout(self, mocker):
        """
        Enforce max 5s timeout.
        """
        gateway = MCPGateway(
            config=MCPGatewayConfig(timeout_seconds=5),
            audit_logger=mocker.Mock(),
        )

        with pytest.raises(SecurityException):
            await gateway.enforce_query_limits(row_count=10, duration_seconds=5.1)

    @pytest.mark.asyncio
    async def test_tenant_context_isolation_blocks_cross_tenant_access(self, mocker):
        """
        Tenant A data must not be accessible when context is Tenant B.
        """
        tenant_a = uuid4()
        tenant_b = uuid4()
        backend_cache = mocker.Mock()
        backend_cache.get.return_value = {"secret": "value"}

        context = TenantContext()
        cache = TenantScopedCache(context=context, backend=backend_cache)

        token = context.set_current_tenant(tenant_b)
        try:
            with pytest.raises(TenantIsolationError):
                cache.get(tenant_id=tenant_a, key="mcp:projects_summary")
        finally:
            context.reset(token)
