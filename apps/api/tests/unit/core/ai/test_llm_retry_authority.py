"""C2PRO-DEV-15 contracts for one authoritative LLM retry loop."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import anthropic
import httpx
import pytest

from src.core.ai.llm_client import LLMClient, LLMErrorType, LLMRequest


def _provider_error(
    status_code: int,
    headers: dict[str, str] | None = None,
) -> anthropic.APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(
        status_code,
        headers=headers or {},
        request=request,
    )
    return anthropic.APIStatusError(
        f"provider status {status_code}",
        response=response,
        body=None,
    )


def _bare_retry_client(*, max_retries: int = 1) -> LLMClient:
    client = object.__new__(LLMClient)
    client.circuit_breaker = None
    client.total_requests = 0
    client.total_retries = 0
    client.total_cost_usd = 0.0
    client.max_retries = max_retries
    client.initial_retry_delay = 1.0
    client.backoff_multiplier = 2.0
    client.max_retry_delay = 32.0
    client.flash_cache = SimpleNamespace(
        get=AsyncMock(return_value=None),
        set=AsyncMock(),
        size=0,
    )
    client._calculate_cost = lambda **_kwargs: 0.0
    return client


def test_llm_client_disables_anthropic_sdk_retries(monkeypatch) -> None:
    """C2Pro owns retries; the provider SDK must execute one attempt per outer attempt."""

    from src.core.ai import llm_client as module

    captured: dict[str, object] = {}

    class FakeAnthropic:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(module, "Anthropic", FakeAnthropic)
    monkeypatch.setattr(module, "ModelRouter", lambda: MagicMock())
    monkeypatch.setattr(module, "LangSmithClient", lambda: MagicMock())
    monkeypatch.setattr(module, "AIUsageLogger", lambda: MagicMock())
    monkeypatch.setattr(module, "get_flash_cache_service", lambda: MagicMock())

    LLMClient(api_key="test-key", enable_circuit_breaker=False)

    assert captured["max_retries"] == 0


def test_anthropic_wrapper_enable_retry_false_is_effective(monkeypatch) -> None:
    """The public wrapper flag must disable the C2Pro retry loop."""

    from src.core.ai import anthropic_wrapper as module

    captured: dict[str, object] = {}

    class FakeLLMClient:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(module, "LLMClient", FakeLLMClient)
    monkeypatch.setattr(module, "get_model_router", lambda: MagicMock())
    monkeypatch.setattr(module, "PiiAnonymizerService", lambda: MagicMock())

    module.AnthropicWrapper(
        api_key="test-key",
        enable_cache=False,
        enable_retry=False,
        max_retries=7,
    )

    assert captured["max_retries"] == 0


@pytest.mark.parametrize("status_code", [408, 409, 429, 500, 503])
def test_provider_retryable_statuses_are_preserved(status_code: int) -> None:
    """Provider retryable HTTP statuses remain retryable after SDK retries are disabled."""

    client = _bare_retry_client()
    error = _provider_error(status_code)

    assert client._should_retry(LLMErrorType.UNKNOWN, error) is True


def test_provider_retry_header_overrides_default_classification() -> None:
    """x-should-retry is authoritative in both directions."""

    client = _bare_retry_client()

    force_retry = _provider_error(400, {"x-should-retry": "true"})
    force_stop = _provider_error(503, {"x-should-retry": "false"})

    assert client._should_retry(LLMErrorType.UNKNOWN, force_retry) is True
    assert client._should_retry(LLMErrorType.SERVER_ERROR, force_stop) is False


def test_non_retryable_status_error_stops_cause_chain() -> None:
    """A status error rejected by provider policy must not inherit a retryable inner cause."""

    client = _bare_retry_client()
    outer = _provider_error(400)
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    outer.__cause__ = anthropic.APITimeoutError(request)

    assert client._should_retry(LLMErrorType.UNKNOWN, outer) is False


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"retry-after-ms": "2500"}, 2.5),
        ({"retry-after": "7"}, 7.0),
        ({"retry-after": "60"}, 60.0),
    ],
)
def test_provider_retry_after_controls_delay(
    headers: dict[str, str],
    expected: float,
) -> None:
    """Reasonable provider Retry-After hints override C2Pro fallback backoff."""

    client = _bare_retry_client()
    error = _provider_error(429, headers)

    assert client._calculate_retry_delay(0, LLMErrorType.RATE_LIMIT, error) == pytest.approx(
        expected
    )


def test_unreasonable_provider_retry_after_falls_back_to_c2pro_backoff(monkeypatch) -> None:
    """Provider delays above 60 seconds follow the SDK policy and are ignored."""

    client = _bare_retry_client()
    error = _provider_error(429, {"retry-after": "120"})
    monkeypatch.setattr("random.uniform", lambda *_args: 1.0)

    assert client._provider_retry_after_seconds(error) is None
    assert client._calculate_retry_delay(
        0,
        LLMErrorType.RATE_LIMIT,
        error,
    ) == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_real_llm_client_timeout_retries_once_then_succeeds(monkeypatch) -> None:
    """A provider timeout exercises the real LLMClient retry loop without network I/O."""

    from src.core.ai import llm_client as module

    client = _bare_retry_client(max_retries=1)
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    timeout = anthropic.APITimeoutError(request)
    provider_response = SimpleNamespace(
        content=[SimpleNamespace(text="ok")],
        usage=SimpleNamespace(input_tokens=2, output_tokens=1),
    )
    client.client = MagicMock()
    client.client.messages.create.side_effect = [timeout, provider_response]

    sleep = AsyncMock()
    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    monkeypatch.setattr(module, "record_ai_cache_miss", lambda *_args: None)
    monkeypatch.setattr(module, "record_ai_cache_size", lambda *_args: None)
    monkeypatch.setattr(
        module,
        "get_token_counter",
        lambda: SimpleNamespace(
            estimate_request=lambda **_kwargs: SimpleNamespace(
                input_tokens=2,
                estimated_output_tokens=1,
                total_cost_usd=0.0,
                context_usage_percent=0.0,
                warnings=[],
            )
        ),
    )

    response = await client.generate(
        LLMRequest(
            model="claude-haiku-test",
            messages=[{"role": "user", "content": "hello"}],
        )
    )

    assert response.content == "ok"
    assert response.retries == 1
    assert client.client.messages.create.call_count == 2
    sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_real_llm_client_timeout_exhaustion_raises_provider_error(monkeypatch) -> None:
    """Timeout exhaustion re-raises the provider error after the configured attempts."""

    from src.core.ai import llm_client as module

    client = _bare_retry_client(max_retries=1)
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    timeout = anthropic.APITimeoutError(request)
    client.client = MagicMock()
    client.client.messages.create.side_effect = [timeout, timeout]

    sleep = AsyncMock()
    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    monkeypatch.setattr(module, "record_ai_cache_miss", lambda *_args: None)
    monkeypatch.setattr(
        module,
        "get_token_counter",
        lambda: SimpleNamespace(
            estimate_request=lambda **_kwargs: SimpleNamespace(
                input_tokens=2,
                estimated_output_tokens=1,
                total_cost_usd=0.0,
                context_usage_percent=0.0,
                warnings=[],
            )
        ),
    )

    with pytest.raises(anthropic.APITimeoutError):
        await client.generate(
            LLMRequest(
                model="claude-haiku-test",
                messages=[{"role": "user", "content": "hello"}],
            )
        )

    assert client.client.messages.create.call_count == 2
    sleep.assert_awaited_once()


def test_wrapped_provider_timeout_remains_retryable() -> None:
    """Wrapped provider failures keep their retry semantics through __cause__."""

    client = _bare_retry_client()
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    inner = anthropic.APITimeoutError(request)
    outer = RuntimeError("middleware wrapper")
    outer.__cause__ = inner

    assert client._should_retry(LLMErrorType.UNKNOWN, outer) is True


def test_provider_retryable_error_opt_in_is_preserved() -> None:
    """Anthropic middleware RetryableError still opts into C2Pro retries."""

    client = _bare_retry_client()
    error = anthropic.RetryableError("retry from middleware")

    assert client._should_retry(LLMErrorType.UNKNOWN, error) is True


def test_wrapped_provider_retry_after_is_preserved() -> None:
    """Retry-After hints survive middleware exception wrapping."""

    client = _bare_retry_client()
    inner = _provider_error(429, {"retry-after": "5"})
    outer = RuntimeError("middleware wrapper")
    outer.__cause__ = inner

    assert client._calculate_retry_delay(
        0,
        LLMErrorType.UNKNOWN,
        outer,
    ) == pytest.approx(5.0)


def test_fallback_retry_delay_never_exceeds_configured_max(monkeypatch) -> None:
    """Jitter must not push C2Pro's fallback delay above max_retry_delay."""

    client = _bare_retry_client()
    client.max_retry_delay = 5.0
    monkeypatch.setattr("random.uniform", lambda *_args: 1.2)

    delay = client._calculate_retry_delay(
        10,
        LLMErrorType.CONNECTION,
    )

    assert delay == pytest.approx(5.0)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (None, None),
        (float("nan"), None),
        (float("inf"), None),
        (0.0, None),
        (60.1, None),
        (60.0, 60.0),
    ],
)
def test_reasonable_retry_delay_window(
    seconds: float | None,
    expected: float | None,
) -> None:
    """Provider delay acceptance matches the pinned SDK's finite 0-60s window."""

    assert LLMClient._reasonable_retry_delay(seconds) == expected


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (None, None),
        ("not-a-number", None),
        ("0", None),
        ("2500", 2.5),
        ("61000", None),
    ],
)
def test_retry_after_ms_parser(raw_value: str | None, expected: float | None) -> None:
    """retry-after-ms parsing is deterministic and bounded."""

    assert LLMClient._parse_retry_after_ms(raw_value) == expected


