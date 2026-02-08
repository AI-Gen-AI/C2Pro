"""
Validate MCP Operation Use Case Tests (TDD - RED Phase)

Refers to Suite ID: TS-UA-SEC-UC-001.
"""

import pytest

from src.core.mcp.application.validate_mcp_operation_use_case import (
    ValidateMCPOperationUseCase,
)


class TestValidateMCPOperationUseCase:
    """Refers to Suite ID: TS-UA-SEC-UC-001."""

    def test_allows_known_view_and_function(self) -> None:
        use_case = ValidateMCPOperationUseCase()

        assert use_case.validate(operation_type="view", operation_name="v_project_summary")
        assert use_case.validate(operation_type="function", operation_name="fn_get_clause_by_id")

    def test_blocks_unknown_operation(self) -> None:
        use_case = ValidateMCPOperationUseCase()

        assert not use_case.validate(operation_type="view", operation_name="v_unknown")
        assert not use_case.validate(operation_type="function", operation_name="fn_unknown")

    def test_rejects_invalid_operation_type(self) -> None:
        use_case = ValidateMCPOperationUseCase()

        with pytest.raises(ValueError):
            use_case.validate(operation_type="query", operation_name="v_project_summary")
