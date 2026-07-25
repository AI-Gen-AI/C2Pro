"""
TS-UD-MCP-RTR-001: Unit tests for MCP router standalone functions and constants.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.core.mcp.router import (
    DESTRUCTIVE_OPERATIONS,
    EXECUTE_ALLOWED_FUNCTIONS,
    EXECUTE_ALLOWED_VIEWS,
    EXECUTE_FUNCTION_TO_DB_FUNCTION,
    EXECUTE_VIEW_TO_DB_VIEW,
    _build_query_result,
    _parse_limit,
    _parse_offset,
    _require_param,
)


class TestParseLimit:
    def test_returns_int_value(self) -> None:
        assert _parse_limit({"limit": 50}) == 50

    def test_default_when_missing(self) -> None:
        assert _parse_limit({}) == 100

    def test_caps_at_1000(self) -> None:
        assert _parse_limit({"limit": 5000}) == 1000

    def test_default_zero_to_min(self) -> None:
        assert _parse_limit({"limit": 0}) == 0


class TestParseOffset:
    def test_returns_int_value(self) -> None:
        assert _parse_offset({"offset": 20}) == 20

    def test_default_zero(self) -> None:
        assert _parse_offset({}) == 0


class TestBuildQueryResult:
    def test_basic_result(self) -> None:
        data = [{"id": 1, "name": "test"}]
        result = _build_query_result(data=data, execution_time_ms=42.0, view_name="v_test")
        assert result.row_count == 1
        assert result.execution_time_ms == 42.0
        assert result.view_name == "v_test"

    def test_empty_data(self) -> None:
        result = _build_query_result(data=[], execution_time_ms=0.0, function_name="fn_test")
        assert result.row_count == 0
        assert result.function_name == "fn_test"


class TestRequireParam:
    def test_returns_value_when_present(self) -> None:
        assert _require_param({"key": "value"}, "key") == "value"

    def test_raises_on_missing(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _require_param({}, "missing")
        assert exc.value.status_code == 422

    def test_raises_on_none(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _require_param({"key": None}, "key")
        assert exc.value.status_code == 422

    def test_raises_on_empty_string(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _require_param({"key": ""}, "key")
        assert exc.value.status_code == 422


class TestExecuteAllowlists:
    """Verify the static allowlist constants are correctly configured."""

    def test_execute_allowed_views_non_empty(self) -> None:
        assert len(EXECUTE_ALLOWED_VIEWS) >= 1
        assert "projects_summary" in EXECUTE_ALLOWED_VIEWS

    def test_execute_allowed_functions_non_empty(self) -> None:
        assert len(EXECUTE_ALLOWED_FUNCTIONS) >= 1
        assert "create_alert" in EXECUTE_ALLOWED_FUNCTIONS

    def test_destructive_operations_are_known(self) -> None:
        assert "delete_all" in DESTRUCTIVE_OPERATIONS
        assert "drop_table" in DESTRUCTIVE_OPERATIONS
        assert "truncate_table" in DESTRUCTIVE_OPERATIONS

    def test_execute_view_to_db_view_maps_correctly(self) -> None:
        assert EXECUTE_VIEW_TO_DB_VIEW["projects_summary"] == "v_project_summary"
        assert EXECUTE_VIEW_TO_DB_VIEW["documents_metadata"] is None
        assert EXECUTE_VIEW_TO_DB_VIEW["audit_recent"] is None

    def test_execute_function_to_db_function_maps_correctly(self) -> None:
        assert EXECUTE_FUNCTION_TO_DB_FUNCTION["create_alert"] == "fn_create_alert"
        assert EXECUTE_FUNCTION_TO_DB_FUNCTION["trigger_recalc"] == "fn_trigger_recalc"


class TestMCPSecurity:
    """Security sanity: destructive operations blocklist."""

    def test_delete_operations_blocked(self) -> None:
        destructive = {"delete_all", "delete_tenant"}
        for op in destructive:
            assert op in DESTRUCTIVE_OPERATIONS, f"{op} must be blocked"

    def test_schema_mutation_blocked(self) -> None:
        assert "drop_table" in DESTRUCTIVE_OPERATIONS
        assert "truncate_table" in DESTRUCTIVE_OPERATIONS
        assert "modify_schema" in DESTRUCTIVE_OPERATIONS
