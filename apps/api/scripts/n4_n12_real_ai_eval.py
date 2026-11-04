"""Focused, governed real-AI evaluation of N4 extraction and N12 critique.

This is an operator-only harness.  It evaluates the committed synthetic EPC
fixture without database, browser, embeddings, S2, or persistence side effects.
The GitHub Actions job supplies the test-only provider credential and the
governor; this file never reads, prints, or writes a credential.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, cast


API_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = API_ROOT.parents[1]
FIXTURE_PATH = REPOSITORY_ROOT / "c2pro-n4n12-epc-synthetic-v1.json"
RESULT_PATH = API_ROOT.parent / "web" / "playwright-report" / "n4-n12-real-ai-evaluation.json"
FIXTURE_SHA256 = "6206d62492e786b2b97902cb59f19ba36f3bd996184470e5aecc3009cdf2c8eb"
EXPECTED_OMISSIONS = ("EPC-04", "EPC-07")
FALSE_INTERPRETATION_CLAUSE = "EPC-05"


def _normalized(value: object) -> str:
    return " ".join(str(value or "").lower().split())


def _source_text(fixture: dict[str, Any]) -> str:
    return "\n\n".join(
        f"{clause['id']}: {clause['text']}"
        for clause in fixture["contract"]["clauses"]
    )


def load_fixture(path: Path = FIXTURE_PATH) -> dict[str, Any]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != FIXTURE_SHA256:
        raise ValueError(f"FIXTURE_SHA256_MISMATCH: expected {FIXTURE_SHA256}, got {digest}")
    fixture = json.loads(raw)
    if len(fixture["contract"]["clauses"]) != 9:
        raise ValueError("FIXTURE_CLAUSE_COUNT_INVALID")
    if len(fixture["n4_oracle"]["expected_risks"]) != 9:
        raise ValueError("FIXTURE_N4_ORACLE_COUNT_INVALID")
    if tuple(fixture["n12_adversarial_input"]["injected_omissions"]) != EXPECTED_OMISSIONS:
        raise ValueError("FIXTURE_N12_OMISSIONS_INVALID")
    return cast(dict[str, Any], fixture)


def _valid_quote(risk: dict[str, Any], source: str) -> bool:
    quote = _normalized(risk.get("source_quote"))
    return (
        risk.get("source_quote_status") == "VERIFIED"
        and bool(quote)
        and quote in _normalized(source)
    )


def _source_marker_matches(marker: str, quote: str) -> bool:
    """Match literal oracle anchors; '...' is an ordered omission, not source text.

    The synthetic EPC-05 oracle abbreviates its expected quotation with '...'.
    Reject reordered or missing anchors rather than matching the punctuation
    literally or accepting a paraphrase as a grounded source quotation.
    """
    normalized_marker = _normalized(marker).replace("…", "...")
    normalized_quote = _normalized(quote)
    parts = [part.strip() for part in normalized_marker.split("...")]
    if any(not part for part in parts):
        return False
    offset = 0
    for part in parts:
        index = normalized_quote.find(part, offset)
        if index < 0:
            return False
        offset = index + len(part)
    return bool(parts)


def score_n4(fixture: dict[str, Any], risks: list[dict[str, Any]]) -> dict[str, Any]:
    """Score emitted N4 risks against independently authored fixture evidence."""
    source = _source_text(fixture)
    expected = fixture["n4_oracle"]["expected_risks"]
    valid = [_valid_quote(risk, source) for risk in risks]
    consumed: set[int] = set()
    cases: list[dict[str, Any]] = []

    for item in expected:
        marker = _normalized(item["citation_must_include"])
        expected_category = _normalized(item["category"])
        matched_index = next(
            (
                index
                for index, risk in enumerate(risks)
                if index not in consumed
                and valid[index]
                and _normalized(risk.get("category")) == expected_category
                and _source_marker_matches(marker, str(risk.get("source_quote") or ""))
            ),
            None,
        )
        if matched_index is not None:
            consumed.add(matched_index)
        cases.append(
            {
                "clause_id": item["clause_id"],
                "expected_category": item["category"],
                "extracted": matched_index is not None,
                "citation_valid": bool(matched_index is not None and valid[matched_index]),
            }
        )

    return {
        "expected_risks": len(expected),
        "emitted_risks": len(risks),
        "true_positives": len(consumed),
        "omissions": len(expected) - len(consumed),
        "false_positives": len(risks) - len(consumed),
        "valid_citations": sum(valid),
        "invalid_citations": len(risks) - sum(valid),
        "cases": cases,
    }


def score_n12(notes: str, source: str | None = None) -> dict[str, Any]:
    """Score only the three deliberately injected N12 failures."""
    normalized_notes = _normalized(notes)
    omission_detection = {
        "EPC-04": "epc-04" in normalized_notes and any(
            term in normalized_notes for term in ("defect", "rectif", "cure")
        ),
        "EPC-07": "epc-07" in normalized_notes and any(
            term in normalized_notes for term in ("liability", "indemn", "cap")
        ),
    }
    wrong_interpretation = (
        "epc-05" in normalized_notes
        and any(
            term in normalized_notes
            for term in (
                "wrong",
                "incorrect",
                "not force majeure",
                "not a force majeure",
                "excluded",
                "exclusion",
                "not covered",
                "does not qualify",
            )
        )
        and any(term in normalized_notes for term in ("financing", "currency", "fluctuation"))
    )
    cited_clause_ids = [
        clause_id
        for clause_id in (*EXPECTED_OMISSIONS, FALSE_INTERPRETATION_CLAUSE)
        if clause_id.lower() in normalized_notes
    ]
    quoted_fragments = re.findall(r'["“]([^"”]{12,})["”]', notes)
    valid_quoted_fragments = (
        [fragment for fragment in quoted_fragments if _normalized(fragment) in _normalized(source)]
        if source is not None
        else []
    )
    return {
        "omissions_expected": 2,
        "omissions_detected": sum(omission_detection.values()),
        "omission_cases": omission_detection,
        "incorrect_interpretation_expected": 1,
        "incorrect_interpretation_detected": wrong_interpretation,
        "critique_citation_clause_refs": cited_clause_ids,
        "critique_quoted_citations": len(quoted_fragments),
        "critique_valid_quoted_citations": len(valid_quoted_fragments),
        "critique_citation_validity": bool(valid_quoted_fragments) if source is not None else None,
    }


def _adversarial_risks(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    clauses = {entry["id"]: entry["text"] for entry in fixture["contract"]["clauses"]}
    risks = []
    for expected in fixture["n4_oracle"]["expected_risks"]:
        if expected["clause_id"] in EXPECTED_OMISSIONS:
            continue
        risks.append(
            {
                "title": expected["risk"],
                "description": expected["risk"],
                "category": expected["category"],
                "severity": "HIGH",
                "likelihood": "MEDIUM",
                "clause_ref": expected["clause_id"],
                "source_quote": clauses[expected["clause_id"]],
                "source_quote_status": "VERIFIED",
            }
        )
    risks.append(
        {
            "title": "Force Majeure financial hardship relief",
            "description": "EPC-05 provides time relief for financial hardship and currency fluctuation.",
            "category": "LEGAL",
            "severity": "HIGH",
            "likelihood": "MEDIUM",
            "clause_ref": FALSE_INTERPRETATION_CLAUSE,
            "source_quote": clauses[FALSE_INTERPRETATION_CLAUSE],
            "source_quote_status": "VERIFIED",
        }
    )
    return risks


def _governor_summary() -> dict[str, Any]:
    ledger_path = os.environ.get("C2PRO_AI_GOVERNOR_LEDGER")
    if not ledger_path:
        return {"available": False}
    path = Path(ledger_path)
    if not path.exists():
        return {"available": False}
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    completed = [event for event in events if event.get("ev") == "done"]
    return {
        "available": True,
        "calls": len([event for event in events if event.get("ev") == "reserve"]),
        "completed_calls": len(completed),
        "models": sorted({str(event.get("model")) for event in completed}),
        "input_tokens": sum(int(event.get("in", 0)) for event in completed),
        "output_tokens": sum(int(event.get("out", 0)) for event in completed),
        "estimated_cost_usd": round(sum(float(event.get("usd", 0.0)) for event in completed), 6),
        "refusals": len([event for event in events if event.get("ev") == "refused"]),
    }


async def run() -> dict[str, Any]:
    if str(os.getenv("C2PRO_AI_MOCK", "")).strip() != "0":
        raise RuntimeError("REAL_AI_REQUIRED: C2PRO_AI_MOCK must be 0")
    fixture = load_fixture()
    source = _source_text(fixture)
    if str(API_ROOT) not in sys.path:
        sys.path.insert(0, str(API_ROOT))

    # Importing the real N4 implementation registers its tool; the runner then
    # constructs its normal no-cache/no-retry wrapper explicitly. This avoids
    # the graph's singleton default, whose production retry policy is unsafe
    # for this bounded, paid experiment.
    from src.analysis.adapters.ai.tools.risk_extraction_tool import (
        RiskExtractionInput,
        RiskExtractionTool,
    )
    from src.analysis.adapters.graph.nodes import _risk_contract_payload
    from src.analysis.application.critique_extraction_use_case import (
        CritiqueExtractionCommand,
        CritiqueExtractionUseCase,
    )
    from src.core.ai.anthropic_wrapper import AIRequest, AnthropicWrapper
    from src.core.ai.model_router import AITaskType

    wrapper = AnthropicWrapper(enable_cache=False, enable_retry=False, max_tokens_limit=4096)
    n4_tool = RiskExtractionTool(anthropic_wrapper=wrapper)
    n4_result = await n4_tool.execute(
        RiskExtractionInput(document_text=source, max_risks=20), low_budget_mode=True
    )
    if not n4_result.success:
        raise RuntimeError(f"N4_REAL_EXECUTION_FAILED: {n4_result.error or n4_result.status}")
    extracted_risks = [
        _risk_contract_payload(n4_tool._risk_item_to_dict(risk), source)
        for risk in (n4_result.data or [])
    ]
    n4_metrics = score_n4(fixture, extracted_risks)

    class _RealNoRetryPort:
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
            return json.loads(response.content)

    n12_result = await CritiqueExtractionUseCase(ai=_RealNoRetryPort()).execute(
        CritiqueExtractionCommand(
            extracted_risks=_adversarial_risks(fixture),
            extracted_wbs=[],
            doc_type="contract",
            retry_count=0,
            source_text=source,
        )
    )
    n12_notes = n12_result.critique_notes
    n12_metrics = score_n12(n12_notes, source)

    return {
        "fixture_id": fixture["fixture_id"],
        "fixture_sha256": FIXTURE_SHA256,
        "provider_call": "real",
        "ai_mock": False,
        "n4": n4_metrics,
        "n12": {
            **n12_metrics,
            "status": n12_result.status,
            "notes_sha256": hashlib.sha256(n12_notes.encode("utf-8")).hexdigest(),
        },
        "provider": _governor_summary(),
        "errors": [],
    }


def main() -> int:
    result = asyncio.run(run())
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"fixture_id": result["fixture_id"], "provider": result["provider"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
