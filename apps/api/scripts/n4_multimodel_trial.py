"""Single-call, metadata-only N4 provider trial on SEC contract excerpts."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path

from src.analysis.adapters.ai.tools.n4_external_provider import get_n4_external_provider
from src.analysis.adapters.ai.tools.risk_extraction_tool import (
    RiskExtractionInput,
    RiskExtractionTool,
)


class _ConcisePromptRiskTool(RiskExtractionTool):
    def _build_default_prompt(self, input_data, is_retry=False):
        _ = is_retry
        system = (
            "You are an experienced EPC contract reviewer. Examine all provided clauses, "
            "including exceptions, cross-references, contradictory numbers and conditional remedies. "
            "Identify every distinct material risk grounded in the source. "
            "Return JSON with a risks array. Each object has category LEGAL/SCHEDULE/QUALITY/SCOPE/TECHNICAL/BUDGET, "
            "title, summary, description, probability LOW/MEDIUM/HIGH, impact LOW/MEDIUM/HIGH/CRITICAL, "
            "mitigation_suggestion, source_quote, source_text_snippet, clause_ref. "
            "Cite an exact contiguous source_quote of 80 or more characters per risk; include the operative exception. "
            "source_text_snippet must preserve the surrounding original evidence. No invented quotes or generic risks. "
            "Do not claim to have examined any annex that is not supplied."
        )
        return "CONTRACT:\n\n" + input_data.document_text, system


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--receipt", required=True)
    args = ap.parse_args()
    source = Path(args.source).read_text()
    if len(source) < 1000:
        raise SystemExit("SOURCE_TOO_SMALL")
    provider = get_n4_external_provider()
    receipt = {
        "provider": provider.config.provider,
        "model": provider.config.model,
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "source_chars": len(source),
        "scope": "Four authentic SolarMax excerpts, NOT full contract",
        "status": "FAIL",
        "trial_style": os.getenv("C2PRO_N4_TRIAL_STYLE", "full"),
    }
    try:
        style = os.getenv("C2PRO_N4_TRIAL_STYLE", "full")
        if style not in {"full", "concise"}:
            raise ValueError("UNSUPPORTED_N4_TRIAL_STYLE")
        tool_class = _ConcisePromptRiskTool if style == "concise" else RiskExtractionTool
        tool = tool_class(anthropic_wrapper=provider, prompt_manager=object())
        result = await tool.execute(
            RiskExtractionInput(document_text=source, strict_completeness=True)
        )
        risks = result.data or []
        exact = sum(bool(r.source_quote and r.source_quote in source) for r in risks)
        refs = sorted({str(r.clause_ref) for r in risks if r.clause_ref})
        receipt.update(
            {
                "status": "PASS"
                if result.success and len(risks) > 0 and exact == len(risks)
                else "FAIL",
                "success": result.success,
                "failure_class": result.error_type,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "cost_estimated_usd": result.cost_usd,
                "risk_count": len(risks),
                "exact_quote_count": exact,
                "clause_refs": refs,
                "titles": [str(r.title)[:110] for r in risks[:30]],
            }
        )
    except Exception as ex:
        receipt["failure_class"] = type(ex).__name__
    finally:
        output = Path(args.receipt)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True))
        print(json.dumps({k: v for k, v in receipt.items() if k != "titles"}, sort_keys=True))
    return 0 if receipt["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
