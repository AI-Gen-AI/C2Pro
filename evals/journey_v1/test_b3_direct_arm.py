"""B3 · direct analysis arm (D4 reference): mock-only tests.

No network, no API keys, no real contracts: every source is synthetic text or
a PDF generated on the fly; providers are replaced by a recording transport.
These tests prove the CODE CONTRACT of the arm; they are not contract analysis.
"""
from __future__ import annotations

import base64
import contextlib
import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import direct_arm as arm  # noqa: E402

from src.analysis.domain.n4_failure_kinds import (  # noqa: E402
    N4_DIMENSIONS,
    N4_SEVERITIES,
    N4_SOURCE_QUOTE_MAX_CHARS,
    N4_SUPPORTING_QUOTES_MAX,
    N4SharedFinding,
)

_GOVERNOR = REPO / "apps/api/scripts/real_ai_governor/real_ai_governor.py"

TAXONOMY_YAML = """
schema_version: 1
controles:
- {id: EPC-01, tipo: Precio y moneda, critico: true, dimension: BUDGET}
- {id: EPC-05, tipo: 'Penalizaciones por retraso: tasa y tope', critico: true, dimension: TIME}
- {id: EPC-18, tipo: Ley aplicable y disputas, critico: false, dimension: LEGAL}
"""
# Independent transcription of plan §6.2 in B1's YAML shape (B1 PR #1287):
# (id, tipo, critico, dimension).
B1_CONTROLS = [
    ("EPC-01", "Precio y moneda", True, "BUDGET"),
    ("EPC-02", "Hitos/calendario de pagos y condiciones", True, "BUDGET"),
    ("EPC-03", "Retenciones, avales y garantías financieras", True, "BUDGET"),
    ("EPC-04", "Plazo / fechas de terminación garantizadas", True, "TIME"),
    ("EPC-05", "Penalizaciones por retraso: tasa y tope", True, "TIME"),
    ("EPC-06", "Garantías y penalizaciones de rendimiento", True, "TECHNICAL"),
    ("EPC-07", "Limitación de responsabilidad, daño consecuencial y excepciones", True, "LEGAL"),
    ("EPC-08", "Indemnidades", True, "LEGAL"),
    ("EPC-09", "Resolución (causas, consecuencias, plazos)", True, "LEGAL"),
    ("EPC-10", "Suspensión", False, "LEGAL"),
    ("EPC-11", "Fuerza mayor", True, "LEGAL"),
    ("EPC-12", "Variaciones / órdenes de cambio y su valoración", True, "SCOPE"),
    ("EPC-13", "Alcance, exclusiones e interfaces", True, "SCOPE"),
    ("EPC-14", "Pruebas y recepción (provisional/definitiva)", True, "QUALITY"),
    ("EPC-15", "Garantía y periodo de defectos", True, "QUALITY"),
    ("EPC-16", "Seguros y límites", False, "LEGAL"),
    ("EPC-17", "Confidencialidad y propiedad intelectual", False, "LEGAL"),
    ("EPC-18", "Ley aplicable y disputas", False, "LEGAL"),
    ("EPC-19", "Impuestos, aranceles, permisos y cambio de ley", False, "BUDGET"),
    ("EPC-20", "Remisiones a anexos y orden de prelación", True, "SCOPE"),
]
B1_FIELDS = [
    "id", "tipo", "critico", "presente", "clausula",
    "pagina", "cita_ancla", "cifras_esperadas", "dimension",
]
N2_TEXT = (
    "1. Contract Price. The Contract Price is EUR 1,000,000 (synthetic).\n"
    "2. Delay damages. Delay damages are 0.5% per week capped at 10%.\n"
)
PAGE_SPANS = [(1, 0, 67), (2, 67, len(N2_TEXT))]
PRICE = arm.ModelPrice(Decimal("3"), Decimal("15"))
RESULT_KEYS = {
    "schema", "prompt_version", "prompt_sha256", "contract_alias", "provider",
    "model", "model_reported", "request_id", "source", "findings", "rejected",
    "controls_not_found", "usage", "usage_known", "cost_usd", "started_at",
    "finished_at",
}


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


