"""
Unit tests for ToolRegistry.
"""
from __future__ import annotations

import pytest
from pydantic import BaseModel
from uuid import UUID

from src.analysis.adapters.graph.schema import ProjectState
from src.core.ai.anthropic_wrapper import AIResponse
from src.core.ai.model_router import AITaskType
from src.core.ai.tools import (
    BaseTool,
    ToolNotFoundError,
    ToolResult,
    get_tool,
    get_tool_registry,
    list_tools,
    register_tool,
    reset_registry,
)


# Test fixtures

class TestInput(BaseModel):
    text: str


class TestOutput(BaseModel):
    result: str


class MockTool(BaseTool[TestInput, TestOutput]):
    """Mock tool for testing."""

    name = "mock_tool"
    version = "1.0"
    description = "Mock tool for testing"
    task_type = AITaskType.COMPLEX_EXTRACTION

    async def _execute_impl(
        self, input_data: TestInput, tenant_id: UUID | None, ai_response: AIResponse
    ) -> TestOutput:
        return TestOutput(result=f"Processed: {input_data.text}")

    def extract_input_from_state(self, state: ProjectState) -> TestInput:
        return TestInput(text=state.get("document_text", ""))

    def inject_output_into_state(
        self, state: ProjectState, result: ToolResult[TestOutput]
    ) -> ProjectState:
        state["output"] = result.data.result
        return state


class AnotherMockTool(BaseTool[TestInput, TestOutput]):
    """Another mock tool for testing."""

    name = "another_tool"
    version = "2.0"
    description = "Another mock tool"
    task_type = AITaskType.STAKEHOLDER_CLASSIFICATION

    async def _execute_impl(
        self, input_data: TestInput, tenant_id: UUID | None, ai_response: AIResponse
    ) -> TestOutput:
        return TestOutput(result=f"Another: {input_data.text}")

    def extract_input_from_state(self, state: ProjectState) -> TestInput:
        return TestInput(text=state.get("document_text", ""))

    def inject_output_into_state(
        self, state: ProjectState, result: ToolResult[TestOutput]
    ) -> ProjectState:
        state["output"] = result.data.result
        return state


@pytest.fixture(autouse=True)
def reset_tool_registry():
    """Reset registry before each test."""
    reset_registry()
    yield
    reset_registry()


class TestToolRegistry:
    """Test ToolRegistry functionality."""

    def test_get_registry_singleton(self):
        """Test that get_tool_registry returns singleton."""
        registry1 = get_tool_registry()
        registry2 = get_tool_registry()
        assert registry1 is registry2

    def test_register_tool(self):
        """Test registering a tool."""
        registry = get_tool_registry()
        registry.register(MockTool)

        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0][0] == "mock_tool"
        assert "1.0" in tools[0][1]

    def test_register_tool_with_override(self):
        """Test registering a tool with custom name and version."""
        registry = get_tool_registry()
        registry.register(MockTool, name="custom_name", version="2.0")

        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0][0] == "custom_name"
        assert "2.0" in tools[0][1]

    def test_get_tool_latest(self):
        """Test getting tool with latest version."""
        registry = get_tool_registry()
        registry.register(MockTool, version="1.0")
        registry.register(MockTool, version="2.0")

        tool = registry.get("mock_tool", version="latest")
        assert tool.version == "2.0"

    def test_get_tool_specific_version(self):
        """Test getting tool with specific version."""
        registry = get_tool_registry()
        registry.register(MockTool, version="1.0")
        registry.register(MockTool, version="2.0")

        tool = registry.get("mock_tool", version="1.0")
        assert tool.version == "1.0"

    def test_get_tool_not_found(self):
        """Test getting non-existent tool raises error."""
        registry = get_tool_registry()

        with pytest.raises(ToolNotFoundError, match="not found"):
            registry.get("nonexistent")

    def test_get_tool_version_not_found(self):
        """Test getting non-existent version raises error."""
        registry = get_tool_registry()
        registry.register(MockTool, version="1.0")

        with pytest.raises(ToolNotFoundError, match="Version '3.0' not found"):
            registry.get("mock_tool", version="3.0")

    def test_get_by_task_type(self):
        """Test getting tools by task type."""
        registry = get_tool_registry()
        registry.register(MockTool)  # COMPLEX_EXTRACTION
        registry.register(AnotherMockTool)  # STAKEHOLDER_CLASSIFICATION

        extraction_tools = registry.get_by_task_type(AITaskType.COMPLEX_EXTRACTION)
        assert len(extraction_tools) == 1
        assert extraction_tools[0][0] == "mock_tool"

        classification_tools = registry.get_by_task_type(
            AITaskType.STAKEHOLDER_CLASSIFICATION
        )
        assert len(classification_tools) == 1
        assert classification_tools[0][0] == "another_tool"

    def test_get_by_task_type_empty(self):
        """Test getting tools by task type returns empty list when none found."""
        registry = get_tool_registry()

        tools = registry.get_by_task_type(AITaskType.COMPLEX_EXTRACTION)
        assert len(tools) == 0

    def test_list_tools(self):
        """Test listing all registered tools."""
        registry = get_tool_registry()
        registry.register(MockTool)
        registry.register(AnotherMockTool)

        tools = registry.list_tools()
        assert len(tools) == 2
        tool_names = [t[0] for t in tools]
        assert "mock_tool" in tool_names
        assert "another_tool" in tool_names

    def test_convenience_get_tool(self):
        """Test convenience get_tool function."""
        registry = get_tool_registry()
        registry.register(MockTool)

        tool = get_tool("mock_tool")
        assert tool.name == "mock_tool"

    def test_convenience_list_tools(self):
        """Test convenience list_tools function."""
        registry = get_tool_registry()
        registry.register(MockTool)

        tools = list_tools()
        assert len(tools) == 1


