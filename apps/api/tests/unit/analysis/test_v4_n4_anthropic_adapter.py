"""N4 Anthropic adapter contract: no real provider called in unit tests."""
from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.analysis.adapters.ai.n4_anthropic_window_provider import (
    AnthropicN4WindowProvider,
    _v2_provider_response,
)
from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.core.ai.model_router import AITaskType, ModelTier


class _FakeWrapper:
    def __init__(self, *, retries=0, cache=False, tool_name="record_window_findings",
                 raw_available=True, stop_reason="tool_use"):
        self.llm_client = SimpleNamespace(max_retries=retries)
        self.enable_cache = cache
        self.cache_service = object() if cache else None
        self.model_router = SimpleNamespace(
            configs={ModelTier.STANDARD: SimpleNamespace(name="unit-model")}
        )
        self.calls = []
        self.tool_name = tool_name
        self.raw_available = raw_available
        self.stop_reason = stop_reason

    async def generate(self, request):
        self.calls.append(request)
        content = ('{"window_examined":true,"findings":[],'
                   '"outstanding_references":[]}')
        tool_use = SimpleNamespace(
            type="tool_use", name=self.tool_name, input=json.loads(content),
        )
        raw_response = (
            SimpleNamespace(
                stop_reason=self.stop_reason, content=[tool_use],
            ) if self.raw_available else None
        )
        return SimpleNamespace(
            content=content, raw_response=raw_response,
            model_used="unit-model",
            cost_usd=0.012345, input_tokens=107, output_tokens=61,
        )


@pytest.mark.asyncio
async def test_window_provider_disables_retry_cache_and_full_source_continuation():
    wrapper = _FakeWrapper()
    provider = AnthropicN4WindowProvider(
        wrapper=wrapper, tier=ModelTier.STANDARD,
        max_output_tokens=1024,
    )
    w = plan_n4_source_windows(
        "Contract Clause 9.6 shall apply to all deliverables.",
        revision_id=str(uuid4()),
    )[0]
    response = await provider.generate(
        window=w, tenant_id=uuid4(), request_id="reservation-id",
    )
    req = wrapper.calls[0]
    assert provider.model_name == response.model_used == "unit-model"
    assert response.reported_cost_usd == "0.012345"
    assert response.input_tokens == 107
    assert response.provider_request_id == "reservation-id"
    assert req.use_cache is False
    assert req.bypass_anonymization is True
    assert req.task_type is AITaskType.CONTRACT_EXTRACTION
    assert req.force_model_tier is ModelTier.STANDARD
    assert req.request_id == "reservation-id"
    assert req.max_tokens == 1024
    assert req.metadata["n4_incremental_window"] is True
    assert req.metadata.get("full_source_analysis") is not True
    assert "Contract Clause 9.6" in req.prompt


@pytest.mark.parametrize("kwargs", [
    {"retries": 1},
    {"cache": True},
])
def test_adapter_refuses_hidden_retries_or_caches(kwargs):
    with pytest.raises(ValueError):
        AnthropicN4WindowProvider(wrapper=_FakeWrapper(**kwargs))


@pytest.mark.parametrize("max_output", [1, 255, 16385, 20000])
def test_excessive_or_inadequate_output_caps_rejected(max_output):
    with pytest.raises(ValueError):
        AnthropicN4WindowProvider(
            wrapper=_FakeWrapper(), max_output_tokens=max_output,
        )



@pytest.mark.asyncio
async def test_v2_forced_tool_and_versioned_clause_inventory_without_network():
    from src.analysis.domain.n4_compact_window_response import (
        N4_WINDOW_PROMPT_VERSION,
    )
    wrapper = _FakeWrapper()
    provider = AnthropicN4WindowProvider(wrapper=wrapper)
    w = plan_n4_source_windows(
        "SECTION 1 Payment terms\n"
        "1.1 The contractor shall provide a performance guarantee.\n"
        "SECCIÓN 2 Plazos\n"
        "2.1 La entrega deberá ser puntual.\n"
        "SEÇÃO 3 Condições\n"
        "3.1 O pagamento deverá ocorrer após aceitação.\n",
        revision_id="synthetic-no-private-data",
    )[0]
    await provider.generate(
        window=w, tenant_id=uuid4(), request_id="a5-attempt-1", attempt=1,
    )
    await provider.generate(
        window=w, tenant_id=uuid4(), request_id="a5-attempt-2", attempt=2,
    )
    first, second = wrapper.calls
    assert provider.prompt_version == N4_WINDOW_PROMPT_VERSION
    assert first.max_tokens == 8192
    assert second.max_tokens == 16384
    assert first.tool_choice == {"type": "tool", "name": "record_window_findings"}
    assert first.tools[0]["name"] == "record_window_findings"
    required = first.tools[0]["input_schema"]["required"]
    assert "examined_clauses" in required
    assert "findings" in required
    assert first.metadata["prompt_version"] == N4_WINDOW_PROMPT_VERSION
    assert first.metadata["inventory_clause_count"] >= 3
    assert "SECCIÓN 2" in first.prompt
    assert "SEÇÃO 3" in first.prompt
    assert first.prompt.find("BEGIN UNTRUSTED SOURCE WINDOW") >= 0


