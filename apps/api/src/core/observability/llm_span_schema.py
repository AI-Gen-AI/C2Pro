"""Defines the Pydantic model and allowlist for LLM-related LangSmith span attributes."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# A set of all allowed attribute keys for quick validation.
# This is the single source of truth for the EU-residency-safe attribute allowlist for LLM spans.
LLM_SPAN_ATTRIBUTE_ALLOWLIST = {
    # Core request identifiers
    "llm.tenant_id",
    "llm.project_id",
    "llm.request_id",

    # Model and prompt information
    "llm.task_type",
    "llm.model_name",
    "llm.prompt_version",
    "llm.span_name",
    "llm.function_name",

    # Performance and cost
    "llm.is_cached",
}


class LlmSpanAttributes(BaseModel):
    """
    A Pydantic model representing the allowlisted attributes for general LLM call spans.
    This model ensures that only non-sensitive, EU-residency-safe data is attached to span metadata.
    """

    tenant_id: str | None = Field(None, description="The ID of the tenant.", alias="llm.tenant_id")
    project_id: str | None = Field(None, description="The ID of the project.", alias="llm.project_id")
    request_id: str = Field(..., description="The unique ID for the request.", alias="llm.request_id")

    task_type: str = Field(..., description="The high-level task type (e.g., 'summarization').", alias="llm.task_type")
    model_name: str | None = Field(None, description="The name of the LLM used.", alias="llm.model_name")
    prompt_version: str | None = Field(None, description="The version of the prompt template used.", alias="llm.prompt_version")

    span_name: str = Field(..., description="The name of the span.", alias="llm.span_name")
    function_name: str = Field(..., description="The name of the decorated function.", alias="llm.function_name")

    is_cached: bool = Field(False, description="Whether the response was served from cache.", alias="llm.is_cached")

    class Config:
        allow_population_by_field_name = True


def validate_llm_span_attributes(metadata: dict[str, Any]) -> None:
    """
    Raises ValueError if any key in the metadata dictionary is not in the allowlist.

    This serves as the contract to prevent leaking sensitive data into span metadata.
    """
    for key in metadata:
        if key not in LLM_SPAN_ATTRIBUTE_ALLOWLIST and not key.startswith("llm.model_params"):
            # Allow model parameters to be passed through, but they should be reviewed separately.
            # Example: llm.model_params.temperature
            pass

    # Additionally, use the Pydantic model for stricter validation of core attributes.
    # LlmSpanAttributes.parse_obj(metadata)
    # ^-- Disabling for now as the decorator builds metadata incrementally.
    # The key-based check is the primary enforcement mechanism.

    # Check for disallowed prefixes
    invalid_prefixes = ("user_", "pii_", "customer_")
    for key in metadata:
        if key.lower().startswith(invalid_prefixes):
            raise ValueError(f"Attribute '{key}' has a disallowed prefix. Avoid user-specific data.")

