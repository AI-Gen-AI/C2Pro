"""C2PRO-DEV-15 assurance contracts for the canonical Anthropic wrapper.

Test Suite ID: TS-DEV15-AI-WRAPPER-001
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import BaseModel

from src.core.ai.anthropic_wrapper import (
    PROMPT_SEPARATOR,
    AIRequest,
    AIResponse,
    AnthropicWrapper,
)
from src.core.ai.llm_client import LLMResponse
from src.core.ai.model_router import AITaskType, ModelTier


class _FakeCache:
    def __init__(
        self,
        payload: dict[str, object] | None = None,
        *,
        fail_get: bool = False,
        fail_set: bool = False,
    ) -> None:
        self.payload = payload
        self.fail_get = fail_get
        self.fail_set = fail_set
        self.get_calls: list[str] = []
        self.set_calls: list[tuple[str, dict[str, object], int | None]] = []

    async def get_json(self, key: str) -> dict[str, object] | None:
        self.get_calls.append(key)
        if self.fail_get:
            raise RuntimeError("cache read failed")
        return self.payload

    async def set_json(
        self,
        key: str,
        value: dict[str, object],
        ttl_seconds: int | None,
    ) -> None:
        if self.fail_set:
            raise RuntimeError("cache write failed")
        self.set_calls.append((key, value, ttl_seconds))


def _bare_wrapper(*, cache: _FakeCache | None = None) -> AnthropicWrapper:
    wrapper = object.__new__(AnthropicWrapper)
    wrapper.total_requests = 0
    wrapper.cache_hits = 0
    wrapper.cache_misses = 0
    wrapper.total_cost_usd = 0.0
    wrapper.max_tokens_limit = None
    wrapper.cache_service = cache

    wrapper.anonymizer_service = MagicMock()
    wrapper.anonymizer_service.anonymize_document.return_value = SimpleNamespace(
        anonymized_text=f"safe-system{PROMPT_SEPARATOR}safe-prompt",
        mapping={},
    )

    model_config = SimpleNamespace(
        name="claude-haiku-test",
        tier=ModelTier.FLASH,
        max_tokens=2048,
    )
    wrapper.model_router = MagicMock()
    wrapper.model_router.select_model_with_budget_mode.return_value = model_config
    wrapper.model_router.estimate_cost.return_value = 0.25

    wrapper.llm_client = MagicMock()
    wrapper.llm_client.generate = AsyncMock(
        return_value=LLMResponse(
            content="safe-response",
            model="claude-haiku-test",
            input_tokens=12,
            output_tokens=7,
            cost_usd=0.0,
            request_id="llm-request",
            execution_time_ms=1.0,
            retries=1,
        )
    )
    wrapper.llm_client.get_statistics.return_value = {"total_requests": 1}
    return wrapper


def test_anthropic_wrapper_is_measured_by_coverage() -> None:
    repo_root = Path(__file__).resolve().parents[6]
    pyproject = tomllib.loads(
        (repo_root / "apps" / "api" / "pyproject.toml").read_text(encoding="utf-8")
    )
    omitted = set(pyproject["tool"]["coverage"]["run"]["omit"])

    assert "src/core/ai/anthropic_wrapper.py" not in omitted


def test_ai_request_normalizes_string_task_type() -> None:
    request = AIRequest(prompt="x", task_type="contract_extraction")

    assert request.task_type is AITaskType.CONTRACT_EXTRACTION


def test_ai_response_usage_and_total_tokens_are_consistent() -> None:
    response = AIResponse(
        content="ok",
        model_used="model",
        input_tokens=11,
        output_tokens=5,
        cost_usd=0.01,
        latency_ms=2.0,
    )

    assert response.usage == {"input_tokens": 11, "output_tokens": 5}
    assert response.total_tokens == 16


def test_cache_key_is_deterministic_within_tenant_and_isolated_across_tenants() -> None:
    wrapper = _bare_wrapper()
    tenant_a = uuid4()
    tenant_b = uuid4()

    kwargs = {
        "prompt": "same prompt",
        "system_prompt": "same system",
        "model": "claude-haiku-test",
        "temperature": 0.0,
        "max_tokens": 512,
    }

    a_first = wrapper._build_cache_key(**kwargs, tenant_id=tenant_a)
    a_second = wrapper._build_cache_key(**kwargs, tenant_id=tenant_a)
    b_key = wrapper._build_cache_key(**kwargs, tenant_id=tenant_b)

    assert a_first == a_second
    assert a_first != b_key
    assert str(tenant_a) not in a_first
    assert str(tenant_b) not in b_key
    assert a_first.startswith("llm_response:")


@pytest.mark.asyncio
async def test_generate_without_tenant_fails_closed_by_bypassing_cache() -> None:
    cache = _FakeCache(
        {
            "content": "must-not-be-used",
            "model": "claude-haiku-test",
            "input_tokens": 1,
            "output_tokens": 1,
            "cost_usd": 0.0,
        }
    )
    wrapper = _bare_wrapper(cache=cache)

    response = await wrapper.generate(
        AIRequest(
            prompt="prompt",
            task_type=AITaskType.CONTRACT_EXTRACTION,
            tenant_id=None,
        )
    )

    assert response.cached is False
    assert cache.get_calls == []
    assert cache.set_calls == []
    wrapper.llm_client.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_cache_miss_uses_tenant_scope_custom_ttl_and_caches_anonymized_content() -> None:
    cache = _FakeCache()
    wrapper = _bare_wrapper(cache=cache)
    tenant_id = uuid4()
    wrapper.max_tokens_limit = 512
    wrapper.anonymizer_service.anonymize_document.return_value = SimpleNamespace(
        anonymized_text=f"safe-system{PROMPT_SEPARATOR}safe-prompt",
        mapping={"[PERSON_001]": "Alice"},
    )
    wrapper.llm_client.generate.return_value = LLMResponse(
        content="Approved by [PERSON_001]",
        model="claude-haiku-test",
        input_tokens=12,
        output_tokens=7,
        cost_usd=0.0,
        request_id="llm-request",
        execution_time_ms=1.0,
        retries=1,
    )

    response = await wrapper.generate(
        AIRequest(
            prompt="raw prompt Alice",
            system_prompt="raw system Alice",
            task_type=AITaskType.CONTRACT_EXTRACTION,
            tenant_id=tenant_id,
            cache_ttl=123,
            max_tokens=1024,
            metadata={"source": "contract"},
        )
    )

    assert response.content == "Approved by Alice"
    assert response.cached is False
    assert response.retries == 1
    assert response.cost_usd == 0.25
    assert wrapper.total_requests == 1
    assert wrapper.cache_misses == 1
    assert wrapper.total_cost_usd == 0.25

    sent_request = wrapper.llm_client.generate.await_args.args[0]
    assert sent_request.messages == [{"role": "user", "content": "safe-prompt"}]
    assert sent_request.system == "safe-system"
    assert sent_request.max_tokens == 512
    assert sent_request.tenant_id == tenant_id
    assert sent_request.metadata == {"source": "contract"}

    assert len(cache.get_calls) == 1
    assert len(cache.set_calls) == 1
    cache_key, cached_payload, ttl = cache.set_calls[0]
    assert cache_key == cache.get_calls[0]
    assert cache_key == wrapper._build_cache_key(
        prompt="safe-prompt",
        system_prompt="safe-system",
        model="claude-haiku-test",
        temperature=0.0,
        max_tokens=512,
        tenant_id=tenant_id,
    )
    assert cached_payload["content"] == "Approved by [PERSON_001]"
    assert ttl == 123


@pytest.mark.asyncio
async def test_generate_cache_hit_rehydrates_content_and_skips_llm() -> None:
    tenant_id = uuid4()
    cache = _FakeCache(
        {
            "content": "Cached [PERSON_001]",
            "model": "claude-haiku-test",
            "input_tokens": 3,
            "output_tokens": 2,
            "cost_usd": 0.02,
        }
    )
    wrapper = _bare_wrapper(cache=cache)
    wrapper.anonymizer_service.anonymize_document.return_value = SimpleNamespace(
        anonymized_text=f"safe-system{PROMPT_SEPARATOR}safe-prompt",
        mapping={"[PERSON_001]": "Alice"},
    )

    response = await wrapper.generate(
        AIRequest(
            prompt="raw Alice",
            system_prompt="system",
            task_type=AITaskType.COHERENCE_CHECK,
            tenant_id=tenant_id,
        )
    )

    assert response.content == "Cached Alice"
    assert response.cached is True
    assert response.retries == 0
    assert wrapper.cache_hits == 1
    assert wrapper.cache_misses == 0
    wrapper.llm_client.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_uses_task_ttl_when_request_has_no_override() -> None:
    cache = _FakeCache()
    wrapper = _bare_wrapper(cache=cache)

    await wrapper.generate(
        AIRequest(
            prompt="prompt",
            task_type=AITaskType.COHERENCE_CHECK,
            tenant_id=uuid4(),
            cache_ttl=None,
        )
    )

    assert cache.set_calls[0][2] == 60 * 30


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_ttl", [0, -1, -60])
async def test_generate_non_positive_cache_ttl_falls_back_to_task_policy(
    invalid_ttl: int,
) -> None:
    cache = _FakeCache()
    wrapper = _bare_wrapper(cache=cache)

    await wrapper.generate(
        AIRequest(
            prompt="prompt",
            task_type=AITaskType.COHERENCE_CHECK,
            tenant_id=uuid4(),
            cache_ttl=invalid_ttl,
        )
    )

    assert cache.set_calls[0][2] == 60 * 30


@pytest.mark.asyncio
async def test_generate_bypass_anonymization_preserves_raw_transport_payload() -> None:
    wrapper = _bare_wrapper(cache=None)
    wrapper.anonymizer_service.anonymize_document.side_effect = AssertionError(
        "anonymizer must not be called"
    )

    await wrapper.generate(
        AIRequest(
            prompt="raw prompt",
            system_prompt="raw system",
            task_type=AITaskType.CONTRACT_EXTRACTION,
            bypass_anonymization=True,
            use_cache=False,
        )
    )

    sent_request = wrapper.llm_client.generate.await_args.args[0]
    assert sent_request.messages == [{"role": "user", "content": "raw prompt"}]
    assert sent_request.system == "raw system"


@pytest.mark.asyncio
async def test_generate_fails_closed_when_anonymization_fails() -> None:
    wrapper = _bare_wrapper(cache=None)
    wrapper.anonymizer_service.anonymize_document.side_effect = RuntimeError("pii failure")

    with pytest.raises(RuntimeError, match="pii failure"):
        await wrapper.generate(
            AIRequest(
                prompt="secret",
                task_type=AITaskType.CONTRACT_EXTRACTION,
                use_cache=False,
            )
        )

    wrapper.model_router.select_model_with_budget_mode.assert_not_called()
    wrapper.llm_client.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_propagates_llm_failure_without_caching() -> None:
    cache = _FakeCache()
    wrapper = _bare_wrapper(cache=cache)
    wrapper.llm_client.generate.side_effect = RuntimeError("provider down")

    with pytest.raises(RuntimeError, match="provider down"):
        await wrapper.generate(
            AIRequest(
                prompt="prompt",
                task_type=AITaskType.CONTRACT_EXTRACTION,
                tenant_id=uuid4(),
            )
        )

    assert cache.set_calls == []


@pytest.mark.asyncio
async def test_cache_read_and_write_failures_are_soft() -> None:
    read_fail = _bare_wrapper(cache=_FakeCache(fail_get=True))
    assert await read_fail._get_from_cache("key") is None

    write_fail = _bare_wrapper(cache=_FakeCache(fail_set=True))
    await write_fail._save_to_cache(
        cache_key="key",
        content="content",
        model="model",
        input_tokens=1,
        output_tokens=2,
        cost_usd=0.01,
        ttl=30,
    )


@pytest.mark.asyncio
async def test_cache_helpers_noop_when_cache_is_disabled() -> None:
    wrapper = _bare_wrapper(cache=None)

    assert await wrapper._get_from_cache("key") is None
    await wrapper._save_to_cache(
        cache_key="key",
        content="content",
        model="model",
        input_tokens=1,
        output_tokens=2,
        cost_usd=0.01,
        ttl=30,
    )


@pytest.mark.asyncio
async def test_generate_structured_delegates_to_shared_parser(monkeypatch) -> None:
    from src.core.ai import anthropic_wrapper as module

    class _Payload(BaseModel):
        value: int

    wrapper = _bare_wrapper(cache=None)
    wrapper.generate = AsyncMock(
        return_value=AIResponse(
            content='{"value": 7}',
            model_used="model",
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.0,
            latency_ms=1.0,
        )
    )
    expected = _Payload(value=7)
    parser = MagicMock(return_value=expected)
    monkeypatch.setattr(module, "parse_llm_json", parser)

    request = AIRequest(prompt="prompt", task_type=AITaskType.VALIDATION)
    result = await wrapper.generate_structured(request, _Payload)

    assert result == expected
    parser.assert_called_once_with('{"value": 7}', _Payload)


def test_statistics_report_zero_and_nonzero_cache_hit_rates() -> None:
    wrapper = _bare_wrapper()
    assert wrapper.get_statistics()["cache_hit_rate"] == 0

    wrapper.total_requests = 5
    wrapper.cache_hits = 3
    wrapper.cache_misses = 1
    wrapper.total_cost_usd = 1.23456

    stats = wrapper.get_statistics()

    assert stats["total_requests"] == 5
    assert stats["cache_hit_rate"] == 0.75
    assert stats["total_cost_usd"] == 1.2346
    assert stats["llm_client_stats"] == {"total_requests": 1}


@pytest.mark.parametrize(
    ("task_type", "expected_ttl"),
    [
        (AITaskType.CONTRACT_EXTRACTION, 60 * 60 * 24 * 7),
        (AITaskType.STAKEHOLDER_CLASSIFICATION, 60 * 60 * 24),
        (AITaskType.COHERENCE_CHECK, 60 * 30),
        (AITaskType.RACI_GENERATION, 60 * 60),
        (AITaskType.VALIDATION, 60 * 60),
    ],
)
def test_task_cache_ttl_policy(task_type: AITaskType, expected_ttl: int) -> None:
    wrapper = _bare_wrapper()

    assert wrapper._get_cache_ttl_for_task(task_type) == expected_ttl


def test_wrapper_init_requires_api_key(monkeypatch) -> None:
    from src.core.ai import anthropic_wrapper as module

    monkeypatch.setattr(module.settings, "anthropic_api_key", "")

    with pytest.raises(ValueError, match="Anthropic API key not configured"):
        AnthropicWrapper(api_key=None, enable_cache=False)


def test_wrapper_init_threads_retry_timeout_and_dependencies(monkeypatch) -> None:
    from src.core.ai import anthropic_wrapper as module

    captured: dict[str, object] = {}

    class _FakeLLMClient:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def get_statistics(self) -> dict[str, int]:
            return {"total_requests": 0}

    fake_router = MagicMock()
    fake_cache = MagicMock()
    fake_anonymizer = MagicMock()

    monkeypatch.setattr(module, "LLMClient", _FakeLLMClient)
    monkeypatch.setattr(module, "get_model_router", lambda: fake_router)
    monkeypatch.setattr(module, "get_cache_service", lambda: fake_cache)
    monkeypatch.setattr(module, "PiiAnonymizerService", lambda: fake_anonymizer)

    wrapper = AnthropicWrapper(
        api_key="test-key",
        enable_cache=True,
        enable_retry=False,
        max_retries=9,
        timeout_seconds=12.5,
        max_tokens_limit=777,
    )

    assert captured == {
        "api_key": "test-key",
        "max_retries": 0,
        "timeout_seconds": 12.5,
    }
    assert wrapper.model_router is fake_router
    assert wrapper.cache_service is fake_cache
    assert wrapper.anonymizer_service is fake_anonymizer
    assert wrapper.max_tokens_limit == 777
