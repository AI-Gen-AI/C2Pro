"""Experimental B0 bridge: Docling structural evidence -> current N4 windows.

This is a pure, dependency-injected adapter: it calls the existing
plan_n4_source_windows implementation supplied by the caller. It never
calls a model or fabricates N12 original-source attestation. Critically,
a non-identity N2 redaction is BLOCKED unless separately mapped to source
offsets. Do not wire this into live N4 pilot without current-SHA QA.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Callable

from src.documents.adapters.parsers.docling_contract_window_packet import (
    ContractWindowError, _text_segments,
)


class DocumentN4BridgeError(ValueError):
    """Source projection or window locator could not be safely grounded."""


@dataclass(frozen=True)
class N4EvidenceSpan:
    locator: str
    kind: str
    start: int
    end: int
    pages: tuple[int, ...]


def project_docling_to_existing_n4(
    docling_candidate: dict[str, Any],
    *,
    n2_safe_projection: str,
    window_planner: Callable[..., Any],
    max_context_chars: int = 12_000,
    overlap_chars: int = 400,
) -> dict[str, Any]:
    """Make a projection + source-offset map for the existing N4 planner.

    Fails closed when N2 has redacted or otherwise changed the source
    projection: an original->redacted offset mapping is still missing.
    """
    if docling_candidate.get("state") != "CANDIDATE_UNVALIDATED":
        raise DocumentN4BridgeError("untrusted candidate required")
    if docling_candidate.get("trusted_promotions") != 0 or docling_candidate.get("effects_allowed") is not False:
        raise DocumentN4BridgeError("unsafe candidate authority")
    if not docling_candidate.get("coverage", {}).get("docling_layout_sequence_available"):
        raise DocumentN4BridgeError("Docling reading order incomplete")
    try:
        segments = _text_segments(docling_candidate)
    except (ContractWindowError, KeyError, TypeError) as exc:
        raise DocumentN4BridgeError(f"unusable Docling source layout ({type(exc).__name__})") from None
    if not segments:
        raise DocumentN4BridgeError("no source text available")

    text_parts: list[str] = []
    spans: list[N4EvidenceSpan] = []
    cursor = 0
    for index, segment in enumerate(segments):
        if index:
            text_parts.append("\n\n")
            cursor += 2
        body = segment["text"]
        if not body:
            raise DocumentN4BridgeError("empty source segment")
        start = cursor
        cursor += len(body)
        text_parts.append(body)
        spans.append(N4EvidenceSpan(
            locator=segment["source_locator"],
            kind=segment["kind"],
            start=start,
            end=cursor,
            pages=tuple(segment["pages"]),
        ))
    projection = "".join(text_parts)
    if not projection or not isinstance(n2_safe_projection, str):
        raise DocumentN4BridgeError("model-safe N2 source projection required")
    if n2_safe_projection != projection:
        # N2 PII anonymization may change offsets; never assert PDF page
        # provenance with the old offsets after a changed projection.
        raise DocumentN4BridgeError("N2 projection changed; original-to-redacted offset map required")
    sha = hashlib.sha256(projection.encode("utf-8")).hexdigest()
    revision_id = docling_candidate.get("scope", {}).get("revision_id")
    windows = window_planner(
        projection,
        revision_id=revision_id,
        max_context_chars=max_context_chars,
        overlap_chars=overlap_chars,
    )
    if not windows:
        raise DocumentN4BridgeError("existing N4 window planner returned no windows")
    if "".join(w.core_text for w in windows) != projection:
        raise DocumentN4BridgeError("N4 window core inventory is not lossless")
    if any(w.source_sha256 != sha for w in windows):
        raise DocumentN4BridgeError("N4 source SHA does not match projection")

    result_windows = []
    for w in windows:
        overlap = []
        for span in spans:
            # Page/locator candidates for the CORE portion are kept separate
            # from context overlap. This prevents treating overlap as fresh
            # evidence and accidentally double-counting sources.
            a = max(span.start, w.core_start)
            b = min(span.end, w.core_end)
            if a < b:
                overlap.append({
                    "source_locator": span.locator,
                    "kind": span.kind,
                    "global_start": a,
                    "global_end": b,
                    "source_start": a - span.start,
                    "source_end": b - span.start,
                    "pages": list(span.pages),
                    "page_anchor_verified_against_original": False,
                })
        result_windows.append({
            "ordinal": w.ordinal,
            "core_start": w.core_start,
            "core_end": w.core_end,
            "context_start": w.context_start,
            "context_end": w.context_end,
            "context_sha256": w.context_sha256,
            "core_evidence": overlap,
            "status": "PLANNED_UNEXAMINED",
        })
    return {
        "scope": docling_candidate["scope"],
        "physical_pdf_sha256": docling_candidate["source"]["sha256"],
        "n4_model_text_sha256": sha,
        "n2_projection_identity_proven": True,
        "state": "CANDIDATE_UNVALIDATED",
        "n4_executed": False,
        "n12_source_attestation": None,
        "original_pdf_page_attestation": "UNVERIFIED",
        "trusted_promotions": 0,
        "coverage": {
            "source_segments": len(spans),
            "source_chars": len(projection),
            "core_chars": sum(w.core_end - w.core_start for w in windows),
            "window_count": len(windows),
            "unanchored_segments": sum(not s.pages for s in spans),
            "all_referenced_annexes_verified": False,
        },
        "window_evidence_map": result_windows,
        # Returned only to the authorized in-process N2/N4 planner; never
        # persist or log this on an untrusted host.
        "model_safe_text": projection,
    }
