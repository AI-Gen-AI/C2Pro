"""B1b: Validate external agent-produced JSON through N4 V2 candidate schema.

One PUBLIC SEC EPC clause only. This script never calls a model itself.
It uses exact current N4 source-window plan and N4 v2 candidate parser.
The raw generative output is in a local lab, never in a public Git repo.
Results are statistics/flags only, not source text or model-written claims.

Experimental inference is via a Gemini review worker, NOT the production
N4 provider, not LangExtract, not a model-to-model fair benchmark.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.analysis.domain.n4_typed_fact_v2_candidate import (
    parse_n4_typed_fact_candidate_response,
)

CLAUSE_PREFIX = "2.5.5 Liquidated Damages for Delay."


def validate(full_text: str, provider_json: dict) -> dict:
    index = full_text.find(CLAUSE_PREFIX)
    if index < 0:
        raise ValueError("pinned public clause missing from source")
    windows = plan_n4_source_windows(
        full_text,revision_id="SEC_PUBLIC_DERIVATIVE_UNATTESTED",
        max_context_chars=12000,overlap_chars=400,
    )
    selected = next((w for w in windows if w.core_start <= index < w.core_end),None)
    if selected is None:
        raise ValueError("source clause outside N4 inventory")
    parsed = parse_n4_typed_fact_candidate_response(provider_json,window=selected)
    verified = []
    for f in parsed.candidate_facts:
        evidence = f["evidence"]
        span = evidence["analysis_span"]
        valid_span = bool(
            span is not None and
            full_text[span[0]:span[1]] == f["verbatim_quote"]
        )
        verified.append({
            "type": f["entity_type"],
            "dimensions": list(f["dimensions"]),
            "status": evidence["evidence_status"],
            "valid_global_source_span": valid_span,
            "has_quote":f["verbatim_quote"] is not None,
        })
    return {
        "status":"PASS_LIMITED_MODEL_OUTPUT_VALIDATED" if all(x["valid_global_source_span"] for x in verified) else "MIXED_SOURCE_ANCHORS",
        "source_provenance":"SEC HTML locally printed to PDF; N2 original-source attestation absent",
        "model_executed":True,
        "model_runner":"AI-GEN Ops Gemini agent, NOT N4 or LangExtract provider",
        "model_provider_and_cost_verified":False,
        "n4_v2_schema_parsed":True,
        "source_sha256":hashlib.sha256(full_text.encode()).hexdigest(),
        "source_window_ordinal":selected.ordinal,
        "window_count":len(windows),
        "model_proposed_count":len(verified),
        "source_exact_candidate_count":sum(x["valid_global_source_span"] for x in verified),
        "source_unverified_count":sum(not x["valid_global_source_span"] for x in verified),
        "entity_type_counts":{k:sum(x["type"]==k for x in verified) for k in sorted({x["type"] for x in verified})},
        "has_explicit_obligation_fact":any(x["type"]=="obligation" for x in verified),
        "source_contains_explicit_pay_obligation":"Contractor shall pay to Owner" in selected.context_text,
        "reviewer_note":"A condition statement mentioning duty to pay is NOT the same as an independently typed obligation fact",
        "model_self_reported_examined":parsed.self_reported_examined,
        "source_coverage_state":parsed.source_coverage_state,
        "unresolved_refs_count":len(parsed.outstanding_references),
        "unresolved_reference_flags":["EXHIBIT_C_TABLE_C1" if "Table C-1" in x else "UNSPECIFIED" for x in parsed.outstanding_references],
        "facts":verified,
        "n12_status":parsed.n12_status,
        "trusted_promotions":parsed.trusted_promotions,
        "not_validated":["human expert adjudication","legal risk recall","all annexes","original page citations","N4 runner","N12","ProjectGraph","cost/latency"],
    }


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--text",type=Path,required=True)
    p.add_argument("--model-json",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    model=json.loads(args.model_json.read_text(encoding="utf-8"))
    report=validate(args.text.read_text(encoding="utf-8"),model)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
