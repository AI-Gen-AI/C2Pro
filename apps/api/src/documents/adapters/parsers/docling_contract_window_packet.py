"""I-C02: exhaustive, source-anchored N4 *input proposal* from Docling items.

Does NOT call N4/N12 or assert original-PDF attestation. Preserves every
character from the Docling candidate strings in consecutive, bounded windows,
including table cells, and records what remains unanchored.
"""
from __future__ import annotations

import hashlib
from typing import Any


class ContractWindowError(ValueError):
    """A candidate packet could not be safely assembled."""


def _text_segments(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for obj in candidate.get("text_items", []):
        text = str(obj.get("content") or "")
        if text:
            items.append({
                "source_locator": obj["source_locator"],
                "text": text,
                "page": (obj.get("locations") or [{}])[0].get("page"),
                "kind": "text",
            })
    for obj in candidate.get("tables", []):
        # Table rows and columns stay available independently in candidate.
        # This text projection is for LLM context only, not a cell citation.
        cells = sorted(obj.get("cells") or [], key=lambda c: (
            c.get("row_start") if c.get("row_start") is not None else 999999,
            c.get("col_start") if c.get("col_start") is not None else 999999,
        ))
        text = " | ".join(str(x.get("text") or "") for x in cells)
        if text:
            items.append({
                "source_locator": obj["source_locator"],
                "text": text,
                "page": (obj.get("locations") or [{}])[0].get("page"),
                "kind": "table_projection",
            })
    return items


def build_untrusted_contract_windows(
    candidate: dict[str, Any], *, max_chars: int = 12_000
) -> dict[str, Any]:
    """Produce bounded consecutive windows without dropping parsed characters.

    Docling objects' reading order has NOT been independently attested.
    Window text is not an original PDF quotation/citation certificate.
    """
    if not isinstance(candidate, dict) or candidate.get("state") != "CANDIDATE_UNVALIDATED":
        raise ContractWindowError("untrusted Docling candidate required")
    if candidate.get("trusted_promotions") != 0 or candidate.get("effects_allowed") is not False:
        raise ContractWindowError("source packet has an unsafe authority state")
    source = candidate.get("source")
    if not isinstance(source, dict) or source.get("basis") != "PINNED_SOURCE_BYTES":
        raise ContractWindowError("source identity not pinned")
    if not isinstance(max_chars, int) or not (256 <= max_chars <= 40_000):
        raise ContractWindowError("invalid context window bound")

    segments = _text_segments(candidate)
    if not segments:
        raise ContractWindowError("no parsed Docling content")
    windows: list[dict[str, Any]] = []
    current = []
    used = 0
    covered_chars = 0
    unanchored = 0

    def flush() -> None:
        nonlocal current, used
        if not current:
            return
        windows.append({
            "window_index": len(windows),
            "parts": current,
            # Delimit different source items rather than silently concatenating
            # unrelated clauses or table contents.
            "text": "".join(part["separator_before"] + part["text"] for part in current),
            "state": "CANDIDATE_UNVALIDATED",
            "original_pdf_attestation": "UNVERIFIED",
        })
        current = []
        used = 0

    for segment in segments:
        text = segment["text"]
        if segment["page"] is None:
            unanchored += 1
        pos = 0
        while pos < len(text):
            left = max_chars - used
            separator = "\\n\\n" if current and current[-1]["source_locator"] != segment["source_locator"] else ""
            if left <= len(separator):
                flush()
                left = max_chars
                separator = ""
            end = min(len(text), pos + left - len(separator))
            piece = text[pos:end]
            current.append({
                "separator_before": separator,
                "source_locator": segment["source_locator"],
                "source_start": pos,
                "source_end": end,
                "page": segment["page"],
                "kind": segment["kind"],
                "text": piece,
                "is_split_segment": len(text) > max_chars or pos > 0 or end < len(text),
            })
            used += len(piece) + len(separator)
            covered_chars += len(piece)
            pos = end
            if used >= max_chars:
                flush()
    flush()

    original = sum(len(x["text"]) for x in segments)
    if original != covered_chars or any(len(w["text"]) > max_chars for w in windows):
        raise ContractWindowError("coverage conservation check failed")
    return {
        "scope": candidate["scope"],
        "source": source,
        "state": "CANDIDATE_UNVALIDATED",
        "original_pdf_attestation": "UNVERIFIED",
        "n12_source_attestation": None,
        "n4_executed": False,
        "n12_executed": False,
        "trusted_promotions": 0,
        "effects_allowed": False,
        "coverage": {
            "parsed_chars": original,
            "window_chars": covered_chars,
            "window_count": len(windows),
            "unanchored_segments": unanchored,
            "reading_order_verified": False,
            "all_referenced_annexes_present": False,
            "semantic_risk_recall_verified": False,
        },
        "windows": windows,
    }
