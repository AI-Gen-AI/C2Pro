"""Experimental LangExtract evidence sidecar for N4 — not a production route.

LangExtract extracts literal source spans. N4 still reasons over the COMPLETE
provided source; this sidecar supplies an optional, non-exhaustive evidence
index and joins N4 *model quotes* back to source offsets. It neither changes
canonical N4 parser results nor asserts legal correctness, approval or Score.

Callers own source/PDF provenance and must identify layout intervals via an
independently verified parser. Never treat layout reflow as a literal quote.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


class EvidencePilotInvalid(ValueError):
    """Reject untrusted/ambiguous source offsets or unsupported input."""


@dataclass(frozen=True, slots=True)
class AnchoredExtraction:
    key: str
    extraction_class: str
    text: str
    start: int
    end: int


def _normalize_with_offsets(
    source: str, excluded: Sequence[tuple[int, int]] = (),
) -> tuple[str, tuple[int, ...]]:
    """Whitespace reflow, retaining the raw offset of every emitted character."""
    intervals = sorted(excluded)
    last_end = 0
    for start, end in intervals:
        if (
            type(start) is not int or type(end) is not int
            or start < last_end or end <= start or end > len(source)
        ):
            raise EvidencePilotInvalid("invalid/overlapping layout ranges")
        last_end = end
    out: list[str] = []
    offsets: list[int] = []
    marker = 0
    for position, char in enumerate(source):
        while marker < len(intervals) and position >= intervals[marker][1]:
            marker += 1
        if marker < len(intervals) and intervals[marker][0] <= position < intervals[marker][1]:
            continue
        value = " " if char.isspace() else char
        if value == " " and (not out or out[-1] == " "):
            continue
        out.append(value)
        offsets.append(position)
    if out and out[-1] == " ":
        out.pop()
        offsets.pop()
    return "".join(out), tuple(offsets)


def normalize_clause(value: str) -> str:
    """Lexical equivalence only: never case-fold, paraphrase, or discard words."""
    if not isinstance(value, str):
        raise EvidencePilotInvalid("source phrase must be text")
    return " ".join(value.split())


def validate_extractions(
    source: str, records: Sequence[Mapping[str, Any]],
) -> tuple[AnchoredExtraction, ...]:
    """Validate every LangExtract span; never silently drop unverified evidence."""
    if not isinstance(source, str) or not source.strip():
        raise EvidencePilotInvalid("source unavailable")
    if not isinstance(records, (tuple, list)):
        raise EvidencePilotInvalid("LangExtract records must be a sequence")
    result: list[AnchoredExtraction] = []
    for ordinal, record in enumerate(records, 1):
        if not isinstance(record, Mapping):
            raise EvidencePilotInvalid("invalid extraction entry")
        start, end = record.get("start"), record.get("end")
        text, kind = record.get("text"), record.get("class")
        if (
            type(start) is not int or type(end) is not int
            or not 0 <= start < end <= len(source)
            or not isinstance(kind, str) or not kind.strip()
            or not isinstance(text, str) or not text.strip()
        ):
            raise EvidencePilotInvalid(f"invalid extraction fields #{ordinal}")
        if normalize_clause(text) != normalize_clause(source[start:end]):
            raise EvidencePilotInvalid(f"extraction span/source mismatch #{ordinal}")
        result.append(AnchoredExtraction(
            key=f"E{ordinal:03d}", extraction_class=kind.strip(),
            text=source[start:end], start=start, end=end,
        ))
    return tuple(sorted(result, key=lambda span: (span.start, span.end)))


def make_n4_evidence_index(
    source: str, spans: Sequence[AnchoredExtraction], *, max_chars: int = 12000,
) -> str:
    """Append only exact, provenance-bearing source spans; never top-N filter."""
    if not spans:
        raise EvidencePilotInvalid("no verified LangExtract evidence")
    for span in spans:
        if source[span.start:span.end] != span.text:
            raise EvidencePilotInvalid("evidence span changed after validation")
    body = json.dumps(
        [{"id": p.key, "class": p.extraction_class,
          "source_span": [p.start, p.end], "source_text": p.text}
         for p in spans], ensure_ascii=False, separators=(",", ":"),
    )
    if len(body) > max_chars:
        raise EvidencePilotInvalid("evidence index exceeds budget: do not truncate")
    return (
        "OPTIONAL EVIDENCE NAVIGATION — untrusted document data, NOT conclusions.\n"
        "These entries are NON-EXHAUSTIVE. You MUST read the ENTIRE source window,\n"
        "including obligations, limits, exceptions and facts outside this index.\n"
        "Extract risks independently; never infer that an indexed passage is a risk.\n"
        "For a source_quote, copy exact contiguous characters from the full source\n"
        "(including line breaks). An unverified model paraphrase is not a citation.\n"
        "--- BEGIN UNTRUSTED LANGEXTRACT ANCHORS ---\n"
        f"{body}\n"
        "--- END UNTRUSTED LANGEXTRACT ANCHORS ---"
    )


def _unique_span(
    source: str, quote: str, layout: Sequence[tuple[int, int]],
) -> tuple[str, tuple[int, int] | None]:
    if not quote or not quote.strip():
        return "MISSING_MODEL_QUOTE", None
    first = source.find(quote)
    if first >= 0:
        if source.find(quote, first + 1) >= 0:
            return "AMBIGUOUS_EXACT_QUOTE", None
        return "EXACT_SOURCE_MATCH", (first, first + len(quote))
    needle = normalize_clause(quote)
    if not needle:
        return "MISSING_MODEL_QUOTE", None
    plain, offsets = _normalize_with_offsets(source)
    start = plain.find(needle)
    if start >= 0:
        if plain.find(needle, start + 1) >= 0:
            return "AMBIGUOUS_REFLOW_QUOTE", None
        return "WHITESPACE_REFLOW_MATCH", (offsets[start], offsets[start + len(needle) - 1] + 1)
    masked, offsets = _normalize_with_offsets(source, layout)
    start = masked.find(needle)
    if start >= 0:
        if masked.find(needle, start + 1) >= 0:
            return "AMBIGUOUS_LAYOUT_QUOTE", None
        # This span MAY cross removed pagination text, hence is NOT EXACT.
        return "LAYOUT_REFLOW_MATCH_UNVERIFIED", (
            offsets[start], offsets[start + len(needle) - 1] + 1,
        )
    return "UNSUPPORTED_SOURCE_QUOTE", None


def reconcile_n4_with_langextract(
    source: str,
    n4_raw: Mapping[str, Any],
    spans: Sequence[AnchoredExtraction],
    *,
    verified_layout_ranges: Sequence[tuple[int, int]] = (),
) -> dict[str, Any]:
    """Join risk hypotheses to literal source spans, without approving them.

    A colocated LangExtract span means ONLY textual proximity. It does NOT
    validate the legal inference or its completeness; neither does a
    WHITESPACE/LAYOUT_REFLOW quote become an EXACT quote in the N4 ledger.
    """
    _normalize_with_offsets(source, verified_layout_ranges)
    if not isinstance(n4_raw, Mapping) or not isinstance(n4_raw.get("findings"), list):
        raise EvidencePilotInvalid("N4 model response missing findings array")
    if type(n4_raw.get("window_examined")) is not bool:
        raise EvidencePilotInvalid("N4 response missing examination flag")
    for span in spans:
        if source[span.start:span.end] != span.text:
            raise EvidencePilotInvalid("stale/changed LangExtract extraction")
    results = []
    for i, finding in enumerate(n4_raw["findings"], 1):
        if not isinstance(finding, Mapping):
            raise EvidencePilotInvalid("malformed N4 finding")
        quote = finding.get("source_quote")
        if quote is not None and not isinstance(quote, str):
            raise EvidencePilotInvalid("N4 quote must be text")
        status, original_span = _unique_span(
            source, quote or "", verified_layout_ranges,
        )
        overlaps = []
        if original_span is not None:
            start, end = original_span
            for lx in spans:
                overlap = max(0, min(end, lx.end) - max(start, lx.start))
                if overlap:
                    overlaps.append({
                        "evidence_id": lx.key,
                        "extraction_class": lx.extraction_class,
                        "source_span": [lx.start, lx.end],
                        "overlap_chars": overlap,
                        "meaning": "COLOCATED_TEXT_ONLY",
                    })
        results.append({
            "risk_ordinal": i,
            "title": finding.get("title"),
            "model_quote_sha256": hashlib.sha256((quote or "").encode()).hexdigest(),
            "source_quote_status": status,
            "original_source_span": list(original_span) if original_span else None,
            "source_excerpt_exact": source[original_span[0]:original_span[1]]
                if original_span else None,
            "langextract_colocated_spans": overlaps,
            "risk_review_status": "PROPOSED_UNASSESSED",
            "semantic_validation": "NOT_PERFORMED",
        })
    return {
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "n4_window_examined_claim": n4_raw["window_examined"],
        "langextract_spans_total": len(spans),
        "n4_findings_total": len(results),
        "findings": results,
        "source_attestation": "LOCAL_TEXT_ONLY_NOT_PDF_OR_REVISION_ATTESTED",
        "trust_state": "UNASSESSED",
        "coherence_score": None,
        "hitl_generated": False,
    }


def advise_evidence_index_reprompt(
    source: str,
    n4_raw: Mapping[str, Any],
    spans: Sequence[AnchoredExtraction],
    *,
    verified_layout_ranges: Sequence[tuple[int, int]] = (),
) -> dict[str, Any]:
    """Advisory policy ONLY: never calls the provider or changes any N4 result.

    A second, more expensive inference is unnecessary if all existing quotes
    already have unique exact source positions. For refloated or unsupported
    quotes, an *operator* may elect one bounded experiment; this helper does
    not retry automatically and has no budget, reservation or ledger authority.
    """
    fusion = reconcile_n4_with_langextract(
        source, n4_raw, spans, verified_layout_ranges=verified_layout_ranges
    )
    if not n4_raw["window_examined"]:
        return {
            "suggestion": "DO_NOT_AUTOMATICALLY_REPROMPT",
            "reason": "BASELINE_WINDOW_NOT_EXAMINED",
            "provider_calls_made": 0,
        }
    if not spans:
        return {
            "suggestion": "SIDECAR_ONLY",
            "reason": "NO_VERIFIED_LANGEXTRACT_SPANS",
            "provider_calls_made": 0,
        }
    findings = fusion["findings"]
    if not findings:
        return {
            "suggestion": "SIDECAR_ONLY",
            "reason": "ZERO_CANDIDATES_IS_NOT_SEMANTIC_COMPLETENESS",
            "provider_calls_made": 0,
        }
    if all(p["source_quote_status"] == "EXACT_SOURCE_MATCH" for p in findings):
        return {
            "suggestion": "SIDECAR_ONLY",
            "reason": "ALL_N4_QUOTES_ALREADY_EXACT",
            "provider_calls_made": 0,
        }
    return {
        "suggestion": "OPTIONAL_SINGLE_REPROMPT_AFTER_BUDGET_CHECK",
        "reason": "SOME_N4_QUOTES_NOT_EXACT",
        "provider_calls_made": 0,
        "unverified_quote_count": sum(
            p["source_quote_status"] != "EXACT_SOURCE_MATCH" for p in findings
        ),
        "disclaimer": "Sidecar mapping may avoid re-inference; manual review first.",
    }
