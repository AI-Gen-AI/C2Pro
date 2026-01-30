"""
core/ai/tools/exceptions.py

Exception hierarchy for tool execution.
"""
from __future__ import annotations


class ToolError(Exception):
    """Base exception for all tool errors."""

    pass


class ToolExecutionError(ToolError):
    """Raised when tool execution fails."""

    def __init__(
        self,
        message: str,
        tool_name: str,
        original_error: Exception | None = None,
    ):
        self.tool_name = tool_name
        self.original_error = original_error
        super().__init__(f"Tool '{tool_name}' execution failed: {message}")


class ToolValidationError(ToolError):
    """Raised when input/output validation fails."""

    def __init__(self, message: str, validation_errors: list[str]):
        self.validation_errors = validation_errors
        super().__init__(f"Validation error: {message}")


class ToolBudgetExceededError(ToolError):
    """Raised when tool execution would exceed budget limits."""

    def __init__(self, requested_cost: float, available_budget: float):
        self.requested_cost = requested_cost
        self.available_budget = available_budget
        super().__init__(
            f"Budget exceeded: requested ${requested_cost:.4f}, "
            f"available ${available_budget:.4f}"
        )


class ToolTimeoutError(ToolError):
    """Raised when tool execution times out."""

    pass


class ToolNotFoundError(ToolError):
    """Raised when requested tool is not in registry."""

    pass
