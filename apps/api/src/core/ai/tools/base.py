"""
core/ai/tools/base.py

Base implementation for AI tools with common functionality.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Generic, TypeVar
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, ValidationError

from src.core.ai.anthropic_wrapper import AIRequest, AIResponse, get_anthropic_wrapper
from src.core.ai.model_router import AITaskType, ModelTier
from src.core.ai.prompts import get_prompt_manager

from .exceptions import ToolExecutionError, ToolValidationError
from .metadata import RetryPolicy, ToolMetadata, ToolResult, ToolStatus

if TYPE_CHECKING:
    from src.analysis.adapters.graph.schema import ProjectState


logger = structlog.get_logger()

# Generic types for input/output
TInput = TypeVar("TInput", bound=BaseModel)
TOutput = TypeVar("TOutput")


class BaseTool(ABC, Generic[TInput, TOutput]):
    """
    Abstract base class for AI tools.

    Provides common functionality:
    - Integration with AnthropicWrapper for LLM calls
    - Integration with PromptManager for prompt templates
    - Retry logic with validation error recovery
    - Budget checking and cost tracking
    - Observability logging
    - State extraction/injection for LangGraph

    Subclasses must implement:
    - _execute_impl(): Core tool logic
    - extract_input_from_state(): Map ProjectState -> TInput
    - inject_output_into_state(): Map ToolResult[TOutput] -> ProjectState

    Subclasses should define:
    - name: Tool name (class attribute)
    - version: Tool version (class attribute)
    - description: Tool description (class attribute)
    - task_type: AITaskType for model routing
    """

    # Tool identity (override in subclasses)
    name: str = "base_tool"
    version: str = "1.0"
    description: str = "Base tool"
    task_type: AITaskType = AITaskType.COMPLEX_EXTRACTION

    # Configuration (can override in subclasses)
    default_model_tier: ModelTier = ModelTier.STANDARD
    timeout_seconds: int = 120
    retry_policy: RetryPolicy = RetryPolicy()
    prompt_template_name: str | None = None
    prompt_version: str = "latest"

    def __init__(
        self,
        anthropic_wrapper: Any | None = None,
        prompt_manager: Any | None = None,
    ):
        """
        Initialize the tool.

        Args:
            anthropic_wrapper: AnthropicWrapper instance (uses singleton if None)
            prompt_manager: PromptManager instance (uses singleton if None)
        """
        self.anthropic_wrapper = anthropic_wrapper or get_anthropic_wrapper()
        self.prompt_manager = prompt_manager or get_prompt_manager()

        logger.info(
            "tool_initialized",
            tool_name=self.name,
            version=self.version,
            task_type=self.task_type.value,
        )

    # ============================================
    # PROTOCOL IMPLEMENTATION
    # ============================================

    @property
    def metadata(self) -> ToolMetadata:
        """Returns full metadata about this tool."""
        # Extract schemas from type hints
        input_schema = self._get_input_schema()
        output_schema = self._get_output_schema()

        return ToolMetadata(
            name=self.name,
            version=self.version,
            description=self.description,
            input_schema=input_schema,
            output_schema=output_schema,
            task_type=self.task_type,
            default_model_tier=self.default_model_tier,
            timeout_seconds=self.timeout_seconds,
            retry_policy=self.retry_policy,
            prompt_template_name=self.prompt_template_name,
            prompt_version=self.prompt_version,
        )

    async def execute(
        self,
        input_data: TInput,
        tenant_id: UUID | None = None,
        low_budget_mode: bool = False,
        **kwargs: Any,
    ) -> ToolResult[TOutput]:
        """
        Execute the tool with structured input.

        This is the main entry point that handles:
        1. Validation
        2. Prompt rendering
        3. LLM call via AnthropicWrapper
        4. Output parsing and validation
        5. Retry logic on validation errors
        6. Observability logging
        """
        start_time = time.perf_counter()
        execution_id = kwargs.get("execution_id", str(uuid4()))

        logger.info(
            "tool_execution_started",
            tool_name=self.name,
            version=self.version,
            execution_id=execution_id,
            tenant_id=str(tenant_id) if tenant_id else None,
            low_budget_mode=low_budget_mode,
        )

        try:
            # Validate input
            try:
                input_data.model_validate(input_data)
            except ValidationError as e:
                raise ToolValidationError(
                    "Input validation failed",
                    validation_errors=[str(err) for err in e.errors()],
                )

            # Execute with retry logic
            result = await self._execute_with_retry(
                input_data=input_data,
                tenant_id=tenant_id,
                low_budget_mode=low_budget_mode,
                execution_id=execution_id,
            )

            # Calculate total latency
            latency_ms = (time.perf_counter() - start_time) * 1000
            result.latency_ms = latency_ms
            result.execution_id = execution_id
            result.tool_name = self.name
            result.tool_version = self.version

            # Log observability
            logger.info("tool_execution_completed", **result.to_observability_dict())

            return result

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000

            logger.error(
                "tool_execution_failed",
                tool_name=self.name,
                version=self.version,
                execution_id=execution_id,
                error=str(e),
                error_type=type(e).__name__,
                latency_ms=round(latency_ms, 2),
            )

            # Return failed result
            return ToolResult(
                data=None,  # type: ignore
                status=ToolStatus.FAILED,
                success=False,
                model_used="",
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                latency_ms=latency_ms,
                execution_id=execution_id,
                tool_name=self.name,
                tool_version=self.version,
                error=str(e),
                error_type=type(e).__name__,
            )

    async def __call__(self, state: ProjectState) -> ProjectState:
        """
        Makes the tool callable as a LangGraph node function.

        Extracts input from state, executes tool, injects output back to state.
        """
        # Extract input from state
        input_data = self.extract_input_from_state(state)

        # Get tenant_id from state
        tenant_id = UUID(state["tenant_id"]) if state.get("tenant_id") else None

        # Execute tool
        result = await self.execute(input_data, tenant_id=tenant_id)

        # Inject output into state
        updated_state = self.inject_output_into_state(state, result)

        # Add execution message
        from langchain_core.messages import AIMessage

        updated_state["messages"].append(
            AIMessage(content=f"Tool '{self.name}' executed: {result.status.value}")
        )

        return updated_state

    # ============================================
    # ABSTRACT METHODS (subclasses must implement)
    # ============================================

    @abstractmethod
    async def _execute_impl(
        self,
        input_data: TInput,
        tenant_id: UUID | None,
        ai_response: AIResponse,
    ) -> TOutput:
        """
        Core tool implementation.

        Subclasses implement this to:
        1. Parse AI response (ai_response.content)
        2. Apply domain logic
        3. Return structured output

        Args:
            input_data: Validated input model
            tenant_id: Tenant ID for context
            ai_response: Raw response from AnthropicWrapper

        Returns:
            Structured output (Pydantic model or list/dict)
        """
        pass

    @abstractmethod
    def extract_input_from_state(self, state: ProjectState) -> TInput:
        """
        Extract tool input from LangGraph state.

        Example:
            def extract_input_from_state(self, state: ProjectState) -> RiskInput:
                return RiskInput(
                    document_text=state["document_text"],
                    max_risks=10
                )
        """
        pass

    @abstractmethod
    def inject_output_into_state(
        self, state: ProjectState, result: ToolResult[TOutput]
    ) -> ProjectState:
        """
        Inject tool result into LangGraph state.

        Example:
            def inject_output_into_state(
                self,
                state: ProjectState,
                result: ToolResult[list[RiskItem]]
            ) -> ProjectState:
                state["extracted_risks"] = [r.dict() for r in result.data]
                state["confidence_score"] = result.confidence_score or 0.0
                return state
        """
        pass

    # ============================================
    # INTERNAL METHODS
    # ============================================

    async def _execute_with_retry(
        self,
        input_data: TInput,
        tenant_id: UUID | None,
        low_budget_mode: bool,
        execution_id: str,
    ) -> ToolResult[TOutput]:
        """Execute with retry logic on validation errors."""
        last_error = None
        retries = 0

        for attempt in range(self.retry_policy.max_retries + 1):
            try:
                # Build prompt
                prompt, system_prompt = self._build_prompt(input_data, attempt > 0)

                # Call LLM via AnthropicWrapper
                ai_request = AIRequest(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    task_type=self.task_type,
                    low_budget_mode=low_budget_mode,
                    tenant_id=tenant_id,
                    metadata={"execution_id": execution_id, "attempt": attempt},
                )

                ai_response = await self.anthropic_wrapper.generate(ai_request)

                # Execute tool logic
                output_data = await self._execute_impl(
                    input_data=input_data,
                    tenant_id=tenant_id,
                    ai_response=ai_response,
                )

                # Validate output if it's a Pydantic model
                if isinstance(output_data, BaseModel):
                    output_data.model_validate(output_data)

                # Success!
                return ToolResult(
                    data=output_data,
                    status=ToolStatus.SUCCESS,
                    success=True,
                    model_used=ai_response.model_used,
                    input_tokens=ai_response.input_tokens,
                    output_tokens=ai_response.output_tokens,
                    cost_usd=ai_response.cost_usd,
                    latency_ms=ai_response.latency_ms,
                    cached=ai_response.cached,
                    retries=retries,
                )

            except (ValidationError, ValueError) as e:
                last_error = e
                retries += 1

                if attempt < self.retry_policy.max_retries:
                    logger.warning(
                        "tool_retry_validation_error",
                        tool_name=self.name,
                        attempt=attempt + 1,
                        max_retries=self.retry_policy.max_retries,
                        error=str(e),
                    )
                    continue
                else:
                    raise ToolValidationError(
                        f"Failed after {retries} retries",
                        validation_errors=[str(last_error)],
                    )

        # Should not reach here
        raise ToolExecutionError(
            "Unexpected retry loop exit", tool_name=self.name, original_error=last_error
        )

    def _build_prompt(
        self, input_data: TInput, is_retry: bool = False
    ) -> tuple[str, str | None]:
        """
        Build prompt from input data.

        If tool has prompt_template_name, uses PromptManager.
        Otherwise, subclass should override this method.
        """
        if self.prompt_template_name:
            # Use PromptManager
            system, user, _ = self.prompt_manager.render_prompt(
                task_name=self.prompt_template_name,
                context=input_data.model_dump(),
                version=self.prompt_version,
            )

            if is_retry:
                # Add hardening instructions on retry
                user = (
                    f"{user}\n\n"
                    "IMPORTANTE: Responde SOLO con JSON válido. "
                    "No uses Markdown, no agregues explicaciones."
                )

            return user, system
        else:
            # Fallback: subclass should override
            return self._build_default_prompt(input_data, is_retry)

    def _build_default_prompt(
        self, input_data: TInput, is_retry: bool
    ) -> tuple[str, str | None]:
        """Override in subclass if not using PromptManager."""
        raise NotImplementedError(
            f"Tool '{self.name}' must either set prompt_template_name "
            "or override _build_default_prompt()"
        )

    def _get_input_schema(self) -> dict[str, Any]:
        """Extract JSON schema from input type hint."""
        # Use type hints to get TInput type
        # This requires Python 3.10+ get_type_hints()
        try:
            from typing import get_args, get_origin

            bases = getattr(self.__class__, "__orig_bases__", [])
            for base in bases:
                if get_origin(base) is BaseTool or (
                    hasattr(base, "__name__") and "BaseTool" in base.__name__
                ):
                    args = get_args(base)
                    if args and len(args) >= 1:
                        input_type = args[0]
                        if hasattr(input_type, "model_json_schema"):
                            return input_type.model_json_schema()
        except Exception:
            pass
        return {}

    def _get_output_schema(self) -> dict[str, Any]:
        """Extract JSON schema from output type hint."""
        try:
            from typing import get_args, get_origin

            bases = getattr(self.__class__, "__orig_bases__", [])
            for base in bases:
                if get_origin(base) is BaseTool or (
                    hasattr(base, "__name__") and "BaseTool" in base.__name__
                ):
                    args = get_args(base)
                    if args and len(args) >= 2:
                        output_type = args[1]
                        if hasattr(output_type, "model_json_schema"):
                            return output_type.model_json_schema()
        except Exception:
            pass
        return {}
