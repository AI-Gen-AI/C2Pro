"""
Tests for core/ai/structured_output.py.

Verifies that parse_llm_json correctly handles all LLM output formats
and raises LLMSchemaError on invalid JSON or schema mismatches.
"""

import pytest
from pydantic import BaseModel

from src.core.ai.structured_output import LLMSchemaError, _strip_markdown_json, parse_llm_json


# ---------------------------------------------------------------------------
# Fixtures / helper schemas
# ---------------------------------------------------------------------------


class SimpleSchema(BaseModel):
    name: str
    value: int


class NestedSchema(BaseModel):
    title: str
    items: list[str]
    score: float = 0.0


# ---------------------------------------------------------------------------
# _strip_markdown_json
# ---------------------------------------------------------------------------


class TestStripMarkdownJson:
    def test_strips_json_fence(self):
        content = '```json\n{"key": "val"}\n```'
        assert _strip_markdown_json(content) == '{"key": "val"}'

    def test_strips_generic_fence_with_object(self):
        content = '```\n{"key": "val"}\n```'
        assert _strip_markdown_json(content) == '{"key": "val"}'

    def test_generic_fence_non_json_not_stripped(self):
        content = "```\nsome plain text\n```"
        result = _strip_markdown_json(content)
        assert "some plain text" in result

    def test_bare_json_returned_as_is(self):
        content = '{"name": "test", "value": 42}'
        assert _strip_markdown_json(content) == content

    def test_extracts_json_from_surrounding_text(self):
        content = 'Here is your answer:\n{"name": "x", "value": 1}\nDone.'
        result = _strip_markdown_json(content)
        assert result.startswith("{")

    def test_strips_whitespace(self):
        content = "  ```json\n  { }\n  ```  "
        assert _strip_markdown_json(content) == "{ }"


# ---------------------------------------------------------------------------
# parse_llm_json - happy path
# ---------------------------------------------------------------------------


class TestParseLlmJsonHappyPath:
    def test_bare_json(self):
        content = '{"name": "foo", "value": 7}'
        result = parse_llm_json(content, SimpleSchema)
        assert result.name == "foo"
        assert result.value == 7

    def test_json_in_markdown_fence(self):
        content = '```json\n{"name": "bar", "value": 3}\n```'
        result = parse_llm_json(content, SimpleSchema)
        assert result.name == "bar"
        assert result.value == 3

    def test_nested_schema(self):
        content = '{"title": "t", "items": ["a", "b"], "score": 0.9}'
        result = parse_llm_json(content, NestedSchema)
        assert result.title == "t"
        assert result.items == ["a", "b"]
        assert result.score == pytest.approx(0.9)

    def test_extra_fields_ignored(self):
        """Pydantic default: extra fields are ignored (not an error)."""
        content = '{"name": "x", "value": 1, "unexpected": true}'
        result = parse_llm_json(content, SimpleSchema)
        assert result.name == "x"

    def test_default_fields_filled(self):
        content = '{"title": "t", "items": []}'
        result = parse_llm_json(content, NestedSchema)
        assert result.score == 0.0


# ---------------------------------------------------------------------------
# parse_llm_json - error cases
# ---------------------------------------------------------------------------


class TestParseLlmJsonErrors:
    def test_invalid_json_raises(self):
        with pytest.raises(LLMSchemaError) as exc_info:
            parse_llm_json("not json at all", SimpleSchema)
        assert "SimpleSchema" in str(exc_info.value)

    def test_schema_mismatch_raises(self):
        content = '{"name": "ok", "value": "not_an_int"}'
        with pytest.raises(LLMSchemaError) as exc_info:
            parse_llm_json(content, SimpleSchema)
        assert "SimpleSchema" in str(exc_info.value)

    def test_missing_required_field_raises(self):
        content = '{"name": "only_name"}'
        with pytest.raises(LLMSchemaError):
            parse_llm_json(content, SimpleSchema)

    def test_error_stores_schema_name(self):
        try:
            parse_llm_json("{invalid", SimpleSchema)
        except LLMSchemaError as e:
            assert e.schema_name == "SimpleSchema"

    def test_error_stores_raw_content(self):
        raw = '{"name": "x", "value": "wrong"}'
        try:
            parse_llm_json(raw, SimpleSchema)
        except LLMSchemaError as e:
            assert "x" in e.raw_content

    def test_long_raw_content_truncated(self):
        raw = "a" * 1000
        try:
            parse_llm_json(raw, SimpleSchema)
        except LLMSchemaError as e:
            assert len(e.raw_content) <= 500
