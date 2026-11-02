"""The real-AI pilot script, exercised with a FAKE provider (no network, no key, no spend).

What is pinned: exactly one provider call is made, the receipt carries the provider's message id / stop reason / usage, the
expected categories come from the known contract's manifest, a quote that is not in the fixture is flagged, a failed
extraction turns into an explicit error and the recorder counts every call.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

SCRIPT_DIR = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import acc01_real_ai_pilot as pilot  # noqa: E402

from src.core.ai.anthropic_wrapper import AIResponse  # noqa: E402

FIXTURE = (pilot.FIXTURE_DIR / "contract-a.source.txt").read_text(encoding="utf-8")
QUOTE = "The total contract price is 2,400,000.00 EUR"


class FakeWrapper:
    def __init__(self, content: str) -> None:
        self.content, self.seen = content, 0

    async def generate(self, request):
        self.seen += 1
        raw = SimpleNamespace(
            id="msg_fake_001", model="claude-fake", stop_reason="end_turn", usage=SimpleNamespace(input_tokens=900, output_tokens=300)
        )
        return AIResponse(
            content=self.content, model_used="claude-fake", input_tokens=900, output_tokens=300, cost_usd=0.0123, latency_ms=5.0,
            request_id="req-fake", raw_response=raw,
        )


def _risks(*items: dict) -> str:
    return json.dumps({"risks": list(items)})


def _risk(category: str, quote: str = QUOTE) -> dict:
    return {"title": f"{category} risk", "category": category, "probability": "HIGH", "impact": "HIGH", "source_quote": quote, "clause_ref": "2"}


def test_the_expected_categories_come_from_the_known_contract_not_from_a_hand_written_list() -> None:
    assert pilot.expected_categories() == ["BUDGET", "LEGAL", "QUALITY", "SCHEDULE", "SCOPE", "TECHNICAL"]


def test_one_call_a_receipt_with_the_provider_evidence_and_the_missing_categories() -> None:
    wrapper = FakeWrapper(_risks(_risk("BUDGET"), _risk("LEGAL", "invented clause that is not in the fixture")))
    receipt = asyncio.run(pilot.run(wrapper=wrapper))
    assert wrapper.seen == 1 and receipt["calls"] == 1 and "error" not in receipt
    assert receipt["provider_responses"][0]["message_id"] == "msg_fake_001" and receipt["provider_responses"][0]["stop_reason"] == "end_turn"
    assert receipt["input_tokens"] == 900 and receipt["output_tokens"] == 300 and receipt["estimated_cost_usd"] == 0.0123
    assert receipt["risk_categories"] == ["BUDGET", "LEGAL"]
    assert receipt["missing_expected_categories"] == ["QUALITY", "SCHEDULE", "SCOPE", "TECHNICAL"]
    verbatim = {r["category"]: r["quote_is_verbatim_in_fixture"] for r in receipt["risks"]}
    assert QUOTE in FIXTURE and verbatim == {"BUDGET": True, "LEGAL": False}, "a quote that is not in the contract is flagged"
    assert receipt["ai_mock"] is False and receipt["automatic_retries"] == 0 and "NOT S1-S2" in receipt["claims"]


def test_a_failed_extraction_is_an_explicit_error_not_a_pass() -> None:
    receipt = asyncio.run(pilot.run(wrapper=FakeWrapper("not json at all")))
    assert receipt["calls"] == 1 and receipt["error"].startswith("PILOT_REAL_EXTRACTION_FAILED")


def test_the_recorder_counts_every_provider_call() -> None:
    wrapper = FakeWrapper(_risks(_risk("BUDGET")))
    recorder = pilot._Recorder(wrapper)

    async def two() -> None:
        await recorder.generate(object())
        await recorder.generate(object())

    asyncio.run(two())
    assert recorder.requests == 2 and wrapper.seen == 2


def test_the_script_imports_the_package_when_run_the_way_ci_runs_it() -> None:
    """The first CI dispatch died with ModuleNotFoundError: src (scripts/ on sys.path, apps/api not) before any provider call.

    pytest puts apps/api on sys.path, which hid it. ``-I`` ignores PYTHONPATH and the cwd, like a bare ``python scripts/x.py``.
    """
    import subprocess

    api_root = Path(__file__).resolve().parents[3]
    code = (
        "import importlib.util;"
        "s=importlib.util.spec_from_file_location('p','scripts/acc01_real_ai_pilot.py');"
        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        "import src.analysis.domain.risk_categories as r;print('IMPORT_OK', m.expected_categories())"
    )
    out = subprocess.run(
        [sys.executable, "-I", "-c", code], cwd=api_root, capture_output=True, text=True, timeout=120, check=False
    )
    assert out.returncode == 0 and "IMPORT_OK" in out.stdout, out.stderr[-500:]
