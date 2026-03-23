"""
TS-INT-EXT-LLM-001: LLM client pricing source-of-truth tests.
"""

from types import SimpleNamespace

from src.core.ai.llm_client import LLMClient
from src.core.ai.model_router import ModelTier


class _FakeRouter:
    def __init__(self) -> None:
        self.named = {
            "custom-model": SimpleNamespace(cost_per_1m_input=7.0, cost_per_1m_output=11.0)
        }
        self.by_tier = {
            ModelTier.FLASH: SimpleNamespace(cost_per_1m_input=0.4, cost_per_1m_output=0.8),
            ModelTier.STANDARD: SimpleNamespace(cost_per_1m_input=1.0, cost_per_1m_output=2.0),
            ModelTier.POWERFUL: SimpleNamespace(cost_per_1m_input=9.0, cost_per_1m_output=18.0),
        }

    def get_model_by_name(self, name: str):
        return self.named.get(name)

    def get_model_by_tier(self, tier: ModelTier):
        return self.by_tier[tier]

    def estimate_cost(self, model, input_tokens: int, output_tokens: int) -> float:
        return round(
            (input_tokens / 1_000_000) * model.cost_per_1m_input
            + (output_tokens / 1_000_000) * model.cost_per_1m_output,
            6,
        )


def test_calculate_cost_uses_model_router_named_pricing(monkeypatch) -> None:
    monkeypatch.setattr("src.core.ai.llm_client.Anthropic", lambda **_: object())
    monkeypatch.setattr("src.core.ai.llm_client.ModelRouter", lambda: _FakeRouter())

    client = LLMClient(api_key="test-key", enable_circuit_breaker=False)

    cost = client._calculate_cost("custom-model", input_tokens=1_000_000, output_tokens=1_000_000)

    assert cost == 18.0


def test_calculate_cost_uses_model_router_tier_fallback(monkeypatch) -> None:
    monkeypatch.setattr("src.core.ai.llm_client.Anthropic", lambda **_: object())
    monkeypatch.setattr("src.core.ai.llm_client.ModelRouter", lambda: _FakeRouter())

    client = LLMClient(api_key="test-key", enable_circuit_breaker=False)

    cost = client._calculate_cost("claude-haiku-unknown-build", input_tokens=1_000_000, output_tokens=1_000_000)

    assert cost == 1.2
