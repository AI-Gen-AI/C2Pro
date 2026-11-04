"""Single governed real-provider N12 check (no N4 rerun, no database, no browser).

Reuses the immutable nine-clause EPC fixture and deliberately adversarial
extraction. The evidence output stores metrics, hashes and provider receipts
ONLY -- no document text, generated completion, or credentials.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

API_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = API_ROOT.parents[1]
RESULT_PATH = API_ROOT.parent / "web" / "playwright-report" / "n12-real-ai-evaluation.json"

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from n4_n12_real_ai_eval import (  # noqa: E402
    _adversarial_risks,
    _governor_summary,
    _source_text,
    load_fixture,
    score_n12,
)


async def run() -> dict[str, Any]:
    if os.getenv("C2PRO_AI_MOCK") != "0":
        raise RuntimeError("N12_PROVIDER_MUST_BE_REAL")
    fixture = load_fixture()
    source = _source_text(fixture)

    from src.analysis.adapters.ai.anthropic_client import AIService
    from src.analysis.application.critique_extraction_use_case import (
        CritiqueExtractionCommand,
        CritiqueExtractionUseCase,
    )
    from src.analysis.domain.critique_findings import source_bound_findings
    from src.core.ai.anthropic_wrapper import AIRequest, AnthropicWrapper
    from src.core.ai.model_router import AITaskType

    wrapper = AnthropicWrapper(enable_cache=False, enable_retry=False, max_tokens_limit=4096)
    json_parser = AIService(wrapper=wrapper)

    class SingleNoRetryPort:
        parse_failure_type: str | None = None
        completion_sha256: str | None = None
        payload: Any = None

        async def run_extraction(self, system_prompt: str, user_content: str) -> Any:
            response = await wrapper.generate(
                AIRequest(
                    prompt=user_content,
                    system_prompt=system_prompt,
                    task_type=AITaskType.COMPLEX_EXTRACTION,
                    low_budget_mode=True,
                    use_cache=False,
                )
            )
            self.completion_sha256 = hashlib.sha256(
                response.content.encode("utf-8")
            ).hexdigest()
            try:
                self.payload = json_parser._parse_json_response(response.content)
            except Exception as exc:
                self.parse_failure_type = type(exc).__name__
                raise
            return self.payload

    port = SingleNoRetryPort()
    response = await CritiqueExtractionUseCase(ai=port).execute(
        CritiqueExtractionCommand(
            extracted_risks=_adversarial_risks(fixture),
            extracted_wbs=[],
            doc_type="contract",
            retry_count=0,
            source_text=source,
        )
    )
    metrics = score_n12(response.critique_notes, source)
    structured = (
        source_bound_findings(port.payload.get("findings"), source_text=source)
        if isinstance(port.payload, dict)
        else []
    )
    source_refs = sorted({str(item["clause_ref"]) for item in structured})
    meaningful = (
        port.parse_failure_type is None
        and not response.critique_notes.startswith("Automatic critique inconclusive.")
        and not response.critique_notes.startswith("N12_UNASSESSED:")
        and response.status == "RETRY"
    )
    passed = (
        meaningful
        and metrics["omissions_detected"] == 2
        and metrics["incorrect_interpretation_detected"] is True
        and set(source_refs) >= {"EPC-04", "EPC-05", "EPC-07"}
        and len(structured) >= 3
        and metrics["critique_citation_validity"] is True
    )
    return {
        "fixture_id": fixture["fixture_id"],
        "fixture_sha256": hashlib.sha256(
            (REPOSITORY_ROOT / "c2pro-n4n12-epc-synthetic-v1.json").read_bytes()
        ).hexdigest(),
        "provider_call": "real",
        "ai_mock": False,
        "n12": {
            **metrics,
            "status": response.status,
            "quality_state": "ACCEPTED" if passed else ("ASSESSED" if meaningful else "NOT_ASSESSED"),
            "supported_findings": len(structured),
            "supported_clause_ids": source_refs,
            "parse_failure_type": port.parse_failure_type,
            "completion_sha256": port.completion_sha256,
            "notes_sha256": hashlib.sha256(response.critique_notes.encode()).hexdigest(),
        },
        "provider": _governor_summary(),
        "verdict": "N12_ACCEPTED" if passed else "N12_NOT_ACCEPTED",
    }


def main() -> int:
    result = asyncio.run(run())
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": result["verdict"],
        "provider": result["provider"],
        "n12": result["n12"],
    }, sort_keys=True))
    if result["provider"].get("completed_calls") != 1 or result["provider"].get("calls") != 1:
        return 3
    return 0 if result["verdict"] == "N12_ACCEPTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