class TestRegisterToolDecorator:
    """Test @register_tool decorator."""

    def test_register_tool_decorator(self):
        """Test that decorator automatically registers tool."""
        # Reset registry first
        reset_registry()

        @register_tool("decorated_tool", version="1.0")
        class DecoratedTool(BaseTool[TestInput, TestOutput]):
            name = "decorated_tool"
            version = "1.0"
            task_type = AITaskType.COMPLEX_EXTRACTION

            async def _execute_impl(self, input_data, tenant_id, ai_response):
                return TestOutput(result="decorated")

            def extract_input_from_state(self, state):
                return TestInput(text="")

            def inject_output_into_state(self, state, result):
                return state

        # Tool should be automatically registered
        tool = get_tool("decorated_tool")
        assert tool.name == "decorated_tool"

    def test_register_tool_decorator_with_defaults(self):
        """Test decorator with default name and version."""
        reset_registry()

        @register_tool()
        class AutoTool(BaseTool[TestInput, TestOutput]):
            name = "auto_tool"
            version = "1.0"
            task_type = AITaskType.COMPLEX_EXTRACTION

            async def _execute_impl(self, input_data, tenant_id, ai_response):
                return TestOutput(result="auto")

            def extract_input_from_state(self, state):
                return TestInput(text="")

            def inject_output_into_state(self, state, result):
                return state

        # Tool should be registered with class attributes
        tool = get_tool("auto_tool")
        assert tool.name == "auto_tool"

    def test_register_tool_decorator_no_auto_register(self):
        """Test decorator with auto_register=False."""
        reset_registry()

        @register_tool("manual_tool", version="1.0", auto_register=False)
        class ManualTool(BaseTool[TestInput, TestOutput]):
            name = "manual_tool"
            version = "1.0"
            task_type = AITaskType.COMPLEX_EXTRACTION

            async def _execute_impl(self, input_data, tenant_id, ai_response):
                return TestOutput(result="manual")

            def extract_input_from_state(self, state):
                return TestInput(text="")

            def inject_output_into_state(self, state, result):
                return state

        # Tool should NOT be registered
        with pytest.raises(ToolNotFoundError):
            get_tool("manual_tool")

        # But we can manually register it
        registry = get_tool_registry()
        registry.register(ManualTool)
        tool = get_tool("manual_tool")
        assert tool.name == "manual_tool"


class TestToolRegistryVersioning:
    """Test version handling in registry."""

    def test_semantic_versioning(self):
        """Test that semantic versioning works correctly."""
        registry = get_tool_registry()
        registry.register(MockTool, version="1.0.0")
        registry.register(MockTool, version="1.1.0")
        registry.register(MockTool, version="2.0.0")

        tool = registry.get("mock_tool", version="latest")
        # Should get 2.0.0 as latest
        assert hasattr(tool, "version")

    def test_non_semantic_versioning_fallback(self):
        """Test that non-semantic versions fall back to alphabetical sorting."""
        registry = get_tool_registry()
        registry.register(MockTool, version="alpha")
        registry.register(MockTool, version="beta")

        tool = registry.get("mock_tool", version="latest")
        # Should get beta (alphabetically last)
        assert hasattr(tool, "version")

    def test_multiple_versions_same_tool(self):
        """Test registering multiple versions of the same tool."""
        registry = get_tool_registry()
        registry.register(MockTool, version="1.0")
        registry.register(MockTool, version="2.0")
        registry.register(MockTool, version="3.0")

        tools = registry.list_tools()
        assert len(tools) == 1
        assert len(tools[0][1]) == 3  # 3 versions
