"""
core/ai/tools

Tool/Agent interface system for C2Pro AI orchestration.

This module provides a unified interface for AI tools that can be used as LangGraph nodes,
with full type safety, observability, and autodiscovery.

Public API:
    # Core abstractions
    Tool - Protocol defining tool interface
    BaseTool - Abstract base class with common functionality

    # Metadata and results
    ToolMetadata - Tool metadata for registry and observability
    ToolResult - Standardized result envelope with execution metadata
    ToolStatus - Execution status enum
    RetryPolicy - Retry policy configuration

    # Registry
    ToolRegistry - Central tool registry
    get_tool_registry - Get singleton registry instance
    get_tool - Get tool instance by name
    list_tools - List all registered tools
    register_tool - Decorator for automatic tool registration

    # Exceptions
    ToolError - Base exception
    ToolExecutionError - Execution failure
    ToolValidationError - Validation failure
    ToolBudgetExceededError - Budget exceeded
    ToolTimeoutError - Execution timeout
    ToolNotFoundError - Tool not found in registry

Usage:
    # Define a tool
    @register_tool("my_tool", version="1.0")
    class MyTool(BaseTool[MyInput, MyOutput]):
        name = "my_tool"
        task_type = AITaskType.COMPLEX_EXTRACTION

        async def _execute_impl(self, input_data, tenant_id, ai_response):
            # Parse and return output
            ...

        def extract_input_from_state(self, state):
            return MyInput(...)

        def inject_output_into_state(self, state, result):
            state["output"] = result.data
            return state

    # Use in LangGraph
    async def my_node(state: ProjectState) -> ProjectState:
        tool = get_tool("my_tool")
        return await tool(state)

    # Use standalone
    tool = get_tool("my_tool")
    result = await tool.execute(MyInput(...), tenant_id=...)
"""

# Core abstractions
from .base import BaseTool
from .protocol import Tool

# Metadata and results
from .metadata import RetryPolicy, ToolMetadata, ToolResult, ToolStatus

# Registry
from .registry import (
    ToolRegistry,
    get_tool,
    get_tool_registry,
    list_tools,
    register_tool,
    reset_registry,
)

# Exceptions
from .exceptions import (
    ToolBudgetExceededError,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolTimeoutError,
    ToolValidationError,
)


__all__ = [
    # Core
    "Tool",
    "BaseTool",
    # Metadata
    "ToolMetadata",
    "ToolResult",
    "ToolStatus",
    "RetryPolicy",
    # Registry
    "ToolRegistry",
    "get_tool_registry",
    "get_tool",
    "list_tools",
    "register_tool",
    "reset_registry",
    # Exceptions
    "ToolError",
    "ToolExecutionError",
    "ToolValidationError",
    "ToolBudgetExceededError",
    "ToolTimeoutError",
    "ToolNotFoundError",
]