def _anthropic_reply(findings, *, not_found=(18,), stop="tool_use", usage=None):
    return {
        "id": "msg_synthetic_001",
        "model": "claude-test-model",
        "stop_reason": stop,
        "usage": usage or {"input_tokens": 1000, "output_tokens": 200},
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


def _write_pdf(path: Path, pages: list[str]) -> Path:
    import pymupdf

    doc = pymupdf.open()
    for line in pages:
        doc.new_page().insert_text((72, 72), line)
    doc.save(path)
    return path


@pytest.fixture
def taxonomy(tmp_path):
    (tmp_path / "taxonomy.yaml").write_text(TAXONOMY_YAML, encoding="utf-8")
    return arm.load_taxonomy("taxonomy.yaml", root=tmp_path)


@pytest.fixture
def n2_source():
    return arm.DirectArmSource.from_n2_text(N2_TEXT, PAGE_SPANS)


@pytest.fixture
def pdf_source(tmp_path):
    _write_pdf(tmp_path / "synthetic.pdf", N2_TEXT.splitlines())
    return arm.DirectArmSource.from_pdf("synthetic.pdf", root=tmp_path)


@pytest.fixture
def register(tmp_path):
    return arm.JsonlSpendRegister(max_usd=Decimal("5"), root=tmp_path)


def _config(provider="anthropic", **kw):
    model = "claude-test-model" if provider == "anthropic" else "gpt-test-model"
    return arm.ArmConfig(provider=provider, model=model, price=PRICE, **kw)


def _run(config, source, taxonomy, register, transport, alias="C1"):
    return arm.run_direct_arm(
        config=config, source=source, taxonomy=taxonomy, contract_alias=alias,
        register=register, transport=transport,
    )


# --- B1 contract: taxonomy ---------------------------------------------------


def test_taxonomy_maps_b1_ids_to_a1_integer_control_ids(taxonomy):
    assert [(c.number, c.label, c.dimension, c.critical) for c in taxonomy] == [
        (1, "EPC-01", "BUDGET", True),
        (5, "EPC-05", "TIME", True),
        (18, "EPC-18", "LEGAL", False),
    ]
    assert arm.epc_control_label(5) == "EPC-05"


def test_full_b1_shaped_taxonomy_loads_all_twenty_controls(tmp_path):
    document = {
        "schema_version": 1,
        "campos_oraculo": B1_FIELDS,
        "controles": [
            {"id": i, "tipo": t, "critico": c, "presente": None, "clausula": None,
             "pagina": None, "cita_ancla": None, "cifras_esperadas": None, "dimension": d}
            for i, t, c, d in B1_CONTROLS
        ],
    }
    (tmp_path / "epc.yaml").write_text(
        yaml.safe_dump(document, allow_unicode=True), encoding="utf-8",
    )
    controls = arm.load_taxonomy("epc.yaml", root=tmp_path)
    assert [c.number for c in controls] == list(range(1, 21))
    assert [(c.label, c.tipo, c.critical, c.dimension) for c in controls] == B1_CONTROLS
    assert sum(c.critical for c in controls) == 15
    assert {arm.epc_control_label(c.number) for c in controls} == {i for i, *_ in B1_CONTROLS}


@pytest.mark.parametrize("bad", [
    "{id: EPC-1, tipo: x, critico: true, dimension: TIME}",
    "{id: EPC-01, tipo: x, critico: si, dimension: TIME}",
    "{id: EPC-01, tipo: x, critico: true, dimension: FINANCE}",
    "{id: EPC-21, tipo: x, critico: true, dimension: TIME}",
])
def test_taxonomy_rejects_controls_outside_the_b1_contract(tmp_path, bad):
    (tmp_path / "bad.yaml").write_text(f"controles:\n- {bad}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="EPC control"):
        arm.load_taxonomy("bad.yaml", root=tmp_path)


# --- A1 contract: finding schema --------------------------------------------


def test_tool_schema_keys_match_a1_shared_finding():
    item = arm.tool_input_schema()["properties"]["findings"]["items"]
    assert set(item["properties"]) == (
        N4SharedFinding.__required_keys__ | N4SharedFinding.__optional_keys__
    ) - {"window_ordinal"}
    assert set(item["required"]) == set(N4SharedFinding.__required_keys__)
    assert item["additionalProperties"] is False


def test_tool_schema_limits_match_a1_constants():
    props = arm.tool_input_schema()["properties"]["findings"]["items"]["properties"]
    assert props["dimension"]["enum"] == list(N4_DIMENSIONS)
    assert props["severity_proposed"]["enum"] == list(N4_SEVERITIES)
    assert props["source_quote"]["maxLength"] == N4_SOURCE_QUOTE_MAX_CHARS
    assert props["supporting_quotes"]["maxItems"] == N4_SUPPORTING_QUOTES_MAX
    assert props["supporting_quotes"]["items"]["maxLength"] == N4_SOURCE_QUOTE_MAX_CHARS
    assert props["epc_control_id"]["minimum"] == 1
    assert props["epc_control_id"]["maximum"] == 20


# --- source -----------------------------------------------------------------


def test_n2_source_is_rendered_with_page_markers_and_hashed(n2_source):
    rendered = n2_source.text
    assert rendered.index("<<<PAGE 1>>>") < rendered.index("Contract Price")
    assert rendered.index("<<<PAGE 2>>>") < rendered.index("Delay damages")
    assert n2_source.kind == "n2_text"
    assert n2_source.page_count == 2
    assert len(n2_source.sha256) == 64


def test_page_spans_must_cover_the_projection_in_order():
    with pytest.raises(ValueError, match="page spans"):
        arm.DirectArmSource.from_n2_text(N2_TEXT, [(1, 0, 10), (2, 20, len(N2_TEXT))])


def test_n2_files_are_loaded_from_the_corpus_root(tmp_path):
    (tmp_path / "c2.txt").write_text(N2_TEXT, encoding="utf-8")
    (tmp_path / "c2.spans.json").write_text(json.dumps([
        {"page": p, "start_offset": s, "end_offset": e} for p, s, e in PAGE_SPANS
    ]), encoding="utf-8")
    source = arm.DirectArmSource.from_n2_files("c2.txt", "c2.spans.json", root=tmp_path)
    assert source == arm.DirectArmSource.from_n2_text(N2_TEXT, PAGE_SPANS)


# --- path selection (SonarCloud S8707): CLI values never build a path -------


@pytest.mark.parametrize("raw", [
    "../escape.yaml", "/etc/passwd", "sub/../../escape.yaml", "missing.yaml",
])
def test_names_not_listed_under_the_root_are_refused(tmp_path, raw):
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "escape.yaml").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="outside the allowed root"):
        arm.select_file(raw, root)


def test_listed_files_are_selected_by_relative_or_absolute_name(tmp_path):
    (tmp_path / "sub").mkdir()
    target = tmp_path / "sub" / "c2.txt"
    target.write_text("x", encoding="utf-8")
    assert arm.select_file("sub/c2.txt", tmp_path) == target
    assert arm.select_file(str(target), tmp_path) == target


def test_symlink_escaping_the_root_is_refused(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("x", encoding="utf-8")
    (root / "link.txt").symlink_to(tmp_path / "secret.txt")
    with pytest.raises(ValueError, match="outside the allowed root"):
        arm.select_file("link.txt", root)


def test_private_roots_cannot_live_inside_the_repository():
    inside = REPO / "evals" / "journey_v1"
    with pytest.raises(ValueError, match="outside the repository"):
        arm.DirectArmSource.from_pdf("x.pdf", root=inside)


def test_default_private_root_is_fixed_and_outside_the_repository():
    for root in (arm.CORPUS_ROOT, arm.RESULTS_ROOT, arm.SPEND_ROOT):
        assert root.is_relative_to(arm.PRIVATE_ROOT)
        assert not root.resolve().is_relative_to(REPO)
    assert arm.TAXONOMY_ROOT == HERE


# --- provider requests (no network) ----------------------------------------


def test_anthropic_request_sends_pdf_document_and_forces_tool(pdf_source, taxonomy):
    body = arm.build_request(_config("anthropic", max_output_tokens=4000), pdf_source, taxonomy)
    assert body["model"] == "claude-test-model"
    assert body["max_tokens"] == 4000
    assert body["temperature"] == 0
    assert body["tool_choice"] == {"type": "tool", "name": arm.TOOL_NAME}
    blocks = body["messages"][0]["content"]
    document = next(b for b in blocks if b["type"] == "document")
    assert document["source"]["media_type"] == "application/pdf"
    assert base64.b64decode(document["source"]["data"]).startswith(b"%PDF")
    assert "EPC-05" in body["system"]
    assert "untrusted" in body["system"].lower()


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


def test_temperature_can_be_omitted_for_reasoning_models(n2_source, taxonomy):
    body = arm.build_request(_config("openai", temperature=None), n2_source, taxonomy)
    assert "temperature" not in body


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
        _finding(quote_omits_figures="no"),
        _finding(page_start=True, page_end=True),
        "not an object",
    ]
    valid, rejected = arm.validate_findings([good, *bad], taxonomy)
    assert valid == [good]
    assert [r["index"] for r in rejected] == list(range(1, len(bad) + 1))
    assert all(r["reason"] for r in rejected)


# --- full run: result contract, spend register, caps, failures ---------------


