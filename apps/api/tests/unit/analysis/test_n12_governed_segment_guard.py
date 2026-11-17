"""Bound N12 provider continuations as a FINANCIAL safeguard, never a source filter."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.core.ai.llm_client import LLMClient, LLMPartialGenerationError, LLMRequest


def _segment(stop: str, fragment: str, *, input_tokens=250, output_tokens=100):
    response = SimpleNamespace(
        stop_reason=stop,
        content=[SimpleNamespace(text=fragment)],
        usage=SimpleNamespace(
            input_tokens=input_tokens, output_tokens=output_tokens,
        ),
    )
    stream = MagicMock()
    stream.__enter__.return_value.get_final_message.return_value = response
    return stream


def _client(*segments):
    streams = MagicMock(side_effect=list(segments))
    client = object.__new__(LLMClient)
    client.client = SimpleNamespace(
        messages=SimpleNamespace(stream=streams, create=MagicMock()),
    )
    client._calculate_cost = lambda **_kwargs: 0.02
    return client, streams


def _kwargs():
    return {
        "model": "claude-sonnet-4-6",
        "max_tokens": 128_000,
        "messages": [{"role": "user", "content": "complete source"}],
        "system": "return JSON",
    }


def _request(max_segments):
    return LLMRequest(
        model="claude-sonnet-4-6",
        messages=_kwargs()["messages"],
        metadata={
            "full_source_analysis": True,
            "max_provider_segments": max_segments,
        },
    )


def test_one_segment_cap_retains_billable_fragment_and_blocks_second_call():
    client, streams = _client(_segment("max_tokens", '{"status":'))
    with pytest.raises(
        LLMPartialGenerationError, match="segment budget exhausted",
    ) as caught:
        client._complete_provider_generation(_kwargs(), _request(1))
    assert streams.call_count == 1
    assert caught.value.input_tokens == 250
    assert caught.value.output_tokens == 100
    assert caught.value.cost_usd > 0


def test_two_segments_can_complete_json_without_restart():
    client, streams = _client(
        _segment("max_tokens", '{"status":'),
        _segment("end_turn", '"OK"}'),
    )
    _, combined, inputs, outputs, continuations = client._complete_provider_generation(
        _kwargs(), _request(2),
    )
    assert combined == '{"status":"OK"}'
    assert inputs == 500 and outputs == 200
    assert continuations == 1
    assert streams.call_count == 2


def test_two_segment_budget_exhausted_records_both_fragments():
    client, streams = _client(
        _segment("max_tokens", '{"status":'),
        _segment("max_tokens", '"OK"'),
    )
    with pytest.raises(LLMPartialGenerationError, match="segment budget exhausted") as caught:
        client._complete_provider_generation(_kwargs(), _request(2))
    assert streams.call_count == 2
    assert caught.value.input_tokens == 500
    assert caught.value.output_tokens == 200


@pytest.mark.parametrize("invalid", [0, 9, -1, 2.0, "2", True])
def test_invalid_explicit_segment_policy_refused_before_provider(invalid):
    client, streams = _client()
    with pytest.raises(ValueError, match="max_provider_segments"):
        client._complete_provider_generation(_kwargs(), _request(invalid))
    streams.assert_not_called()


def test_without_governed_policy_historic_full_source_behavior_unchanged():
    client, streams = _client(
        _segment("max_tokens", '{"status":'),
        _segment("end_turn", '"OK"}'),
    )
    no_policy = LLMRequest(
        model="claude-sonnet-4-6",
        messages=_kwargs()["messages"],
        metadata={"full_source_analysis": True},
    )
    _, combined, *_ = client._complete_provider_generation(_kwargs(), no_policy)
    assert combined == '{"status":"OK"}'
    assert streams.call_count == 2
