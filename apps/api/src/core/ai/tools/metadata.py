"""
core/ai/tools/metadata.py

Metadata schemas for tool registration and execution tracking.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.core.ai.model_router import AITaskType, ModelTier


# Generic output type
T = TypeVar("T")


class ToolStatus(str, Enum):
    """Tool execution status."""

    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    BUDGET_EXCEEDED = "budget_exceeded"
    VALIDATION_ERROR = "validation_error"


class RetryPolicy(BaseModel):
    """Retry policy configuration for tool execution."""

    max_retries: int = Field(2, ge=0, le=5, description="Maximum retry attempts")
    retry_on_validation_error: bool = Field(
        True, description="Retry with hardened prompt on JSON validation errors"
    )
    exponential_backoff: bool = Field(True, description="Use exponential backoff")
    initial_delay_ms: int = Field(1000, description="Initial retry delay in ms")


@dataclass
class ToolMetadata:
    """
    Complete metadata about a tool.

    This is used for:
    - Tool registry lookups
    - Observability/monitoring
    - Budget planning
    - API documentation generation
    """

    # Identity
    name: str
    version: str
    description: str

    # Type signatures (as JSON Schema)
    input_schema: dict[str, Any]  # Pydantic model JSON schema
    output_schema: dict[str, Any]  # Pydantic model JSON schema

    # Task mapping
    task_type: AITaskType  # Maps to ModelRouter task types

    # Execution configuration
    default_model_tier: ModelTier = ModelTier.STANDARD
    timeout_seconds: int = 120
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

    # Budget & permissions
    estimated_cost_usd: float | None = None  # Typical execution cost
    requires_budget_approval: bool = False
    required_permissions: list[str] = field(default_factory=list)

    # Prompt information
    prompt_template_name: str | None = None  # Reference to PromptManager template
    prompt_version: str | None = None

    # Documentation
    examples: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    # Lifecycle
    deprecated: bool = False
    deprecation_message: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ToolResult(Generic[T]):
    """
    Standardized result envelope for tool execution.

    Wraps the actual tool output with execution metadata for:
    - Observability (tokens, cost, latency)
    - Error handling (status, error messages)
    - Caching (cache hit/miss)
    - Debugging (model used, retries)

    Generic over output type T (the actual tool output).
    """

    # Output data
    data: T  # The actual tool output (Pydantic model)

    # Execution status
    status: ToolStatus
    success: bool

    # AI model metadata
    model_used: str
    input_tokens: int
    output_tokens: int
    cost_usd: float

    # Performance metrics
    latency_ms: float
    cached: bool = False
    retries: int = 0

    # Tracking
    execution_id: str = field(default_factory=lambda: str(uuid4()))
    tool_name: str = ""
    tool_version: str = ""
    prompt_version: str | None = None

    # Error handling
    error: str | None = None
    error_type: str | None = None
    validation_errors: list[str] = field(default_factory=list)

    # Timing breakdown
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime = field(default_factory=datetime.utcnow)

    # Confidence/quality scores (optional)
    confidence_score: float | None = None
    quality_score: float | None = None

    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output)."""
        return self.input_tokens + self.output_tokens

    def to_observability_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary for observability logging.

        This format is optimized for structured logging and metrics.
        """
        return {
            "execution_id": self.execution_id,
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "status": self.status.value,
            "success": self.success,
            "model_used": self.model_used,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "latency_ms": round(self.latency_ms, 2),
            "cached": self.cached,
            "retries": self.retries,
            "error": self.error,
            "error_type": self.error_type,
            "confidence_score": self.confidence_score,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
        }
