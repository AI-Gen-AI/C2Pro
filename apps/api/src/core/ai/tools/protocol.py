"""
core/ai/tools/protocol.py

Defines the Tool protocol that all AI tools must implement.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, TypeVar, runtime_checkable
from uuid import UUID

from pydantic import BaseModel

from .metadata import ToolMetadata, ToolResult

if TYPE_CHECKING:
    from src.analysis.adapters.graph.schema import ProjectState


# Generic input/output types
TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput", covariant=True)


@runtime_checkable
class Tool(Protocol[TInput, TOutput]):
    """
    Protocol for AI tools that can be used as LangGraph nodes.

    Tools are stateless, reusable components that:
    1. Accept structured input (Pydantic models)
    2. Call LLMs via AnthropicWrapper
    3. Return structured output (Pydantic models) wrapped in ToolResult
    4. Track execution metadata (cost, tokens, latency)
    5. Integrate with observability systems

    Tools work directly as LangGraph nodes by implementing the __call__ signature
    that accepts and returns ProjectState (or other TypedDict state types).

    Example:
        @register_tool("risk_extraction", version="1.0")
        class RiskExtractionTool(BaseTool[RiskExtractionInput, list[RiskItem]]):
            '''Extracts risks from contract documents'''

            async def execute(
                self,
                input_data: RiskExtractionInput,
                tenant_id: UUID | None = None
            ) -> ToolResult[list[RiskItem]]:
                # Implementation here
                pass

        # Use as LangGraph node
        async def risk_node(state: ProjectState) -> ProjectState:
            tool = get_tool("risk_extraction")
            return await tool(state)  # Calls __call__
    """

    # Tool identity
    name: str
    version: str
    description: str

    # Metadata
    @property
    def metadata(self) -> ToolMetadata:
        """Returns full metadata about this tool."""
        ...

    # Core execution method
    async def execute(
        self, input_data: TInput, tenant_id: UUID | None = None, **kwargs: Any
    ) -> ToolResult[TOutput]:
        """
        Execute the tool with structured input.

        Args:
            input_data: Validated input model
            tenant_id: Tenant ID for multi-tenancy and budget tracking
            **kwargs: Additional execution parameters

        Returns:
            ToolResult containing the output data plus execution metadata

        Raises:
            ToolExecutionError: If execution fails
            ToolValidationError: If input validation fails
            ToolBudgetExceededError: If budget limit reached
        """
        ...

    # LangGraph integration - Tools can be called directly with state
    async def __call__(self, state: ProjectState) -> ProjectState:
        """
        Makes the tool callable as a LangGraph node function.

        This method extracts relevant data from state, calls execute(),
        and updates the state with results.

        Args:
            state: LangGraph state (ProjectState TypedDict)

        Returns:
            Updated state with tool results
        """
        ...

    # State extraction/injection (for LangGraph integration)
    def extract_input_from_state(self, state: ProjectState) -> TInput:
        """
        Extract tool input from LangGraph state.

        Each tool defines how to map ProjectState fields to its input model.
        """
        ...

    def inject_output_into_state(
        self, state: ProjectState, result: ToolResult[TOutput]
    ) -> ProjectState:
        """
        Inject tool result into LangGraph state.

        Each tool defines how to map its output back to ProjectState fields.
        """
        ...
