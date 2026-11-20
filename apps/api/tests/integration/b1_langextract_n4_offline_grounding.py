"""B1a: offline real-package comparison of N4 and LangExtract quote grounding.

Requires (a) local, public-source legacy PDF text projection and (b) the
EXACT current N4 plan+compact window parser. The benchmark DOES NOT run
an LLM or judge semantic quality/recall. It probes positions and failures
using the same predefined literal probes and model-safe source windows.
Public result: metrics only; no source text, excerpts or private artifacts.

LangExtract v1.7.1: Resolver.align(extractions, source_text, token_offset=0,
char_offset=...); exact-only is used for any credible literal citation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from langextract import resolver
from langextract.core import data
from src.analysis.domain.n4_compact_window_response import parse_n4_window_output
from src.analysis.domain.n4_source_windows import plan_n4_source_windows

MARKERS = {
    "2_5_5": r"2\s*\.\s*5\s*\.\s*5",
    "9_6": r"\b9\s*\.\s*6\b",
    "4_3_1": r"\b4\s*\.\s*3\s*\.\s*1",
    "article_13": r"\b(?:ARTICLE\s+)?13\s*[.:\-]",
}
MAX_SAFE_QUOTE_CHARS = 95


def make_probes(text: str, windows: tuple) -> list[dict]:
    probes = []
    for label, pat in MARKERS.items():
        occurrences = list(re.finditer(pat, text, flags=re.I))
        for m in occurrences:
            w = next((w for w in windows if w.core_start <= m.start() < w.core_end), None)
            if not w:
                continue
            # Select a contiguous quote entirely inside the core span.
            start = m.start()
            stop = min(start + MAX_SAFE_QUOTE_CHARS, w.core_end)
            # A LangExtract token aligner cannot anchor half of a word.
            # Use complete-word literal quotes for a fair N4/LX comparison.
            raw = text[start:stop]
            boundary = max(raw.rfind(" "), raw.rfind("\n"), raw.rfind("\t"))
            quote = raw[:boundary].strip() if boundary >= 40 else raw.strip()
            if len(quote) < 30:
                continue
            if w.context_text.count(quote) != 1:
                continue
            probes.append({"clause":label, "ordinal":w.ordinal,
                           "source_start":text.find(quote,start,w.core_end),
                           "quote":quote})
            break
    return probes


def n4_match(window, quote: str) -> tuple[str, tuple | None]:
    raw = {
      "window_examined":True,
      "findings":[{"title":"Literal grounding probe","category":"contractual",
                   "risk_reason":"Synthetic candidate: NOT a legal risk finding",
                   "source_quote":quote,"clause_ref":None,"impact":None}],
      "outstanding_references":[],
    }
    item=parse_n4_window_output(raw,window=window).proposed_findings[0]
    source=item["source_refs"][0]
    return source["evidence_status"], tuple(source["analysis_span"]) if source["analysis_span"] else None


def langextract_match(window, quote: str, *, fuzzy: bool) -> tuple[str, tuple | None, bool]:
    extraction=data.Extraction(extraction_class="source_literal",
                               extraction_text=quote)
    items=list(resolver.Resolver().align([extraction],
          source_text=window.context_text,token_offset=0,
          char_offset=window.context_start,
          enable_fuzzy_alignment=fuzzy,
          accept_match_lesser=fuzzy))
    if not items:
        return "NOT_RETURNED",None,False
    result=items[0]
    ci=result.char_interval
    position=(ci.start_pos,ci.end_pos) if ci and ci.start_pos is not None else None
    exact=(bool(position) and
           window.context_text[position[0]-window.context_start:position[1]-window.context_start] == quote)
    return str(result.alignment_status),position,exact


def run(source_text: str, *, revision_id="b1-public-pdf-only") -> dict:
    windows=plan_n4_source_windows(source_text,revision_id=revision_id,
                                   max_context_chars=12000,overlap_chars=400)
    samples=make_probes(source_text,windows)
    if len(samples)<2:
        raise ValueError("At least two suitable literal source probes required")
    window_by_id={w.ordinal:w for w in windows}
    cases=[]
    for sample in samples:
        window=window_by_id[sample["ordinal"]]
        quote=sample["quote"]
        # Neither changes the underlying public source; these are controlled
        # candidate outputs to test false-positive/ambiguous alignment.
        changed=quote[:max(2,len(quote)//2)]+"[PARAPHRASED]"+quote[max(2,len(quote)//2)+5:]
        variants=[
            ("exact",quote),
            ("altered",changed),
            ("invented","CONTRACT EXPLICITLY CANCELS ALL RISKS IN PROJECT XQZ-998"),
        ]
        for kind,reported in variants:
            n4_status,n4_range=n4_match(window,reported)
            lx_status,lx_range,lx_exact=langextract_match(window,reported,fuzzy=False)
            fuzzy_status,fuzzy_range,fuzzy_exact=langextract_match(window,reported,fuzzy=True)
            expected=(sample["source_start"],sample["source_start"]+len(quote)) if kind=="exact" else None
            cases.append({
                "clause":sample["clause"],
                "variant":kind,"window_ordinal":window.ordinal,
                "n4_status":n4_status,
                "n4_range_exact":bool(expected and n4_range==expected),
                "n4_range_reported":n4_range is not None,
                "langextract_exact_status":lx_status,
                "langextract_exact_range_correct":bool(expected and lx_range==expected),
                "langextract_exact_span_is_verbatim":lx_exact,
                "langextract_fuzzy_status":fuzzy_status,
                "langextract_fuzzy_range_reported":fuzzy_range is not None,
                "langextract_fuzzy_span_is_verbatim":fuzzy_exact,
                "original_quote_chars":len(quote),
            })

    stats={}
    for variant in ("exact","altered","invented"):
        subset=[v for v in cases if v["variant"]==variant]
        stats[variant]={
            "count":len(subset),
            "n4_spans_reported":sum(v["n4_range_reported"] for v in subset),
            "n4_exact_expected_locations":sum(v["n4_range_exact"] for v in subset),
            "langextract_exact_spans_verbatim":sum(v["langextract_exact_span_is_verbatim"] for v in subset),
            "langextract_exact_expected_locations":sum(v["langextract_exact_range_correct"] for v in subset),
            "langextract_fuzzy_spans_reported":sum(v["langextract_fuzzy_range_reported"] for v in subset),
            "langextract_fuzzy_verbatim_citations":sum(v["langextract_fuzzy_span_is_verbatim"] for v in subset),
            "langextract_fuzzy_alignment_statuses":dict(Counter(
                v["langextract_fuzzy_status"] for v in subset)),
        }
    return {
        "status":"PASS_LIMITED_OFFLINE_ALIGNMENT_ONLY",
        "source_origin":"SEC public EPC contract PDF locally rendered from HTML",
        "baseline_parser":"C2Pro PDFFileParser",
        "n4_source_code_sha":"916808c5212e3dbc652407f35f3a17557623c06c",
        "langextract_version":"1.7.1",
        "source_sha256":hashlib.sha256(source_text.encode()).hexdigest(),
        "source_chars":len(source_text),
        "source_windows":len(windows),
        "candidate_output_count":len(cases),
        "oracle_type":"SEEDED_LITERAL_SOURCE_SPANS_NOT_SEMANTIC_ORACLE",
        "no_llm_invoked":True,
        "source_coverage_executed":False,
        "semantic_obligations_risks_evaluated":False,
        "summary":stats,
        "cases":cases,
        "limitations":[
          "Injected candidate source quotes, not LLM-generated obligations or risk findings",
          "Exact character-source matches do not attest to original physical PDF page or legal meaning",
          "LangExtract fuzzy alignment can anchor a modified string; never label it verbatim",
          "No independent human EPC oracle, provider spend or model quality comparison",
          "The SEC HTML-derived PDF's pagination is only local rendering",
        ],
    }


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--text-file",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    doc=args.text_file.read_text(encoding="utf-8")
    report=run(doc)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"source_windows":report["source_windows"],
                      "source_chars":report["source_chars"],"summary":report["summary"]},
                     ensure_ascii=False))
