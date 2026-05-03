"""TS-INF-PERF-056-002: LLM tracing wrapper benchmark coverage."""

from __future__ import annotations

import pytest

from tests.perf.conftest import run_async_benchmark_round


pytestmark = pytest.mark.performance


def test_mocked_traced_llm_call_has_stable_overhead(benchmark, monkeypatch: pytest.MonkeyPatch) -> None:
    """TS-INF-PERF-056-002: Benchmark disabled-tracing LLM wrapper overhead."""
    from src.core.ai.traced_llm_call import traced_llm_call

    class _DisabledLangSmithClient:
        enabled = False
        is_enabled = False

    @traced_llm_call(task_type="perf", client=_DisabledLangSmithClient())
    async def _mock_llm_call() -> dict[str, object]:
        return {
            "content": "ok",
            "model": "mock",
            "usage": {"input_tokens": 12, "output_tokens": 4, "total_tokens": 16},
        }

    result = benchmark.pedantic(
        run_async_benchmark_round,
        args=(_mock_llm_call,),
        rounds=8,
        iterations=3,
    )

    assert result["content"] == "ok"