def test_retry_after_parser_supports_seconds_and_http_date() -> None:
    """Retry-After accepts numeric seconds and a reasonable future HTTP date."""

    assert LLMClient._parse_retry_after("7") == pytest.approx(7.0)
    assert LLMClient._parse_retry_after(None) is None
    assert LLMClient._parse_retry_after("not-a-date") is None

    future = format_datetime(datetime.now(UTC) + timedelta(seconds=30), usegmt=True)
    parsed = LLMClient._parse_retry_after(future)

    assert parsed is not None
    assert 0 < parsed <= 30


def test_invalid_retry_after_ms_falls_through_to_retry_after() -> None:
    """An invalid extension header must not hide a valid standard Retry-After."""

    client = _bare_retry_client()
    error = _provider_error(
        429,
        {
            "retry-after-ms": "invalid",
            "retry-after": "4",
        },
    )

    assert client._provider_retry_after_seconds(error) == pytest.approx(4.0)


def test_retry_after_requires_retryable_status_context() -> None:
    """Retry delay headers do not override a provider decision not to retry."""

    client = _bare_retry_client()
    error = _provider_error(
        400,
        {
            "x-should-retry": "false",
            "retry-after": "4",
        },
    )

    assert client._provider_retry_after_seconds(error) is None


@pytest.mark.parametrize(
    ("error_type", "status_code", "expected"),
    [
        (anthropic.RateLimitError, 429, LLMErrorType.RATE_LIMIT),
        (anthropic.AuthenticationError, 401, LLMErrorType.AUTHENTICATION),
        (anthropic.BadRequestError, 400, LLMErrorType.INVALID_REQUEST),
        (anthropic.NotFoundError, 404, LLMErrorType.NOT_FOUND),
        (anthropic.InternalServerError, 500, LLMErrorType.SERVER_ERROR),
    ],
)
def test_classify_provider_status_errors(
    error_type,
    status_code: int,
    expected: LLMErrorType,
) -> None:
    """Known Anthropic status errors keep their application classification."""

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code, request=request)
    error = error_type("provider error", response=response, body=None)

    assert _bare_retry_client()._classify_error(error) == expected


def test_classify_provider_connection_and_timeout_errors() -> None:
    """Connection and timeout errors retain their distinct retry categories."""

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    timeout = anthropic.APITimeoutError(request)
    connection = anthropic.APIConnectionError(request=request)

    client = _bare_retry_client()

    assert client._classify_error(timeout) == LLMErrorType.TIMEOUT
    assert client._classify_error(connection) == LLMErrorType.CONNECTION
