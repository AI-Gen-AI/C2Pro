"""
MCP gateway audit logging adapter tests.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.mcp.adapters.mcp_audit import MCPAuditEventType, MCPAuditLogger


@pytest.mark.asyncio
class TestMCPAuditLogger:
    """Refers to Suite ID: TS-UC-SEC-MCP-004"""

    async def test_001_log_operation_allowed_creates_event(self) -> None:
        logger = MCPAuditLogger()
        await logger.log_operation_allowed("tenant_a", "view_projects_summary")
        events = await logger.list_events()
        assert len(events) == 1
        assert events[0].event_type == MCPAuditEventType.OPERATION_ALLOWED

    async def test_002_log_operation_blocked_creates_event(self) -> None:
        logger = MCPAuditLogger()
        await logger.log_operation_blocked("tenant_a", "drop_table", "destructive_operation")
        events = await logger.list_events()
        assert len(events) == 1
        assert events[0].event_type == MCPAuditEventType.OPERATION_BLOCKED

    async def test_003_event_contains_tenant_id(self) -> None:
        logger = MCPAuditLogger()
        await logger.log_operation_allowed("tenant_42", "view_alerts_active")
        event = (await logger.list_events())[0]
        assert event.tenant_id == "tenant_42"

    async def test_004_event_contains_normalized_operation_name(self) -> None:
        logger = MCPAuditLogger()
        await logger.log_operation_allowed("tenant_a", "  VIEW_PROJECTS_SUMMARY  ")
        event = (await logger.list_events())[0]
        assert event.operation_name == "view_projects_summary"

    async def test_005_blocked_event_contains_reason(self) -> None:
        logger = MCPAuditLogger()
        await logger.log_operation_blocked("tenant_a", "unknown", "not_allowlisted")
        event = (await logger.list_events())[0]
        assert event.reason == "not_allowlisted"

    async def test_006_events_are_ordered_by_timestamp(self) -> None:
        class _Clock:
            def __init__(self) -> None:
                self._value = datetime(2026, 2, 5, 10, 0, 0, tzinfo=timezone.utc)

            def now(self) -> datetime:
                current = self._value
                self._value = self._value.replace(second=self._value.second + 1)
                return current

        clock = _Clock()
        logger = MCPAuditLogger(datetime_provider=clock.now)
        await logger.log_operation_allowed("tenant_a", "op_1")
        await logger.log_operation_blocked("tenant_a", "op_2", "blocked")
        events = await logger.list_events()
        assert events[0].timestamp <= events[1].timestamp

    async def test_007_list_events_for_tenant_filters_results(self) -> None:
        logger = MCPAuditLogger()
        await logger.log_operation_allowed("tenant_a", "op_1")
        await logger.log_operation_allowed("tenant_b", "op_2")
        tenant_events = await logger.list_events(tenant_id="tenant_a")
        assert len(tenant_events) == 1
        assert tenant_events[0].tenant_id == "tenant_a"

    async def test_008_list_events_limit_returns_latest_n(self) -> None:
        logger = MCPAuditLogger()
        await logger.log_operation_allowed("tenant_a", "op_1")
        await logger.log_operation_allowed("tenant_a", "op_2")
        await logger.log_operation_allowed("tenant_a", "op_3")
        limited = await logger.list_events(limit=2)
        assert len(limited) == 2
        assert [event.operation_name for event in limited] == ["op_2", "op_3"]

    async def test_009_sensitive_query_text_is_redacted_from_metadata(self) -> None:
        logger = MCPAuditLogger()
        await logger.log_operation_blocked(
            tenant_id="tenant_a",
            operation_name="execute_query",
            reason="query_limit",
            metadata={"query": "SELECT * FROM auth.users WHERE email='x@y.com'"},
        )
        event = (await logger.list_events())[0]
        assert event.metadata["query"] == "[REDACTED]"

    async def test_010_invalid_tenant_or_operation_raises(self) -> None:
        logger = MCPAuditLogger()
        with pytest.raises(ValueError, match="Tenant ID cannot be empty or None"):
            await logger.log_operation_allowed("", "view_projects_summary")
        with pytest.raises(ValueError, match="Operation name cannot be empty or None"):
            await logger.log_operation_allowed("tenant_a", "")