@pytest.mark.asyncio
async def test_v2_provider_does_not_fabricate_missing_clause_examination():
    from src.analysis.domain.n4_compact_window_response import (
        N4WindowContractError,
        parse_n4_window_output,
    )
    wrapper = _FakeWrapper()  # its mock has no examined_clauses
    provider = AnthropicN4WindowProvider(wrapper=wrapper)
    w = plan_n4_source_windows(
        "9.6 The contractor shall provide insurance.",
        revision_id="synthetic-revision",
    )[0]
    response = await provider.generate(
        window=w, tenant_id=uuid4(), request_id="a5-missing-clauses",
    )
    with pytest.raises(N4WindowContractError, match="examined_clauses"):
        parse_n4_window_output(response.content, window=w)



@pytest.mark.asyncio
@pytest.mark.parametrize("bad_tool", [
    "unexpected_tool", "record_other_contract", "",
])
async def test_unexpected_tool_name_fails_closed_even_with_valid_json(bad_tool):
    """Forced tool_choice alone must NOT attest that the tool was respected."""
    from src.analysis.domain.n4_compact_window_response import (
        N4WindowContractError,
        parse_n4_window_output,
    )

    wrapper = _FakeWrapper(tool_name=bad_tool)
    provider = AnthropicN4WindowProvider(wrapper=wrapper)
    window = plan_n4_source_windows(
        "9.6 The supplier shall provide the project schedule.",
        revision_id="synthetic-tool-identity",
    )[0]
    receipt = await provider.generate(
        window=window, tenant_id=uuid4(), request_id="unexpected-tool",
    )
    assert json.loads(receipt.content)["error"] == "INVALID_N4_TOOL_ENVELOPE"
    assert receipt.reported_cost_usd == "0.012345"
    with pytest.raises(N4WindowContractError):
        parse_n4_window_output(receipt.content, window=window)


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_available, stop_reason", [
    (False, "tool_use"), (True, "end_turn"),
])
async def test_missing_raw_tool_attestation_fails_closed(raw_available, stop_reason):
    wrapper = _FakeWrapper(
        raw_available=raw_available, stop_reason=stop_reason,
    )
    provider = AnthropicN4WindowProvider(wrapper=wrapper)
    window = plan_n4_source_windows(
        "8.1 This synthetic clause remains unverified.",
        revision_id="synthetic-no-tool",
    )[0]
    receipt = await provider.generate(
        window=window, tenant_id=uuid4(), request_id="missing-tool",
    )
    assert json.loads(receipt.content)["error"] == "INVALID_N4_TOOL_ENVELOPE"



@pytest.mark.asyncio
async def test_prompt_version_drift_rejected_before_any_provider_call():
    wrapper = _FakeWrapper()
    provider = AnthropicN4WindowProvider(wrapper=wrapper)
    provider.prompt_version = "n4-compact-window-obsolete"
    window = plan_n4_source_windows(
        "9.6 Synthetic clause.", revision_id="synthetic-version-drift",
    )[0]
    with pytest.raises(ValueError, match="prompt version differs"):
        await provider.generate(
            window=window, tenant_id=uuid4(), request_id="version-drift",
        )
    assert wrapper.calls == []



@pytest.mark.parametrize("extra_type", ["text", "thinking", "server_tool_use"])
def test_tool_envelope_rejects_additional_blocks_even_when_empty(extra_type):
    """A valid forced tool is not enough when the envelope also has other blocks."""
    payload = {
        "window_examined": True, "findings": [], "outstanding_references": [],
        "examined_clauses": [],
    }
    raw = SimpleNamespace(
        stop_reason="tool_use",
        content=[
            SimpleNamespace(
                type="tool_use", name="record_window_findings", input=payload,
            ),
            SimpleNamespace(type=extra_type, text=""),
        ],
    )
    actual = _v2_provider_response(json.dumps(payload), raw)
    assert json.loads(actual) == {"error": "INVALID_N4_TOOL_ENVELOPE"}


def test_tool_envelope_rejects_duplicate_matching_tools():
    payload = {"window_examined": True, "findings": []}
    tool = SimpleNamespace(
        type="tool_use", name="record_window_findings", input=payload,
    )
    raw = SimpleNamespace(stop_reason="tool_use", content=[tool, tool])
    assert json.loads(_v2_provider_response(json.dumps(payload), raw)) == {
        "error": "INVALID_N4_TOOL_ENVELOPE",
    }


@pytest.mark.parametrize("untrusted_content", [
    "{",
    "[]",
    "null",
    '{"window_examined":false}',
    '{"window_examined":true,"findings":[],"unexpected":true}',
])
def test_tool_envelope_rejects_truncation_or_mismatched_json(untrusted_content):
    """Do not use a syntactically valid JSON body to impersonate tool output."""
    payload = {"window_examined": True, "findings": []}
    tool = SimpleNamespace(
        type="tool_use", name="record_window_findings", input=payload,
    )
    raw = SimpleNamespace(stop_reason="tool_use", content=[tool])
    assert json.loads(_v2_provider_response(untrusted_content, raw)) == {
        "error": "INVALID_N4_TOOL_ENVELOPE",
    }


def test_exact_tool_input_preserves_v2_identity_without_semantic_approval():
    payload = {
        "window_examined": True,
        "findings": [],
        "examined_clauses": [],
        "outstanding_references": [],
    }
    raw = SimpleNamespace(stop_reason="tool_use", content=[
        SimpleNamespace(type="tool_use", name="record_window_findings", input=payload),
    ])
    normalized = json.loads(_v2_provider_response(json.dumps(payload), raw))
    assert normalized["prompt_version"] == "n4-compact-window-v2"
    assert normalized["findings"] == []
    assert normalized["window_examined"] is True
