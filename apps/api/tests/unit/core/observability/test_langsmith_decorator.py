"""Unit tests for the LangSmith decorator."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.ai.llm_client import LLMRequest
from src.core.observability.langsmith_decorator import traced_llm_call

MOCK_TENANT_ID = "a4b6c8d0-9f0a-4e8c-8d6e-2f3a4b5c6d7e"

@pytest.fixture
def mock_span_client():
    """Fixture for a mock span client."""
    client = MagicMock()
    client.start_span.return_value = {"id": "mock_span_id", "url": "http://mock.url"}
    return client

@pytest.fixture
def mock_usage_logger():
    """Fixture for a mock usage logger."""
    return AsyncMock()

@pytest.fixture
def mock_langsmith_client_enabled(mock_span_client):
    """Fixture for an enabled LangSmithClient."""
    client = MagicMock()
    client.enabled = True
    client.build_tags.return_value = ["tag1", "tag2"]
    client.build_metadata.return_value = {"meta1": "value1"}
    # The decorator uses the passed in client, or creates a new one.
    # We need to make sure the one created is our mock.
    with patch("src.core.observability.langsmith_decorator.LangSmithClient") as mock_class:
        instance = mock_class.return_value
        instance.enabled = True
        instance.build_tags.return_value = ["tag1", "tag2"]
        instance.build_metadata.return_value = {"meta1": "value1"}
        yield instance


@pytest.mark.asyncio
async def test_traced_llm_call_async_success(mock_langsmith_client_enabled, mock_span_client, mock_usage_logger):
    """Test that the decorator calls start and end span on async functions."""

    class LLMClientMock:
        def __init__(self):
            self.langsmith_client = mock_span_client
            self.usage_logger = mock_usage_logger

        @traced_llm_call(task_type="test_task")
        async def sample_method(self, request: LLMRequest):
            return {"usage": {"prompt_tokens": 10, "completion_tokens": 20}}

    client = LLMClientMock()
    request = LLMRequest(
        model="test_model", messages=[], tenant_id=MOCK_TENANT_ID, project_id="proj_123"
    )

    await client.sample_method(request)

    mock_span_client.start_span.assert_called_once()
    mock_span_client.end_span.assert_called_once()
    mock_usage_logger.log_success.assert_called_once()


@pytest.mark.asyncio
async def test_traced_llm_call_uses_current_inputs_keyword(mock_langsmith_client_enabled):
    """TS-AI-LANGSMITH-002: decorator must call current LangSmith wrapper with inputs, not legacy input."""

    class StrictSpanClient:
        def __init__(self) -> None:
            self.inputs = None
            self.ended = False

        def start_span(self, name, run_type, metadata=None, inputs=None, tags=None):
            self.inputs = inputs
            return {"id": "strict_span_id", "url": "http://mock.url"}

        def end_span(self, span, outputs=None):
            self.ended = True

    strict_client = StrictSpanClient()

    @traced_llm_call(task_type="test_task")
    async def sample_function(request: LLMRequest, langsmith_client: StrictSpanClient):
        return {"usage": {"prompt_tokens": 1, "completion_tokens": 1}}

    await sample_function(
        LLMRequest(model="test_model", messages=[]),
        langsmith_client=strict_client,
    )

    assert strict_client.inputs is not None
    assert strict_client.inputs["args_count"] == 1
    assert strict_client.ended is True

@pytest.mark.asyncio
async def test_traced_llm_call_disabled(mock_span_client):
    """Test that the decorator is a no-op when disabled."""

    with patch("src.core.observability.langsmith_decorator.LangSmithClient") as mock_class:
        instance = mock_class.return_value
        instance.enabled = False

        @traced_llm_call(task_type="test_task")
        async def sample_function(request: LLMRequest, langsmith_client: MagicMock):
            return {}

        request = LLMRequest(model="test_model", messages=[])
        await sample_function(request, langsmith_client=mock_span_client)

        mock_span_client.start_span.assert_not_called()
        mock_span_client.end_span.assert_not_called()


def test_traced_llm_call_sync_success(mock_langsmith_client_enabled, mock_span_client):
    """Test that the decorator calls start and end span on sync functions."""

    @traced_llm_call(task_type="test_task")
    def sample_function(request: LLMRequest, langsmith_client: MagicMock):
        return {"usage": {"prompt_tokens": 10, "completion_tokens": 20}}

    request = LLMRequest(model="test_model", messages=[])
    sample_function(request, langsmith_client=mock_span_client)

    mock_span_client.start_span.assert_called_once()
    mock_span_client.end_span.assert_called_once()


@pytest.mark.asyncio
async def test_traced_llm_call_exception(mock_langsmith_client_enabled, mock_span_client):
    """Test that the decorator ends the span on exception."""

    @traced_llm_call(task_type="test_task")
    async def sample_function(request: LLMRequest, langsmith_client: MagicMock):
        raise ValueError("test error")

    request = LLMRequest(model="test_model", messages=[])
    with pytest.raises(ValueError):
        await sample_function(request, langsmith_client=mock_span_client)

    mock_span_client.start_span.assert_called_once()
    mock_span_client.end_span.assert_called_once()
    args, kwargs = mock_span_client.end_span.call_args
    assert kwargs["outputs"]["status"] == "error"
    assert kwargs["outputs"]["error"] == "test error"

@pytest.mark.asyncio
async def test_attribute_allowlist(mock_span_client):
    """Test that only allow-listed attributes are passed as metadata."""
    from src.core.ai.langsmith_client import LLM_SPAN_ATTRIBUTE_ALLOWLIST

    extra_metadata = {
        "allowed_key": "allowed_value",
        "disallowed_key": "pii_value",
        "tenant_id": MOCK_TENANT_ID,
    }

    with patch("src.core.observability.langsmith_decorator.LangSmithClient") as mock_class:
        instance = mock_class.return_value
        instance.enabled = True

        def side_effect(*args, **kwargs):
            metadata = kwargs.get("extra", {})
            metadata["tenant_id"] = kwargs.get("tenant_id")
            return {
                k: v for k, v in metadata.items() if k in LLM_SPAN_ATTRIBUTE_ALLOWLIST and v is not None
            }

        instance.build_metadata.side_effect = side_effect

        @traced_llm_call(task_type="test_task")
        async def sample_function(langsmith_client: MagicMock, **kwargs):
            return {}

        # The decorator will create its own LangSmithClient, which is mocked by mock_class.
        # We also pass a span_client to be extracted.
        await sample_function(langsmith_client=mock_span_client, **extra_metadata)

        mock_span_client.start_span.assert_called_once()
        call_kwargs = mock_span_client.start_span.call_args.kwargs

        metadata_sent_to_span = call_kwargs.get("metadata", {})

        assert "allowed_key" not in metadata_sent_to_span
        assert "disallowed_key" not in metadata_sent_to_span
        assert "tenant_id" in metadata_sent_to_span
        assert metadata_sent_to_span["tenant_id"] == MOCK_TENANT_ID

