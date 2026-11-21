"""B3 · direct analysis arm (D4 reference): mock-only tests.

No network, no API keys, no real contracts: every source is synthetic text or
a PDF generated on the fly; providers are replaced by a recording transport.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import direct_arm as arm  # noqa: E402

from src.analysis.domain.n4_failure_kinds import N4SharedFinding  # noqa: E402

_GOVERNOR = REPO / "apps/api/scripts/real_ai_governor/real_ai_governor.py"

TAXONOMY_YAML = """
schema_version: 1
controles:
- {id: EPC-01, tipo: Precio y moneda, critico: true, dimension: BUDGET}
- {id: EPC-05, tipo: 'Penalizaciones por retraso: tasa y tope', critico: true, dimension: TIME}
- {id: EPC-18, tipo: Ley aplicable y disputas, critico: false, dimension: LEGAL}
"""
N2_TEXT = (
    "1. Contract Price. The Contract Price is EUR 1,000,000 (synthetic).\n"
    "2. Delay damages. Delay damages are 0.5% per week capped at 10%.\n"
)
PAGE_SPANS = [(1, 0, 67), (2, 67, len(N2_TEXT))]
PRICE = arm.ModelPrice(Decimal("3"), Decimal("15"))


def _finding(**overrides):
    item = {
        "title": "Delay damages capped",
        "category": "delay_damages",
        "dimension": "TIME",
        "severity_proposed": "HIGH",
        "risk_reason": "Interpretation: the cap limits recovery for long delays.",
        "source_quote": "Delay damages are 0.5% per week capped at 10%.",
        "page_start": 2,
        "page_end": 2,
        "epc_control_id": 5,
        "clause_ref": "2",
        "supporting_quotes": [],
        "quote_omits_figures": False,
    }
    item.update(overrides)
    return item


def _anthropic_reply(findings, *, not_found=(18,), stop="tool_use", tokens=(1000, 200)):
    return {
        "id": "msg_synthetic_001",
        "model": "claude-test-model",
        "stop_reason": stop,
        "usage": {"input_tokens": tokens[0], "output_tokens": tokens[1]},
        "content": [{
            "type": "tool_use", "id": "toolu_1", "name": arm.TOOL_NAME,
            "input": {"findings": findings, "controls_not_found": list(not_found)},
        }],
    }


def _openai_reply(findings, *, not_found=(18,), finish="tool_calls", tokens=(900, 150)):
    return {
        "id": "chatcmpl_synthetic_001",
        "model": "gpt-test-model",
        "usage": {"prompt_tokens": tokens[0], "completion_tokens": tokens[1]},
        "choices": [{
            "finish_reason": finish,
            "message": {"tool_calls": [{
                "type": "function",
                "function": {
                    "name": arm.TOOL_NAME,
                    "arguments": json.dumps(
                        {"findings": findings, "controls_not_found": list(not_found)}
                    ),
                },
            }]},
        }],
    }


class RecordingTransport:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    def __call__(self, provider, body):
        self.calls.append((provider, body))
        if self.error is not None:
            raise self.error
        return self.reply


@pytest.fixture
def taxonomy(tmp_path):
    path = tmp_path / "taxonomy.yaml"
    path.write_text(TAXONOMY_YAML, encoding="utf-8")
    return arm.load_taxonomy(path)


@pytest.fixture
def n2_source():
    return arm.DirectArmSource.from_n2_text(N2_TEXT, PAGE_SPANS)


@pytest.fixture
def pdf_source(tmp_path):
    import pymupdf

    doc = pymupdf.open()
    for line in N2_TEXT.splitlines():
        doc.new_page().insert_text((72, 72), line)
    path = tmp_path / "synthetic.pdf"
    doc.save(path)
    return arm.DirectArmSource.from_pdf(path)


@pytest.fixture
def register(tmp_path):
    return arm.JsonlSpendRegister(tmp_path / "spend.jsonl", max_usd=Decimal("5"))


def _config(provider="anthropic", **kw):
    model = "claude-test-model" if provider == "anthropic" else "gpt-test-model"
    return arm.ArmConfig(provider=provider, model=model, price=PRICE, **kw)


# --- taxonomy, source and schema ------------------------------------------


def test_taxonomy_maps_b1_ids_to_a1_integer_control_ids(taxonomy):
    assert [(c.number, c.label, c.dimension, c.critical) for c in taxonomy] == [
        (1, "EPC-01", "BUDGET", True),
        (5, "EPC-05", "TIME", True),
        (18, "EPC-18", "LEGAL", False),
    ]
    assert arm.epc_control_label(5) == "EPC-05"


def test_n2_source_is_rendered_with_page_markers_and_hashed(n2_source):
    rendered = n2_source.text
    assert rendered.index("<<<PAGE 1>>>") < rendered.index("Contract Price")
    assert rendered.index("<<<PAGE 2>>>") < rendered.index("Delay damages")
    assert n2_source.kind == "n2_text" and n2_source.page_count == 2
    assert len(n2_source.sha256) == 64


def test_page_spans_must_cover_the_projection_in_order():
    with pytest.raises(ValueError, match="page spans"):
        arm.DirectArmSource.from_n2_text(N2_TEXT, [(1, 0, 10), (2, 20, len(N2_TEXT))])


def test_tool_schema_matches_a1_shared_finding_keys():
    item = arm.tool_input_schema()["properties"]["findings"]["items"]
    assert set(item["properties"]) == (
        N4SharedFinding.__required_keys__ | N4SharedFinding.__optional_keys__
    ) - {"window_ordinal"}
    assert set(item["required"]) == set(N4SharedFinding.__required_keys__)
    assert item["additionalProperties"] is False


# --- provider requests (no network) ----------------------------------------


def test_anthropic_request_sends_pdf_document_and_forces_tool(pdf_source, taxonomy):
    body = arm.build_request(_config("anthropic", max_output_tokens=4000), pdf_source, taxonomy)
    assert body["model"] == "claude-test-model"
    assert body["max_tokens"] == 4000 and body["temperature"] == 0
    assert body["tool_choice"] == {"type": "tool", "name": arm.TOOL_NAME}
    blocks = body["messages"][0]["content"]
    document = next(b for b in blocks if b["type"] == "document")
    assert document["source"]["media_type"] == "application/pdf"
    assert base64.b64decode(document["source"]["data"]).startswith(b"%PDF")
    assert "EPC-05" in body["system"] and "untrusted" in body["system"].lower()


def test_openai_request_sends_text_and_forces_function(n2_source, taxonomy):
    body = arm.build_request(_config("openai"), n2_source, taxonomy)
    assert body["model"] == "gpt-test-model"
    assert body["tool_choice"] == {"type": "function", "function": {"name": arm.TOOL_NAME}}
    assert body["tools"][0]["function"]["parameters"] == arm.tool_input_schema()
    user = body["messages"][-1]["content"]
    assert any("<<<PAGE 2>>>" in part.get("text", "") for part in user)


def test_openai_request_sends_pdf_as_file_part(pdf_source, taxonomy):
    body = arm.build_request(_config("openai"), pdf_source, taxonomy)
    part = next(p for p in body["messages"][-1]["content"] if p["type"] == "file")
    assert part["file"]["file_data"].startswith("data:application/pdf;base64,")


# --- validation into the A1 schema -----------------------------------------


def test_valid_findings_are_kept_in_a1_schema_and_invalid_ones_reported(taxonomy):
    good = _finding()
    bad = [
        _finding(dimension="FINANCE"),
        _finding(severity_proposed="SEVERE"),
        _finding(source_quote="x" * 1201),
        _finding(source_quote=" "),
        _finding(supporting_quotes=["a", "b", "c"]),
        _finding(page_start=None),
        _finding(page_start=3, page_end=2),
        _finding(epc_control_id=7),
        _finding(unexpected="field"),
    ]
    valid, rejected = arm.validate_findings([good, *bad], taxonomy)
    assert valid == [good]
    assert [r["index"] for r in rejected] == list(range(1, 10))
    assert all(r["reason"] for r in rejected)


# --- full run: spend register, caps, failures -------------------------------


def test_anthropic_run_records_spend_and_returns_result_document(
    n2_source, taxonomy, register,
):
    transport = RecordingTransport(_anthropic_reply([_finding(), _finding(dimension="X")]))
    result = arm.run_direct_arm(
        config=_config("anthropic"), source=n2_source, taxonomy=taxonomy,
        contract_alias="C1", register=register, transport=transport,
    )
    assert len(transport.calls) == 1
    assert result["schema"] == arm.RESULT_SCHEMA
    assert result["prompt_version"] == arm.PROMPT_VERSION
    assert result["contract_alias"] == "C1"
    assert (result["provider"], result["model"]) == ("anthropic", "claude-test-model")
    assert result["source"] == {"kind": "n2_text", "sha256": n2_source.sha256, "pages": 2}
    assert result["findings"] == [_finding()]
    assert len(result["rejected"]) == 1
    assert result["controls_not_found"] == [18]
    # 1000 in * 3 USD/M + 200 out * 15 USD/M
    assert Decimal(result["cost_usd"]) == Decimal("0.006")
    assert result["usage"] == {"input_tokens": 1000, "output_tokens": 200}


def test_spend_register_is_readable_by_the_governor_summary(n2_source, taxonomy, register):
    arm.run_direct_arm(
        config=_config("openai"), source=n2_source, taxonomy=taxonomy,
        contract_alias="C2", register=register,
        transport=RecordingTransport(_openai_reply([_finding()])),
    )
    spec = importlib.util.spec_from_file_location("real_ai_governor", _GOVERNOR)
    governor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(governor)
    summary = governor.summarize(governor.read_events(register.path))
    assert (summary["calls"], summary["completed"], summary["in_flight"]) == (1, 1, 0)
    assert summary["spent_usd"] == pytest.approx(900 * 3e-6 + 150 * 15e-6)
    events = governor.read_events(register.path)
    assert {e["provider"] for e in events} == {"openai"}
    assert all(e["arm"] == "B3" for e in events)
    assert not any("Delay damages" in json.dumps(e) for e in events)


def test_global_budget_cap_refuses_before_any_provider_call(tmp_path, n2_source, taxonomy):
    register = arm.JsonlSpendRegister(tmp_path / "spend.jsonl", max_usd=Decimal("0.01"))
    transport = RecordingTransport(_anthropic_reply([_finding()]))
    with pytest.raises(arm.SpendRefused, match="budget"):
        arm.run_direct_arm(
            config=_config("anthropic", max_output_tokens=16000), source=n2_source,
            taxonomy=taxonomy, contract_alias="C1", register=register,
            transport=transport,
        )
    assert transport.calls == []
    assert [e["ev"] for e in register.events()] == ["refused"]


def test_per_call_cap_refuses_before_any_provider_call(pdf_source, taxonomy, register):
    transport = RecordingTransport(_anthropic_reply([_finding()]))
    with pytest.raises(arm.SpendRefused, match="per-call"):
        arm.run_direct_arm(
            config=_config("anthropic", max_usd_per_call=Decimal("0.001")),
            source=pdf_source, taxonomy=taxonomy, contract_alias="C1",
            register=register, transport=transport,
        )
    assert transport.calls == []


def test_provider_error_is_recorded_as_failed_call(n2_source, taxonomy, register):
    transport = RecordingTransport(error=TimeoutError("synthetic timeout"))
    with pytest.raises(TimeoutError):
        arm.run_direct_arm(
            config=_config("anthropic"), source=n2_source, taxonomy=taxonomy,
            contract_alias="C1", register=register, transport=transport,
        )
    assert [e["ev"] for e in register.events()] == ["reserve", "fail"]


@pytest.mark.parametrize("provider,reply", [
    ("anthropic", _anthropic_reply([], stop="max_tokens")),
    ("openai", _openai_reply([], finish="length")),
])
def test_truncated_output_is_billed_but_never_returned_as_a_result(
    provider, reply, n2_source, taxonomy, register,
):
    with pytest.raises(arm.DirectArmOutputError, match="truncated"):
        arm.run_direct_arm(
            config=_config(provider), source=n2_source, taxonomy=taxonomy,
            contract_alias="C1", register=register, transport=RecordingTransport(reply),
        )
    assert [e["ev"] for e in register.events()] == ["reserve", "done"]


def test_unknown_price_or_real_name_alias_is_refused(n2_source, taxonomy, register):
    with pytest.raises(ValueError, match="price"):
        arm.ArmConfig(provider="anthropic", model="m", price=arm.ModelPrice(Decimal("0"), Decimal("1")))
    with pytest.raises(ValueError, match="alias"):
        arm.run_direct_arm(
            config=_config("anthropic"), source=n2_source, taxonomy=taxonomy,
            contract_alias="SolarMax", register=register,
            transport=RecordingTransport(_anthropic_reply([])),
        )


def test_result_cannot_be_written_inside_the_repository(tmp_path):
    result = {"schema": arm.RESULT_SCHEMA}
    with pytest.raises(ValueError, match="outside the repository"):
        arm.write_result(result, REPO / "evals/journey_v1/out.json")
    out = tmp_path / "c1-anthropic.json"
    arm.write_result(result, out)
    assert json.loads(out.read_text(encoding="utf-8")) == result
