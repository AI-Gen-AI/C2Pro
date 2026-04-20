"""
C2Pro - Structured LLM Output Parsing (Gate S2)

parse_llm_json[T] is the ONLY sanctioned way to cross the LLM→structured-data
seam. Never call json.loads() on raw LLM output without going through this.

Design: spec-first. Each LLM call must declare its expected Pydantic schema
before the prompt is written. The schema IS the contract with the model.
"""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMSchemaError(Exception):
    """
    Raised when an LLM response cannot be parsed or fails Pydantic validation.

    Attributes:
        raw_content: Original LLM text (truncated to 500 chars for logs)
        schema_name: Name of the target Pydantic model
    """

    def __init__(
        self,
        message: str,
        raw_content: str = "",
        schema_name: str = "",
    ) -> None:
        super().__init__(message)
        self.raw_content = raw_content[:500]
        self.schema_name = schema_name


def _strip_markdown_json(content: str) -> str:
    """Strip markdown code fences and return the JSON payload."""
    content = content.strip()

    # ```json ... ```
    m = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if m:
        return m.group(1).strip()

    # ``` ... ``` (generic fence whose body starts with { or [)
    m = re.search(r"```\s*(.*?)\s*```", content, re.DOTALL)
    if m:
        candidate = m.group(1).strip()
        if candidate.startswith(("{", "[")):
            return candidate

    # Bare JSON object or array (first occurrence wins)
    m = re.search(r"(\{.*\}|\[.*\])", content, re.DOTALL)
    if m:
        return m.group(1)

    return content


def parse_llm_json(content: str, schema: type[T]) -> T:
    """
    Extract JSON from LLM output and validate it against a Pydantic model.

    Steps:
    1. Strip markdown code fences
    2. Parse JSON (raises LLMSchemaError on malformed JSON)
    3. model_validate against schema (raises LLMSchemaError on mismatch)

    Args:
        content: Raw LLM text response.
        schema:  Pydantic BaseModel subclass describing the expected shape.

    Returns:
        A validated instance of *schema*.

    Raises:
        LLMSchemaError: JSON is invalid or doesn't satisfy the schema.
    """
    schema_name = schema.__name__
    json_str = _strip_markdown_json(content)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise LLMSchemaError(
            f"LLM returned invalid JSON for {schema_name}: {exc}",
            raw_content=content,
            schema_name=schema_name,
        ) from exc

    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        raise LLMSchemaError(
            f"LLM response failed {schema_name} validation: {exc}",
            raw_content=content,
            schema_name=schema_name,
        ) from exc