def test_result_document_contract(n2_source, taxonomy, register):
    transport = RecordingTransport(_anthropic_reply([_finding(), _finding(dimension="X")]))
    result = _run(_config("anthropic"), n2_source, taxonomy, register, transport)
    assert set(result) == RESULT_KEYS
    assert len(transport.calls) == 1
    assert result["schema"] == arm.RESULT_SCHEMA
    assert result["prompt_version"] == arm.PROMPT_VERSION
    assert len(result["prompt_sha256"]) == 64
    assert result["contract_alias"] == "C1"
    assert result["provider"] == "anthropic"
    assert result["model"] == "claude-test-model"
    assert result["source"] == {"kind": "n2_text", "sha256": n2_source.sha256, "pages": 2}
    assert result["findings"] == [_finding()]
    assert len(result["rejected"]) == 1
    assert result["controls_not_found"] == [18]
    assert result["usage"] == {"input_tokens": 1000, "output_tokens": 200}
    assert result["usage_known"] is True
    json.dumps(result)  # serialisable as written to disk


def test_cost_is_tokens_times_explicit_price(n2_source, taxonomy, register):
    result = _run(_config("anthropic"), n2_source, taxonomy, register,
                  RecordingTransport(_anthropic_reply([_finding()])))
    # 1000 in * 3 USD/M + 200 out * 15 USD/M
    assert Decimal(result["cost_usd"]) == Decimal("0.006")


def test_anthropic_cache_tokens_are_billed_pessimistically(n2_source, taxonomy, register):
    usage = {"input_tokens": 1000, "output_tokens": 0,
             "cache_creation_input_tokens": 100, "cache_read_input_tokens": 200}
    result = _run(_config("anthropic"), n2_source, taxonomy, register,
                  RecordingTransport(_anthropic_reply([], usage=usage)))
    # cache writes at 1.25x, cache reads at full input price (never discounted)
    assert Decimal(result["cost_usd"]) == Decimal("0.003975")
    assert result["usage"]["input_tokens"] == 1300


def test_unknown_usage_is_charged_at_the_worst_case(n2_source, taxonomy, register):
    reply = _anthropic_reply([_finding()])
    reply["usage"] = {}
    result = _run(_config("anthropic"), n2_source, taxonomy, register, RecordingTransport(reply))
    reserve = next(e for e in register.events() if e["ev"] == "reserve")
    assert result["usage_known"] is False
    assert Decimal(result["cost_usd"]) == Decimal(str(reserve["est_usd"]))


def test_94_page_pdf_fits_the_default_per_call_cap(tmp_path, taxonomy):
    _write_pdf(tmp_path / "long.pdf", [f"synthetic page {n}" for n in range(94)])
    source = arm.DirectArmSource.from_pdf("long.pdf", root=tmp_path)
    config = _config("anthropic")
    estimate = arm.estimate_usd(config, source, arm.build_request(config, source, taxonomy))
    # 94 pages x 3000 tokens x 3 USD/M + 16000 out x 15 USD/M = 1.086 USD
    assert Decimal("1.086") <= estimate < Decimal("1.10")
    assert estimate <= config.max_usd_per_call


def test_spend_register_is_readable_by_the_governor_summary(n2_source, taxonomy, register):
    _run(_config("openai"), n2_source, taxonomy, register,
         RecordingTransport(_openai_reply([_finding()])), alias="C2")
    spec = importlib.util.spec_from_file_location("real_ai_governor", _GOVERNOR)
    governor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(governor)
    events = governor.read_events(register.path)
    summary = governor.summarize(events)
    assert summary["calls"] == 1
    assert summary["completed"] == 1
    assert summary["in_flight"] == 0
    assert summary["spent_usd"] == pytest.approx(900 * 3e-6 + 150 * 15e-6)
    assert {e["provider"] for e in events} == {"openai"}
    assert all(e["arm"] == "B3" for e in events)
    assert not any("Delay damages" in json.dumps(e) for e in events)


def test_global_budget_cap_refuses_before_any_provider_call(tmp_path, n2_source, taxonomy):
    register = arm.JsonlSpendRegister(max_usd=Decimal("0.01"), root=tmp_path)
    transport = RecordingTransport(_anthropic_reply([_finding()]))
    config = _config("anthropic", max_output_tokens=16000)
    with pytest.raises(arm.SpendRefused, match="budget"):
        _run(config, n2_source, taxonomy, register, transport)
    assert transport.calls == []
    assert [e["ev"] for e in register.events()] == ["refused"]


def test_budget_counts_spend_already_in_the_register(tmp_path, n2_source, taxonomy):
    register = arm.JsonlSpendRegister(max_usd=Decimal("0.5"), root=tmp_path)
    config = _config("anthropic", max_output_tokens=16000)  # worst case ~0.25 USD
    _run(config, n2_source, taxonomy, register,
         RecordingTransport(_anthropic_reply([], usage={"input_tokens": 1, "output_tokens": 20000})))
    transport = RecordingTransport(_anthropic_reply([]))
    with pytest.raises(arm.SpendRefused, match="budget"):
        _run(config, n2_source, taxonomy, register, transport)
    assert transport.calls == []


def test_per_call_cap_refuses_before_any_provider_call(pdf_source, taxonomy, register):
    transport = RecordingTransport(_anthropic_reply([_finding()]))
    config = _config("anthropic", max_usd_per_call=Decimal("0.001"))
    with pytest.raises(arm.SpendRefused, match="per-call"):
        _run(config, pdf_source, taxonomy, register, transport)
    assert transport.calls == []


def test_request_proven_not_sent_releases_the_reservation(n2_source, taxonomy, register):
    transport = RecordingTransport(error=arm.RequestNotSent("synthetic: never sent"))
    config = _config("anthropic")
    with pytest.raises(arm.RequestNotSent):
        _run(config, n2_source, taxonomy, register, transport)
    assert [e["ev"] for e in register.events()] == ["reserve", "fail"]


@pytest.mark.parametrize("provider,reply", [
    ("anthropic", _anthropic_reply([], stop="max_tokens")),
    ("openai", _openai_reply([], finish="length")),
])
def test_truncated_output_is_billed_but_never_returned_as_a_result(
    provider, reply, n2_source, taxonomy, register,
):
    config, transport = _config(provider), RecordingTransport(reply)
    with pytest.raises(arm.DirectArmOutputError, match="truncated"):
        _run(config, n2_source, taxonomy, register, transport)
    assert [e["ev"] for e in register.events()] == ["reserve", "done"]


