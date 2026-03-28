"""
C2Pro - Token Counter & Cost Estimator

Pre-execution token counting for cost prediction and budget control.
Uses tiktoken with cl100k_base encoding (closest approximation for Claude models).

Version: 1.0.0
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import structlog
import tiktoken

logger = structlog.get_logger()

# ===========================================
# MODEL PRICING (USD per 1M tokens)
# ===========================================

MODEL_PRICING: dict[str, dict[str, float]] = {
    # Claude 4.5 models (2025-2026)
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
    "claude-opus-4-6": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},  # Haiku 4.5 (Oct 2025)
    # Claude 4 models (2025)
    "claude-haiku-4-20250514": {"input": 0.25, "output": 1.25},
    # Claude 3.5 models
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20240620": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.25, "output": 1.25},
    # Claude 3 models
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    # Aliases (tier-based)
    "opus": {"input": 15.00, "output": 75.00},
    "sonnet": {"input": 3.00, "output": 15.00},
    "haiku": {"input": 0.25, "output": 1.25},
}

# Default pricing for unknown models (use Sonnet pricing)
DEFAULT_PRICING = {"input": 3.00, "output": 15.00}

# Token limits per model
MODEL_CONTEXT_LIMITS: dict[str, int] = {
    # Claude 4.5 models (2025-2026)
    "claude-opus-4-20250514": 200_000,
    "claude-opus-4-6": 200_000,
    "claude-sonnet-4-20250514": 200_000,
    "claude-sonnet-4-6": 200_000,
    "claude-haiku-4-5": 200_000,
    # Claude 4 models (2025)
    "claude-haiku-4-20250514": 200_000,
    "claude-3-5-sonnet-20241022": 200_000,
    "claude-3-5-sonnet-20240620": 200_000,
    "claude-3-5-haiku-20241022": 200_000,
    "claude-3-opus-20240229": 200_000,
    "claude-3-sonnet-20240229": 200_000,
    "claude-3-haiku-20240307": 200_000,
}

DEFAULT_CONTEXT_LIMIT = 200_000


# ===========================================
# DATA STRUCTURES
# ===========================================


@dataclass
class TokenEstimate:
    """Pre-execution token estimate."""

    input_tokens: int
    estimated_output_tokens: int
    total_tokens: int

    # Cost breakdown
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float

    # Model info
    model: str
    context_limit: int
    context_usage_percent: float

    # Breakdown by component
    system_tokens: int = 0
    message_tokens: int = 0

    # Warnings
    warnings: list[str] = field(default_factory=list)


@dataclass
class CostBreakdown:
    """Detailed cost breakdown for budget tracking."""

    model: str
    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float

    # Rate info
    input_rate_per_million: float
    output_rate_per_million: float


# ===========================================
# TOKEN COUNTER SERVICE
# ===========================================


class TokenCounter:
    """
    Token counting service using tiktoken.

    Uses cl100k_base encoding which provides a close approximation
    for Claude models (typically within 5-10% of actual token count).

    Usage:
        counter = TokenCounter()

        # Estimate tokens and cost before calling LLM
        estimate = counter.estimate_request(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello"}],
            system="You are a helpful assistant.",
            expected_output_tokens=500
        )

        print(f"Estimated cost: ${estimate.total_cost_usd:.4f}")
        print(f"Context usage: {estimate.context_usage_percent:.1f}%")
    """

    def __init__(self):
        """Initialize with tiktoken encoder."""
        # Use cl100k_base encoding (closest to Claude's tokenizer)
        self._encoding = tiktoken.get_encoding("cl100k_base")

        logger.debug("token_counter_initialized", encoding="cl100k_base")

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in a text string.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        if not text:
            return 0
        return len(self._encoding.encode(text))

    def count_message_tokens(self, messages: list[dict[str, Any]]) -> int:
        """
        Count tokens in a list of messages.

        Claude API uses approximately:
        - 3 tokens overhead per message
        - Content tokens
        - Role indicator (~1 token)

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Estimated token count
        """
        total = 0

        for msg in messages:
            # Message overhead (~4 tokens per message for role + formatting)
            total += 4

            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.count_tokens(content)
            elif isinstance(content, list):
                # Handle multi-part content (e.g., images + text)
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            total += self.count_tokens(part.get("text", ""))
                        elif part.get("type") == "image":
                            # Images use ~1600 tokens for 1024x1024
                            total += 1600
                    elif isinstance(part, str):
                        total += self.count_tokens(part)

        # Add reply priming overhead
        total += 3

        return total

    def estimate_request(
        self,
        model: str,
        messages: list[dict[str, Any]],
        system: str | None = None,
        expected_output_tokens: int | None = None,
        max_tokens: int = 4096,
    ) -> TokenEstimate:
        """
        Estimate tokens and cost for a request before execution.

        Args:
            model: Model identifier
            messages: List of conversation messages
            system: Optional system prompt
            expected_output_tokens: Expected output tokens (defaults to max_tokens/2)
            max_tokens: Maximum output tokens

        Returns:
            TokenEstimate with all cost and token information
        """
        warnings: list[str] = []

        # Count system tokens
        system_tokens = self.count_tokens(system) if system else 0

        # Count message tokens
        message_tokens = self.count_message_tokens(messages)

        # Total input tokens
        input_tokens = system_tokens + message_tokens

        # Estimate output tokens
        if expected_output_tokens is not None:
            estimated_output = expected_output_tokens
        else:
            # Default: assume 50% of max_tokens
            estimated_output = max_tokens // 2

        # Get model pricing
        pricing = self._get_pricing(model)

        # Calculate costs
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (estimated_output / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost

        # Get context limit
        context_limit = MODEL_CONTEXT_LIMITS.get(model, DEFAULT_CONTEXT_LIMIT)
        total_tokens = input_tokens + estimated_output
        context_usage = (total_tokens / context_limit) * 100

        # Generate warnings
        if context_usage > 90:
            warnings.append(f"High context usage ({context_usage:.1f}%) - may truncate")
        elif context_usage > 75:
            warnings.append(f"Elevated context usage ({context_usage:.1f}%)")

        if total_tokens > context_limit:
            warnings.append(f"Request exceeds context limit ({total_tokens} > {context_limit})")

        estimate = TokenEstimate(
            input_tokens=input_tokens,
            estimated_output_tokens=estimated_output,
            total_tokens=total_tokens,
            input_cost_usd=round(input_cost, 6),
            output_cost_usd=round(output_cost, 6),
            total_cost_usd=round(total_cost, 6),
            model=model,
            context_limit=context_limit,
            context_usage_percent=round(context_usage, 2),
            system_tokens=system_tokens,
            message_tokens=message_tokens,
            warnings=warnings,
        )

        logger.debug(
            "token_estimate_calculated",
            model=model,
            input_tokens=input_tokens,
            estimated_output_tokens=estimated_output,
            total_cost_usd=total_cost,
            context_usage_percent=context_usage,
        )

        return estimate

    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> CostBreakdown:
        """
        Calculate actual cost after execution.

        Args:
            model: Model identifier
            input_tokens: Actual input tokens used
            output_tokens: Actual output tokens generated

        Returns:
            CostBreakdown with detailed cost information
        """
        pricing = self._get_pricing(model)

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return CostBreakdown(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost_usd=round(input_cost, 6),
            output_cost_usd=round(output_cost, 6),
            total_cost_usd=round(input_cost + output_cost, 6),
            input_rate_per_million=pricing["input"],
            output_rate_per_million=pricing["output"],
        )

    def _get_pricing(self, model: str) -> dict[str, float]:
        """Get pricing for a model."""
        # Direct match
        if model in MODEL_PRICING:
            return MODEL_PRICING[model]

        # Match by tier name in model string
        model_lower = model.lower()
        if "opus" in model_lower:
            return MODEL_PRICING["opus"]
        elif "haiku" in model_lower:
            return MODEL_PRICING["haiku"]
        elif "sonnet" in model_lower:
            return MODEL_PRICING["sonnet"]

        logger.warning("unknown_model_pricing", model=model, using="default")
        return DEFAULT_PRICING

    def estimate_batch_cost(
        self,
        requests: list[dict[str, Any]],
        model: str | None = None,
    ) -> dict[str, Any]:
        """
        Estimate total cost for a batch of requests.

        Args:
            requests: List of request dicts with 'messages', 'system', 'model'
            model: Default model if not specified per request

        Returns:
            Summary dict with total cost and per-request breakdown
        """
        estimates = []
        total_input = 0
        total_output = 0
        total_cost = 0.0

        for req in requests:
            req_model = req.get("model", model)
            if not req_model:
                continue

            estimate = self.estimate_request(
                model=req_model,
                messages=req.get("messages", []),
                system=req.get("system"),
                expected_output_tokens=req.get("expected_output_tokens"),
                max_tokens=req.get("max_tokens", 4096),
            )

            estimates.append(estimate)
            total_input += estimate.input_tokens
            total_output += estimate.estimated_output_tokens
            total_cost += estimate.total_cost_usd

        return {
            "request_count": len(estimates),
            "total_input_tokens": total_input,
            "total_estimated_output_tokens": total_output,
            "total_estimated_cost_usd": round(total_cost, 4),
            "estimates": estimates,
        }


# ===========================================
# SINGLETON INSTANCE
# ===========================================

_token_counter: TokenCounter | None = None


def get_token_counter() -> TokenCounter:
    """
    Get singleton TokenCounter instance.

    Usage:
        from src.core.ai.token_counter import get_token_counter

        counter = get_token_counter()
        estimate = counter.estimate_request(...)
    """
    global _token_counter
    if _token_counter is None:
        _token_counter = TokenCounter()
    return _token_counter


# ===========================================
# CONVENIENCE FUNCTIONS
# ===========================================


def count_tokens(text: str) -> int:
    """Quick token count for a text string."""
    return get_token_counter().count_tokens(text)


def estimate_cost(
    model: str,
    messages: list[dict[str, Any]],
    system: str | None = None,
    expected_output_tokens: int | None = None,
) -> float:
    """Quick cost estimate for a request."""
    estimate = get_token_counter().estimate_request(
        model=model,
        messages=messages,
        system=system,
        expected_output_tokens=expected_output_tokens,
    )
    return estimate.total_cost_usd
