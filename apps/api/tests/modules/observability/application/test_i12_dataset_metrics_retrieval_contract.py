"""
I12 - Dataset Metrics Retrieval Contract (RED)
Test Suite ID: TS-I12-OBS-APP-004
"""

from __future__ import annotations

import pytest

from src.modules.observability.application.ports import LangSmithAdapter


class _MockLangSmithClientForMetrics:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def get_dataset_eval_metrics(self, dataset_name: str) -> object:
        return self.payload


@pytest.mark.asyncio
async def test_i12_get_dataset_eval_metrics_returns_recent_and_baseline_red() -> None:
    """
    TS-I12-OBS-APP-004:
    adapter must return a normalized metrics payload with recent/baseline keys.
    """
    adapter = LangSmithAdapter(
        langsmith_client=_MockLangSmithClientForMetrics(
            payload={
                "recent_metrics": {"recall": 0.87, "groundedness": 0.91},
                "baseline_metrics": {"recall": 0.90, "groundedness": 0.93},
            }
        )
    )

    metrics = await adapter.get_dataset_eval_metrics("extraction_eval_dataset")

    assert metrics == {
        "recent_metrics": {"recall": 0.87, "groundedness": 0.91},
        "baseline_metrics": {"recall": 0.90, "groundedness": 0.93},
    }


@pytest.mark.asyncio
async def test_i12_get_dataset_eval_metrics_fills_missing_keys_with_empty_maps_red() -> None:
    """
    TS-I12-OBS-APP-004:
    missing top-level keys must be normalized to empty dicts, not exceptions.
    """
    adapter = LangSmithAdapter(
        langsmith_client=_MockLangSmithClientForMetrics(payload={"recent_metrics": {"recall": 0.87}})
    )

    metrics = await adapter.get_dataset_eval_metrics("partial_eval_dataset")

    assert metrics["recent_metrics"] == {"recall": 0.87}
    assert metrics["baseline_metrics"] == {}


@pytest.mark.asyncio
async def test_i12_get_dataset_eval_metrics_sanitizes_malformed_payload_red() -> None:
    """
    TS-I12-OBS-APP-004:
    malformed payloads must be sanitized to empty metric maps.
    """
    adapter = LangSmithAdapter(
        langsmith_client=_MockLangSmithClientForMetrics(
            payload={
                "recent_metrics": {"recall": "0.87", "bad_nested": {"x": 1}},
                "baseline_metrics": None,
            }
        )
    )

    metrics = await adapter.get_dataset_eval_metrics("malformed_eval_dataset")

    assert metrics == {
        "recent_metrics": {},
        "baseline_metrics": {},
    }