def test_reply_without_tool_output_is_billed_but_not_a_result(n2_source, taxonomy, register):
    reply = _openai_reply([])
    reply["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = "{not json"
    config, transport = _config("openai"), RecordingTransport(reply)
    with pytest.raises(arm.DirectArmOutputError, match="tool output"):
        _run(config, n2_source, taxonomy, register, transport)
    assert [e["ev"] for e in register.events()] == ["reserve", "done"]


def test_non_positive_price_is_refused():
    with pytest.raises(ValueError, match="price"):
        arm.ModelPrice(Decimal("0"), Decimal("1"))


def test_contract_names_are_refused_as_aliases(n2_source, taxonomy, register):
    config, transport = _config("anthropic"), RecordingTransport(_anthropic_reply([]))
    with pytest.raises(ValueError, match="alias"):
        _run(config, n2_source, taxonomy, register, transport, alias="SolarMax")
    assert transport.calls == []


def test_result_file_name_is_built_from_constants_only(tmp_path):
    result = {"schema": arm.RESULT_SCHEMA, "contract_alias": "C3", "provider": "openai"}
    target = arm.write_result(result, root=tmp_path / "results")
    assert target.parent == tmp_path / "results"
    assert target.name.startswith("C3-openai-")
    assert target.suffix == ".json"
    assert json.loads(target.read_text(encoding="utf-8")) == result


@pytest.mark.parametrize("alias,provider", [("../C1", "openai"), ("C1", "../x")])
def test_result_with_unknown_alias_or_provider_is_not_written(tmp_path, alias, provider):
    result = {"contract_alias": alias, "provider": provider}
    with pytest.raises(ValueError, match="alias|provider"):
        arm.write_result(result, root=tmp_path)
    assert not any(tmp_path.iterdir())


# --- CLI (mock transport, confined roots) -------------------------------------


@pytest.fixture
def private_root(tmp_path, monkeypatch):
    root = tmp_path / "private"
    monkeypatch.setattr(arm, "CORPUS_ROOT", root / "corpus")
    monkeypatch.setattr(arm, "RESULTS_ROOT", root / "results")
    monkeypatch.setattr(arm, "SPEND_ROOT", root / "spend")
    monkeypatch.setattr(arm, "TAXONOMY_ROOT", root)
    (root / "corpus").mkdir(parents=True)
    (root / "taxonomy.yaml").write_text(TAXONOMY_YAML, encoding="utf-8")
    _write_pdf(root / "corpus" / "c1.pdf", N2_TEXT.splitlines())
    return root


def _cli_args(*extra):
    return [
        "--provider", "anthropic", "--model", "claude-test-model",
        "--price-in", "3", "--price-out", "15", "--contract-alias", "C1",
        "--taxonomy", "taxonomy.yaml", "--max-usd", "5", *extra,
    ]


def test_cli_runs_with_mock_transport_and_writes_only_private_files(private_root):
    transport = RecordingTransport(_anthropic_reply([_finding()]))
    argv = _cli_args("--source-pdf", "c1.pdf")
    assert arm.main(argv, transport=transport) == 0
    assert len(transport.calls) == 1
    (written,) = (private_root / "results").glob("C1-anthropic-*.json")
    assert json.loads(written.read_text(encoding="utf-8"))["findings"] == [_finding()]
    assert (private_root / "spend" / arm.DEFAULT_LEDGER).exists()


@pytest.mark.parametrize("extra", [
    ("--source-pdf", "../../etc/passwd"),
    ("--source-pdf", "c1.pdf", "--taxonomy", "../../escape.yaml"),
    ("--source-n2", "../c2.txt", "--page-spans", "c2.json"),
])
@pytest.mark.usefixtures("private_root")
def test_cli_refuses_names_outside_private_roots(extra):
    transport = RecordingTransport(_anthropic_reply([]))
    argv = _cli_args(*extra)
    with pytest.raises(ValueError, match="outside the allowed root"):
        arm.main(argv, transport=transport)
    assert transport.calls == []


# --- remaining guards and the real transport (httpx mocked, no network) -------


@pytest.mark.parametrize("kwargs", [
    {"provider": "gemini"},
    {"model": " "},
    {"max_output_tokens": 0},
    {"max_usd_per_call": Decimal("0")},
])
def test_invalid_arm_config_is_refused(kwargs):
    params = {"provider": "anthropic", "model": "m", "price": PRICE, **kwargs}
    with pytest.raises(ValueError):
        arm.ArmConfig(**params)


def test_non_pdf_bytes_are_refused(tmp_path):
    (tmp_path / "fake.pdf").write_text("not a pdf", encoding="utf-8")
    with pytest.raises(ValueError, match="not a PDF"):
        arm.DirectArmSource.from_pdf("fake.pdf", root=tmp_path)


def test_duplicate_controls_are_refused(tmp_path):
    line = "- {id: EPC-01, tipo: x, critico: true, dimension: BUDGET}\n"
    (tmp_path / "dup.yaml").write_text("controles:\n" + line + line, encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        arm.load_taxonomy("dup.yaml", root=tmp_path)


def test_spend_register_requires_a_positive_cap(tmp_path):
    with pytest.raises(ValueError, match="cap"):
        arm.JsonlSpendRegister(max_usd=Decimal("0"), root=tmp_path)


def test_openai_other_tools_and_non_object_arguments_are_not_results():
    other = _openai_reply([])
    other["choices"][0]["message"]["tool_calls"][0]["function"]["name"] = "other_tool"
    listed = _openai_reply([])
    listed["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = "[1, 2]"
    assert arm._parse_reply("openai", other).tool_input is None
    assert arm._parse_reply("openai", listed).tool_input is None


def test_non_text_optional_fields_are_rejected(taxonomy):
    _, rejected = arm.validate_findings([_finding(clause_ref=7)], taxonomy)
    assert rejected == [{"index": 0, "reason": "clause_ref must be text"}]


class _FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


@pytest.mark.parametrize("provider,env,url,header,value", [
    ("anthropic", "ANTHROPIC_API_KEY", "https://api.anthropic.com/v1/messages",
     "x-api-key", "sk-ant-synthetic-key-for-tests-only"),
    ("openai", "OPENAI_API_KEY", "https://api.openai.com/v1/chat/completions",
     "authorization", "Bearer sk-synthetic-openai-key-for-tests"),
])
def test_httpx_transport_builds_provider_request_without_network(
    monkeypatch, provider, env, url, header, value,
):
    import httpx

    monkeypatch.setenv(env, value.removeprefix("Bearer "))
    calls = []

    def fake_post(target, *, json, headers, timeout):
        calls.append((target, json, headers, timeout))
        return _FakeResponse({"ok": True})

    monkeypatch.setattr(httpx, "post", fake_post)
    assert arm.HttpxTransport(timeout_s=12.0)(provider, {"model": "m"}) == {"ok": True}
    ((target, body, headers, timeout),) = calls
    assert target == url
    assert body == {"model": "m"}
    assert headers[header] == value
    assert timeout == pytest.approx(12.0)
    if provider == "anthropic":
        assert headers["anthropic-version"] == "2023-06-01"


@pytest.mark.parametrize("provider,env", [
    ("anthropic", "ANTHROPIC_API_KEY"), ("openai", "OPENAI_API_KEY"),
])
def test_httpx_transport_refuses_to_send_without_a_key(monkeypatch, provider, env):
    import httpx

    monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(httpx, "post", pytest.fail)
    transport = arm.HttpxTransport()
    with pytest.raises(RuntimeError, match="API key missing"):
        transport(provider, {"model": "m"})


def test_cli_n2_source_requires_page_spans(private_root):
    argv = _cli_args("--source-n2", "c2.txt")
    transport = RecordingTransport(_anthropic_reply([]))
    with pytest.raises(SystemExit):
        arm.main(argv, transport=transport)
    assert not (private_root / "results").exists()


def test_cli_runs_an_n2_projection_with_mock_transport(private_root):
    (private_root / "corpus/c2.txt").write_text(N2_TEXT, encoding="utf-8")
    (private_root / "corpus/c2.json").write_text(json.dumps([
        {"page": p, "start_offset": s, "end_offset": e} for p, s, e in PAGE_SPANS
    ]), encoding="utf-8")
    transport = RecordingTransport(_openai_reply([_finding()]))
    argv = _cli_args("--source-n2", "c2.txt", "--page-spans", "c2.json", "--no-temperature")
    argv[argv.index("anthropic")] = "openai"
    argv[argv.index("C1")] = "C2"
    assert arm.main(argv, transport=transport) == 0
    ((provider, body),) = transport.calls
    assert provider == "openai"
    assert "temperature" not in body
    (written,) = (private_root / "results").glob("C2-openai-*.json")
    assert json.loads(written.read_text(encoding="utf-8"))["source"]["kind"] == "n2_text"


# --- P0 (L0 GO 22/11): uncertain provider outcomes never release spend --------


def _load_governor():
    spec = importlib.util.spec_from_file_location("real_ai_governor", _GOVERNOR)
    governor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(governor)
    return governor


@pytest.mark.parametrize("error", [
    TimeoutError("synthetic read timeout"),
    ConnectionResetError("synthetic reset after send"),
    RuntimeError("synthetic 504 gateway timeout"),
    KeyboardInterrupt(),
])
def test_uncertain_outcome_keeps_the_worst_case_reserved(error, n2_source, taxonomy, register):
    transport = RecordingTransport(error=error)
    config = _config("anthropic")
    with pytest.raises(type(error)):
        _run(config, n2_source, taxonomy, register, transport)
    events = register.events()
    assert [e["ev"] for e in events] == ["reserve", "unknown"]
    reserved = Decimal(str(events[0]["est_usd"]))
    assert register.committed_usd() == reserved
    summary = _load_governor().summarize(events)  # what B5 would read: still held
    assert summary["in_flight"] == 1
    assert summary["reserved_open_usd"] == pytest.approx(float(reserved))
    assert summary["failed"] == 0


def test_uncertain_outcome_still_counts_against_the_budget(tmp_path, n2_source, taxonomy):
    register = arm.JsonlSpendRegister(max_usd=Decimal("0.5"), root=tmp_path)
    config = _config("anthropic", max_output_tokens=16000)  # worst case ~0.25 USD
    timeout = RecordingTransport(error=TimeoutError("synthetic"))
    with pytest.raises(TimeoutError):
        _run(config, n2_source, taxonomy, register, timeout, alias="C1")
    second = RecordingTransport(error=TimeoutError("synthetic"))
    with pytest.raises(TimeoutError):
        _run(config, n2_source, taxonomy, register, second, alias="C2")
    third = RecordingTransport(_anthropic_reply([]))
    with pytest.raises(arm.SpendRefused, match="budget"):
        _run(config, n2_source, taxonomy, register, third, alias="C3")
    assert third.calls == []


def test_no_retry_while_an_uncertain_call_is_unreconciled(n2_source, taxonomy, register):
    config = _config("anthropic")
    timeout = RecordingTransport(error=TimeoutError("synthetic"))
    with pytest.raises(TimeoutError):
        _run(config, n2_source, taxonomy, register, timeout)
    retry = RecordingTransport(_anthropic_reply([]))
    with pytest.raises(arm.SpendRefused, match="reconcil"):
        _run(config, n2_source, taxonomy, register, retry)
    assert retry.calls == []


def test_unreconciled_call_does_not_block_other_contracts_or_providers(
    n2_source, taxonomy, register,
):
    timeout = RecordingTransport(error=TimeoutError("synthetic"))
    config = _config("anthropic")
    with pytest.raises(TimeoutError):
        _run(config, n2_source, taxonomy, register, timeout)
    other_alias = RecordingTransport(_anthropic_reply([]))
    _run(config, n2_source, taxonomy, register, other_alias, alias="C2")
    other_provider = RecordingTransport(_openai_reply([]))
    _run(_config("openai"), n2_source, taxonomy, register, other_provider)
    assert len(other_alias.calls) == 1
    assert len(other_provider.calls) == 1


def test_an_open_reservation_blocks_a_concurrent_duplicate(n2_source, taxonomy, register):
    config = _config("anthropic")
    key = arm.call_key("C1", "anthropic")
    register.reserve(provider="anthropic", model=config.model,
                     est_usd=Decimal("0.01"), key=key,
                     source_sha256=n2_source.sha256)  # another process, in flight
    transport = RecordingTransport(_anthropic_reply([]))
    with pytest.raises(arm.SpendRefused, match="reconcil"):
        _run(config, n2_source, taxonomy, register, transport)
    assert transport.calls == []


@pytest.mark.parametrize("error", [
    arm.RequestNotSent("synthetic"),
])
def test_provably_unbilled_failures_release_and_allow_a_retry(
    error, n2_source, taxonomy, register,
):
    config = _config("anthropic")
    failing = RecordingTransport(error=error)
    with pytest.raises(type(error)):
        _run(config, n2_source, taxonomy, register, failing)
    assert register.committed_usd() == 0
    retry = RecordingTransport(_anthropic_reply([]))
    _run(config, n2_source, taxonomy, register, retry)
    assert len(retry.calls) == 1


def test_a_successful_call_settles_and_does_not_block_a_later_run(n2_source, taxonomy, register):
    config = _config("anthropic")
    for _ in range(2):
        _run(config, n2_source, taxonomy, register, RecordingTransport(_anthropic_reply([])))
    assert [e["ev"] for e in register.events()] == ["reserve", "done", "reserve", "done"]


@pytest.mark.parametrize("outcomes", [
    ("ok", "timeout", "not_sent", "ok", "rejected", "timeout"),
    ("timeout", "timeout", "timeout", "timeout"),
    ("not_sent", "rejected", "ok", "ok", "ok", "ok", "ok"),
])
def test_spend_invariants_hold_for_any_sequence_of_outcomes(
    outcomes, tmp_path, n2_source, taxonomy,
):
    """Committed spend never exceeds the cap; uncertain holds are never released."""
    cap = Decimal("0.6")
    register = arm.JsonlSpendRegister(max_usd=cap, root=tmp_path)
    errors = {"timeout": TimeoutError("t"), "not_sent": arm.RequestNotSent("n"),
              "rejected": RuntimeError("synthetic HTTP 429")}
    for index, outcome in enumerate(outcomes):
        alias = arm.ALIASES[index % len(arm.ALIASES)]
        transport = (RecordingTransport(_anthropic_reply([])) if outcome == "ok"
                     else RecordingTransport(error=errors[outcome]))
        with contextlib.suppress(
            arm.SpendRefused, TimeoutError, arm.RequestNotSent, RuntimeError,
        ):
            _run(_config("anthropic"), n2_source, taxonomy, register, transport, alias=alias)
        assert register.committed_usd() <= cap
    events = register.events()
    terminal = [e for e in events if e["ev"] in ("done", "fail", "unknown")]
    assert len({e["id"] for e in terminal}) == len(terminal)  # one outcome per call
    unknown = {e["id"] for e in events if e["ev"] == "unknown"}
    released = {e["id"] for e in events if e["ev"] in ("done", "fail")}
    assert not unknown & released


# --- HttpxTransport: classification of what was (not) sent, no network ------


def _httpx_response(status, payload=None):
    import httpx

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return httpx.Response(status, json=payload or {}, request=request)


@pytest.fixture
def anthropic_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-synthetic-key-for-tests-only")


@pytest.mark.usefixtures("anthropic_key")
@pytest.mark.parametrize(
    "status", [400, 401, 402, 403, 404, 408, 413, 422, 429, 500, 502, 503, 504, 529],
)
def test_transport_keeps_every_http_error_billing_uncertain(monkeypatch, status):
    """Policy A: a response came back, so no-charge is not demonstrable."""
    import httpx

    monkeypatch.setattr(httpx, "post", lambda *_a, **_k: _httpx_response(status))
    transport = arm.HttpxTransport()
    with pytest.raises(httpx.HTTPStatusError) as caught:
        transport("anthropic", {"model": "m"})
    assert not isinstance(caught.value, arm.RequestNotSent)
    assert not hasattr(arm, "ProviderRejected")


@pytest.mark.usefixtures("anthropic_key")
def test_transport_maps_connection_failures_to_not_sent(monkeypatch):
    import httpx

    def refuse(*_a, **_k):
        raise httpx.ConnectError("synthetic refused")

    monkeypatch.setattr(httpx, "post", refuse)
    transport = arm.HttpxTransport()
    with pytest.raises(arm.RequestNotSent):
        transport("anthropic", {"model": "m"})


@pytest.mark.usefixtures("anthropic_key")
def test_transport_keeps_read_timeouts_uncertain(monkeypatch):
    import httpx

    def slow(*_a, **_k):
        raise httpx.ReadTimeout("synthetic read timeout")

    monkeypatch.setattr(httpx, "post", slow)
    transport = arm.HttpxTransport()
    with pytest.raises(httpx.ReadTimeout):
        transport("anthropic", {"model": "m"})


def test_missing_key_is_a_request_not_sent(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    transport = arm.HttpxTransport()
    with pytest.raises(arm.RequestNotSent, match="API key missing"):
        transport("openai", {"model": "m"})


# --- D2 (L0 22/11, QA FAIL P0 at c91c60a0) ------------------------------------


def _variant_source():
    """Same contract identity, different bytes (e.g. a re-export)."""
    text = N2_TEXT + " "
    return arm.DirectArmSource.from_n2_text(text, [(1, 0, 67), (2, 67, len(text))])


@pytest.mark.usefixtures("anthropic_key")
def test_529_overloaded_is_billing_uncertain_and_blocks_retry(
    monkeypatch, n2_source, taxonomy, register,
):
    """F1: 529 is not proof of no charge -> unknown, hold kept, no retry."""
    import httpx

    monkeypatch.setattr(httpx, "post", lambda *_a, **_k: _httpx_response(529))
    config = _config("anthropic")
    transport = arm.HttpxTransport()
    with pytest.raises(httpx.HTTPStatusError):
        _run(config, n2_source, taxonomy, register, transport)
    events = register.events()
    assert [e["ev"] for e in events] == ["reserve", "unknown"]
    assert register.committed_usd() == Decimal(str(events[0]["est_usd"]))
    retry = RecordingTransport(_anthropic_reply([]))
    with pytest.raises(arm.SpendRefused, match="reconcil"):
        _run(config, n2_source, taxonomy, register, retry)
    assert retry.calls == []


def test_unknown_blocks_the_same_contract_and_provider_even_with_another_source(
    n2_source, taxonomy, register,
):
    """F2: a different source sha256 for the same alias+provider cannot bypass it."""
    config = _config("anthropic")
    timeout = RecordingTransport(error=TimeoutError("synthetic"))
    with pytest.raises(TimeoutError):
        _run(config, n2_source, taxonomy, register, timeout)
    variant = _variant_source()
    assert variant.sha256 != n2_source.sha256
    retry = RecordingTransport(_anthropic_reply([]))
    with pytest.raises(arm.SpendRefused, match="reconcil"):
        _run(config, variant, taxonomy, register, retry)
    assert retry.calls == []


def test_in_flight_call_blocks_the_same_contract_and_provider_with_another_source(
    n2_source, taxonomy, register,
):
    config = _config("anthropic")
    register.reserve(provider="anthropic", model=config.model, est_usd=Decimal("0.01"),
                     key=arm.call_key("C1", "anthropic"),
                     source_sha256=n2_source.sha256)  # another process, in flight
    transport = RecordingTransport(_anthropic_reply([]))
    variant = _variant_source()
    with pytest.raises(arm.SpendRefused, match="reconcil"):
        _run(config, variant, taxonomy, register, transport)
    assert transport.calls == []


def test_source_sha256_is_kept_for_traceability(n2_source, taxonomy, register):
    config = _config("anthropic")
    timeout = RecordingTransport(error=TimeoutError("synthetic"))
    with pytest.raises(TimeoutError):
        _run(config, n2_source, taxonomy, register, timeout)
    variant = _variant_source()
    retry = RecordingTransport(_anthropic_reply([]))
    with pytest.raises(arm.SpendRefused):
        _run(config, variant, taxonomy, register, retry)
    reserve, unknown, refused = register.events()
    assert reserve["key"] == "C1:anthropic"
    assert reserve["source_sha256"] == n2_source.sha256
    assert reserve["source_kind"] == "n2_text"
    assert unknown["ev"] == "unknown"
    assert refused["ev"] == "refused"
    assert refused["source_sha256"] == variant.sha256


def test_after_a_settled_call_a_new_source_revision_may_run(n2_source, taxonomy, register):
    """Blocking is only for open/uncertain calls; settled history does not block."""
    config = _config("anthropic")
    _run(config, n2_source, taxonomy, register, RecordingTransport(_anthropic_reply([])))
    second = RecordingTransport(_anthropic_reply([]))
    _run(config, _variant_source(), taxonomy, register, second)
    assert len(second.calls) == 1


# --- Policy A (L0 23/11): no HTTP response is provably unbilled ---------------


@pytest.mark.usefixtures("anthropic_key")
def test_429_is_billing_uncertain_and_blocks_retry(monkeypatch, n2_source, taxonomy, register):
    import httpx

    monkeypatch.setattr(httpx, "post", lambda *_a, **_k: _httpx_response(429))
    config = _config("anthropic")
    transport = arm.HttpxTransport()
    with pytest.raises(httpx.HTTPStatusError):
        _run(config, n2_source, taxonomy, register, transport)
    events = register.events()
    assert [e["ev"] for e in events] == ["reserve", "unknown"]
    assert register.committed_usd() == Decimal(str(events[0]["est_usd"]))
    retry = RecordingTransport(_anthropic_reply([]))
    with pytest.raises(arm.SpendRefused, match="reconcil"):
        _run(config, n2_source, taxonomy, register, retry)
    assert retry.calls == []


def test_every_event_carries_the_ledger_schema_version(n2_source, taxonomy, register):
    config = _config("anthropic")
    _run(config, n2_source, taxonomy, register, RecordingTransport(_anthropic_reply([])))
    other = _config("openai")
    timeout = RecordingTransport(error=TimeoutError("t"))
    with pytest.raises(TimeoutError):
        _run(other, n2_source, taxonomy, register, timeout)
    retry = RecordingTransport(_openai_reply([]))
    with pytest.raises(arm.SpendRefused):
        _run(other, n2_source, taxonomy, register, retry)
    events = register.events()
    assert {e["ev"] for e in events} == {"reserve", "done", "unknown", "refused"}
    assert {e["schema"] for e in events} == {arm.LEDGER_SCHEMA}


def test_release_records_the_not_sent_evidence(n2_source, taxonomy, register):
    config = _config("anthropic")
    not_sent = RecordingTransport(error=arm.RequestNotSent("synthetic: no connection"))
    with pytest.raises(arm.RequestNotSent):
        _run(config, n2_source, taxonomy, register, not_sent)
    fail = register.events()[-1]
    assert fail["ev"] == "fail"
    assert fail["release"] == "request_not_sent"
    assert fail["schema"] == arm.LEDGER_SCHEMA


# --- legacy ledgers (no schema): read as written, interpreted fail-closed -----


def _write_legacy(register, *events):
    register.path.parent.mkdir(parents=True, exist_ok=True)
    with register.path.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps({"t": 0.0, "arm": "B3", **event}) + "\n")
    return register.path.read_bytes()


def _legacy_reserve(rid, **extra):
    return {"ev": "reserve", "id": rid, "provider": "anthropic", "model": "synthetic",
            "est_usd": 0.25, "pid": 1, **extra}


def test_legacy_key_with_source_sha_blocks_its_alias_and_provider(n2_source, taxonomy, register):
    """c91c60a0 ledgers used key alias:provider:kind:sha."""
    _write_legacy(
        register,
        _legacy_reserve("l1", key=f"C1:anthropic:n2_text:{n2_source.sha256}"),
        {"ev": "unknown", "id": "l1", "provider": "anthropic", "error": "TimeoutError"},
    )
    blocked = RecordingTransport(_anthropic_reply([]))
    anthropic = _config("anthropic")
    with pytest.raises(arm.SpendRefused, match="reconcil"):
        _run(anthropic, n2_source, taxonomy, register, blocked)
    assert blocked.calls == []
    other = RecordingTransport(_anthropic_reply([]))
    _run(_config("anthropic"), n2_source, taxonomy, register, other, alias="C2")
    assert len(other.calls) == 1


def test_legacy_reservation_without_key_blocks_every_call(n2_source, taxonomy, register):
    """dbb71fe6 ledgers wrote reservations without any key."""
    _write_legacy(register, _legacy_reserve("l2"))
    for provider, alias in (("anthropic", "C1"), ("anthropic", "C2"), ("openai", "C3")):
        transport = RecordingTransport(
            _anthropic_reply([]) if provider == "anthropic" else _openai_reply([])
        )
        config = _config(provider)
        with pytest.raises(arm.SpendRefused, match="reconcil"):
            _run(config, n2_source, taxonomy, register, transport, alias=alias)
        assert transport.calls == []


def test_legacy_fail_does_not_release_a_possibly_billed_call(n2_source, taxonomy, register):
    """Old versions wrote 'fail' for timeouts/429/529: not evidence of no charge."""
    _write_legacy(
        register,
        _legacy_reserve("l3", key="C1:anthropic"),
        {"ev": "fail", "id": "l3", "provider": "anthropic", "error": "TimeoutError"},
    )
    assert register.committed_usd() == Decimal("0.25")
    blocked = RecordingTransport(_anthropic_reply([]))
    anthropic = _config("anthropic")
    with pytest.raises(arm.SpendRefused, match="reconcil"):
        _run(anthropic, n2_source, taxonomy, register, blocked)
    assert blocked.calls == []


def test_legacy_settled_call_neither_blocks_nor_is_forgotten(n2_source, taxonomy, register):
    _write_legacy(
        register,
        _legacy_reserve("l4", key=f"C1:anthropic:n2_text:{n2_source.sha256}"),
        {"ev": "done", "id": "l4", "provider": "anthropic", "model": "synthetic",
         "in": 10, "out": 10, "usd": 0.07, "message_id": "m", "stop_reason": "tool_use"},
    )
    transport = RecordingTransport(_anthropic_reply([]))
    _run(_config("anthropic"), n2_source, taxonomy, register, transport)
    assert len(transport.calls) == 1
    assert register.committed_usd() == Decimal("0.07") + Decimal("0.006")


def test_legacy_lines_are_never_rewritten_and_stay_governor_readable(
    n2_source, taxonomy, register,
):
    before = _write_legacy(
        register,
        _legacy_reserve("l5", key=f"C1:anthropic:n2_text:{n2_source.sha256}"),
        {"ev": "unknown", "id": "l5", "provider": "anthropic", "error": "TimeoutError"},
    )
    _run(_config("openai"), n2_source, taxonomy, register,
         RecordingTransport(_openai_reply([])), alias="C2")
    assert register.path.read_bytes().startswith(before)  # append-only, no migration
    summary = _load_governor().summarize(register.events())
    assert summary["in_flight"] == 1
    assert summary["completed"] == 1


def test_legacy_holds_count_against_the_budget(tmp_path, n2_source, taxonomy):
    register = arm.JsonlSpendRegister(max_usd=Decimal("0.4"), root=tmp_path)
    _write_legacy(register, _legacy_reserve("l6", key="C2:openai:pdf:abc"),
                  {"ev": "fail", "id": "l6", "provider": "openai", "error": "ProviderRejected"})
    transport = RecordingTransport(_anthropic_reply([]))
    config = _config("anthropic", max_output_tokens=16000)  # worst case ~0.25 USD
    with pytest.raises(arm.SpendRefused, match="budget"):
        _run(config, n2_source, taxonomy, register, transport)
    assert transport.calls == []


def test_unversioned_release_marker_is_not_trusted(n2_source, taxonomy, register):
    """A 'fail' that claims request_not_sent but lacks the schema is not evidence."""
    _write_legacy(
        register,
        _legacy_reserve("l7", key="C1:anthropic"),
        {"ev": "fail", "id": "l7", "provider": "anthropic", "error": "RequestNotSent",
         "release": "request_not_sent"},
    )
    assert register.committed_usd() == Decimal("0.25")
    transport = RecordingTransport(_anthropic_reply([]))
    config = _config("anthropic")
    with pytest.raises(arm.SpendRefused, match="reconcil"):
        _run(config, n2_source, taxonomy, register, transport)
    assert transport.calls == []


def test_register_refuses_to_release_without_not_sent_evidence(register):
    call_id = register.reserve(provider="anthropic", model="m", est_usd=Decimal("0.1"),
                               key="C1:anthropic", source_sha256="a" * 64)
    not_evidence = TimeoutError("synthetic")
    with pytest.raises(TypeError, match="RequestNotSent"):
        register.fail(call_id, provider="anthropic", error=not_evidence)
    assert [e["ev"] for e in register.events()] == ["reserve"]
    assert register.committed_usd() == Decimal("0.1")


# --- L0 23/11 (7101807816): larger liability prevails, no double count, -------
# --- no false release; B3 view must never be below the legacy governor view --


def _settled(rid, usd, **extra):
    return {"ev": "done", "id": rid, "provider": "anthropic", "model": "synthetic",
            "in": 1, "out": 1, "usd": usd, "message_id": "m", "stop_reason": "tool_use", **extra}


@pytest.mark.parametrize("amounts", [(0.05, 0.07), (0.07, 0.05)])
def test_duplicate_settlements_of_one_reservation_count_once(register, amounts):
    """A replayed/duplicated settlement must not double-count spend; the larger wins."""
    first, second = amounts
    _write_legacy(register, _legacy_reserve("d1", key="C1:anthropic"),
                  _settled("d1", first), _settled("d1", second))
    assert register.committed_usd() == Decimal("0.07")


def test_settlement_is_not_reopened_by_a_later_legacy_fail(n2_source, taxonomy, register):
    _write_legacy(register, _legacy_reserve("d2", key="C1:anthropic"), _settled("d2", 0.07),
                  {"ev": "fail", "id": "d2", "provider": "anthropic", "error": "TimeoutError"})
    assert register.committed_usd() == Decimal("0.07")
    transport = RecordingTransport(_anthropic_reply([]))
    _run(_config("anthropic"), n2_source, taxonomy, register, transport)
    assert len(transport.calls) == 1


def test_v2_release_cannot_close_a_legacy_reservation(n2_source, taxonomy, register):
    """No false release: release evidence only applies to a v2 reservation."""
    _write_legacy(
        register,
        _legacy_reserve("d3", key="C1:anthropic"),
        {"ev": "fail", "id": "d3", "provider": "anthropic", "error": "RequestNotSent",
         "release": "request_not_sent", "schema": arm.LEDGER_SCHEMA},
    )
    assert register.committed_usd() == Decimal("0.25")
    transport = RecordingTransport(_anthropic_reply([]))
    config = _config("anthropic")
    with pytest.raises(arm.SpendRefused, match="reconcil"):
        _run(config, n2_source, taxonomy, register, transport)
    assert transport.calls == []


def test_blocked_retry_after_legacy_timeout_never_charges_twice(n2_source, taxonomy, register):
    _write_legacy(register, _legacy_reserve("d4", key="C1:anthropic"),
                  {"ev": "fail", "id": "d4", "provider": "anthropic", "error": "TimeoutError"})
    transport = RecordingTransport(_anthropic_reply([]))
    config = _config("anthropic")
    with pytest.raises(arm.SpendRefused, match="reconcil"):
        _run(config, n2_source, taxonomy, register, transport)
    assert transport.calls == []
    assert register.committed_usd() == Decimal("0.25")  # held once, not 0.25 x 2
    assert [e["ev"] for e in register.events()][-1] == "refused"


def test_releasing_one_call_never_releases_another(n2_source, taxonomy, register):
    _write_legacy(register, _legacy_reserve("d5", key="C1:anthropic"),
                  {"ev": "fail", "id": "d5", "provider": "anthropic", "error": "TimeoutError"})
    not_sent = RecordingTransport(error=arm.RequestNotSent("synthetic"))
    config = _config("anthropic")
    with pytest.raises(arm.RequestNotSent):
        _run(config, n2_source, taxonomy, register, not_sent, alias="C2")
    assert register.committed_usd() == Decimal("0.25")


_LEGACY_FIXTURES = {
    "reserve+fail(timeout)": [
        _legacy_reserve("f1", key="C1:anthropic"),
        {"ev": "fail", "id": "f1", "provider": "anthropic", "error": "TimeoutError"}],
    "reserve+unknown": [
        _legacy_reserve("f2", key="C1:anthropic:n2_text:abc"),
        {"ev": "unknown", "id": "f2", "provider": "anthropic", "error": "TimeoutError"}],
    "keyless reserve": [_legacy_reserve("f3")],
    "reserve+done": [_legacy_reserve("f4", key="C1:anthropic"), _settled("f4", 0.07)],
    "duplicate done": [_legacy_reserve("f5", key="C1:anthropic"),
                       _settled("f5", 0.07), _settled("f5", 0.05)],
    "v2 release of legacy id": [
        _legacy_reserve("f6", key="C1:anthropic"),
        {"ev": "fail", "id": "f6", "provider": "anthropic", "error": "RequestNotSent",
         "release": "request_not_sent", "schema": "b3-ledger-v2"}],
}


@pytest.mark.parametrize("name", sorted(_LEGACY_FIXTURES))
def test_b3_liability_is_never_below_the_legacy_governor_view(register, name):
    """L0: the larger exposure prevails; B3 must never under-report vs governor."""
    _write_legacy(register, *_LEGACY_FIXTURES[name])
    summary = _load_governor().summarize(register.events())
    governor = Decimal(str(summary["spent_usd"])) + Decimal(str(summary["reserved_open_usd"]))
    assert register.committed_usd() >= governor


@pytest.mark.parametrize("schema", [{}, {"schema": arm.LEDGER_SCHEMA}], ids=["legacy", "v2"])
def test_identical_reservation_replay_is_idempotent(register, schema):
    event = _legacy_reserve("replay", key="C1:anthropic", **schema)
    before = _write_legacy(register, event, dict(event), dict(event))
    assert register.committed_usd() == Decimal("0.25")
    assert len(register._open_reserves(register.events())) == 1
    assert register.path.read_bytes() == before


def test_distinct_reservations_are_not_deduplicated(register):
    _write_legacy(register, _legacy_reserve("r1"), _legacy_reserve("r2"))
    assert register.committed_usd() == Decimal("0.50")


def test_conflicting_reservation_replay_preserves_conservative_hold(register):
    _write_legacy(register, _legacy_reserve("r1"), _legacy_reserve("r1", est_usd=0.35))
    assert register.committed_usd() == Decimal("0.60")


def test_unattributed_reserves_are_not_deduplicated(register):
    event = _legacy_reserve(None)
    _write_legacy(register, event, dict(event))
    assert register.committed_usd() == Decimal("0.50")
