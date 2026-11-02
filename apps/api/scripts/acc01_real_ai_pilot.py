"""ACC-01 partial S1-S2 pilot: ONE real-AI risk extraction over the synthetic PJ-01 Contract A.

This proves exactly one thing: that C2Pro's own risk extractor, with a real provider call, produces findings from a known
contract. It does NOT prove S1-S2 (no upload, no Clerk identity, no database, no HITL, no persistence).

Guarantees enforced here, not just documented:

* exactly one provider call: the wrapper is wrapped in a recorder and the run fails if the call count is not 1;
* no automatic retries: transport retries and the response cache are disabled, and the tool's own retry policy is 0;
* nothing but a sanitized receipt leaves the process (no key, no environment, no prompt beyond the public synthetic fixture).

The receipt carries what the provider returned (message id, stop reason, token usage) plus C2Pro's token-priced estimate,
which is an estimate and not a provider invoice.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "web" / "src" / "tests" / "e2e" / "test-data" / "pj01"
INPUT_CHAR_LIMIT = 5_000  # the tool never sends more than this when RISK_EXTRACTION_MAX_CHARS=5000
# Enough room for eight structured risks. 512 (the first draft) would truncate the JSON and waste the single run.
OUTPUT_TOKEN_CEILING = 4_096
MAX_RISKS = 8


class _Recorder:
    """Counts and keeps every provider response; delegates everything else to the real wrapper."""

    def __init__(self, wrapper: Any) -> None:
        self._wrapper = wrapper
        self.responses: list[Any] = []
        self.requests = 0

    async def generate(self, request: Any) -> Any:
        self.requests += 1
        response = await self._wrapper.generate(request)
        self.responses.append(response)
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapper, name)


def _value(item: Any) -> str:
    return str(getattr(item, "value", item))


def expected_categories(fixture_dir: Path = FIXTURE_DIR) -> list[str]:
    """The six Health categories the known contract declares, in the platform's canonical risk taxonomy."""
    from src.analysis.domain.risk_categories import normalize_category

    manifest = json.loads((fixture_dir / "contract-a.manifest.json").read_text(encoding="utf-8"))
    return sorted({_value(normalize_category(name)) for name in manifest["expected_health"]["categories"]})


def build_receipt(*, fixture_dir: Path, result: Any, recorder: _Recorder) -> dict[str, Any]:
    fixture = fixture_dir / "contract-a.source.txt"
    expected = expected_categories(fixture_dir)
    risks = list(result.data or [])
    categories = sorted({_value(risk.category) for risk in risks})
    provider = []
    for response in recorder.responses:
        raw = getattr(response, "raw_response", None)
        usage = getattr(raw, "usage", None)
        provider.append(
            {
                "message_id": getattr(raw, "id", None),
                "model": getattr(raw, "model", None) or response.model_used,
                "stop_reason": getattr(raw, "stop_reason", None),
                "input_tokens": getattr(usage, "input_tokens", response.input_tokens),
                "output_tokens": getattr(usage, "output_tokens", response.output_tokens),
                "retries": getattr(response, "retries", 0),
                "cached": bool(getattr(response, "cached", False)),
            }
        )
    return {
        "evidence_class": "LIVE_PARTIAL_TEST_S1_S2",
        "claims": "real-AI risk extractor only; NOT S1-S2, NOT upload/HITL/persistence/UAT",
        "fixture": "PJ01-CONTRACT-A",
        "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "provider": "Anthropic",
        "provider_call": "real",
        "ai_mock": False,
        "calls": recorder.requests,
        "automatic_retries": 0,
        "provider_responses": provider,
        "model": result.model_used,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        # C2Pro's token-priced estimate, not a provider invoice.
        "estimated_cost_usd": result.cost_usd,
        "risk_count": len(risks),
        "risk_categories": categories,
        "expected_categories": expected,
        "missing_expected_categories": sorted(set(expected) - set(categories)),
        "unexpected_categories": sorted(set(categories) - set(expected)),
        "risks": [
            {
                "title": risk.title,
                "category": _value(risk.category),
                "probability": _value(risk.probability),
                "impact": _value(risk.impact),
                "clause_ref": risk.clause_ref,
                "source_quote": (risk.source_quote or risk.source_text_snippet or "")[:240],
                "quote_is_verbatim_in_fixture": bool(
                    (risk.source_quote or risk.source_text_snippet)
                    and (risk.source_quote or risk.source_text_snippet or "").strip()
                    in fixture.read_text(encoding="utf-8")
                ),
                "risk_score": risk.risk_score,
            }
            for risk in risks
        ],
    }


async def run(*, wrapper: Any, fixture_dir: Path = FIXTURE_DIR) -> dict[str, Any]:
    from src.analysis.adapters.ai.tools.risk_extraction_tool import (
        RiskExtractionInput,
        RiskExtractionTool,
    )

    text = (fixture_dir / "contract-a.source.txt").read_text(encoding="utf-8")
    if len(text) > INPUT_CHAR_LIMIT:
        raise SystemExit("PILOT_INPUT_LIMIT_EXCEEDED")
    recorder = _Recorder(wrapper)
    tool = RiskExtractionTool(anthropic_wrapper=recorder)
    result = await tool.execute(RiskExtractionInput(document_text=text, max_risks=MAX_RISKS), low_budget_mode=True)
    receipt = build_receipt(fixture_dir=fixture_dir, result=result, recorder=recorder)
    if recorder.requests != 1:
        receipt["error"] = f"PILOT_CALL_COUNT_VIOLATION: {recorder.requests} provider calls"
    elif not result.success or not result.data or result.cached:
        receipt["error"] = f"PILOT_REAL_EXTRACTION_FAILED: {result.error or result.status}"
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="where the sanitized receipt JSON is written")
    args = parser.parse_args(argv)

    from src.core.ai.anthropic_wrapper import AnthropicWrapper

    # Transport retries and the response cache are off; the risk tool's retry policy is 0 (see its class definition).
    wrapper = AnthropicWrapper(enable_cache=False, enable_retry=False, max_tokens_limit=OUTPUT_TOKEN_CEILING)
    receipt = asyncio.run(run(wrapper=wrapper))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))  # the receipt is also the run log: sanitized, public fixture only
    return 1 if "error" in receipt else 0


if __name__ == "__main__":
    sys.exit(main())
