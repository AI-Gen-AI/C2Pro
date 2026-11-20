"""I-C02: reversible Docling -> N4 *candidate input* windows (not LLM).

Preserve Docling native layout ordering, 2D table rows and complete multi-page
provenance. No source window is approved, no original-PDF attestation is made.
Fail-closed for unknown layout or unbreakable source tokens.
"""
from __future__ import annotations

import re
from typing import Any


class ContractWindowError(ValueError):
    """Structural packet lacks sufficient grounded source to continue."""


def _text_segments(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}

    for item in candidate.get("text_items", []):
        body = str(item.get("content") or "")
        if not body:
            continue
        locations = item.get("locations") or []
        pages = sorted({x["page"] for x in locations if isinstance(x.get("page"), int)})
        locator = item["source_locator"]
        indexed[locator] = {
            "source_locator": locator, "text": body, "pages": pages, "kind": "text",
        }

    for table in candidate.get("tables", []):
        rows = table.get("rows")
        cols = table.get("columns")
        if not isinstance(rows, int) or rows <= 0 or not isinstance(cols, int) or cols <= 0:
            raise ContractWindowError("table dimensions unverified")
        cells = table.get("cells") or []
        matrix = [["" for _ in range(cols)] for _ in range(rows)]
        seen = set()
        for cell in cells:
            row, col = cell.get("row_start"), cell.get("col_start")
            if not isinstance(row, int) or not isinstance(col, int):
                raise ContractWindowError("table cell coordinates missing")
            if not (0 <= row < rows and 0 <= col < cols) or (row, col) in seen:
                raise ContractWindowError("table cell coordinates ambiguous")
            seen.add((row, col))
            matrix[row][col] = str(cell.get("text") or "").replace("\n", " ")
        # Keep row boundaries explicit: single-line flattening loses the
        # meaning of deadlines, price/currency, conditions and WBS tables.
        body = "\n".join(" | ".join(row) for row in matrix)
        if not body.strip():
            continue
        locations = table.get("locations") or []
        pages = sorted({x["page"] for x in locations if isinstance(x.get("page"), int)})
        locator = table["source_locator"]
        indexed[locator] = {
            "source_locator": locator, "text": body, "pages": pages,
            "kind": "table_projection",
        }

    reading_order = candidate.get("reading_order")
    if not isinstance(reading_order, list) or set(reading_order) != set(indexed):
        raise ContractWindowError("native Docling reading order unavailable or incomplete")
    if len(reading_order) != len(set(reading_order)):
        raise ContractWindowError("Docling reading order contains duplicates")
    return [indexed[locator] for locator in reading_order]


def build_untrusted_contract_windows(
    candidate: dict[str, Any], *, max_chars: int = 12_000
) -> dict[str, Any]:
    """Create consecutive chunks with no omitted parsed source characters.

    The reader's order is Docling's model output; NOT a verified original-PDF
    layout certificate. A very long unbreakable token raises an honest blocker
    rather than splitting a monetary figure or identifying code silently.
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
    current: list[dict[str, Any]] = []
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
            "text": "".join(part["separator_before"] + part["text"] for part in current),
            "state": "CANDIDATE_UNVALIDATED",
            "original_pdf_attestation": "UNVERIFIED",
        })
        current = []
        used = 0

    for segment in segments:
        body = segment["text"]
        if not segment["pages"]:
            unanchored += 1
        position = 0
        while position < len(body):
            separator = "\n\n" if current and current[-1]["source_locator"] != segment["source_locator"] else ""
            remaining = max_chars - used - len(separator)
            if remaining <= 0:
                flush()
                continue

            end = min(position + remaining, len(body))
            if end < len(body):
                # If this segment needs another window, preserve token
                # boundaries; do not silently cut clause refs or numbers.
                candidates = list(re.finditer(r"\s+", body[position:end]))
                if candidates:
                    end = position + candidates[-1].end()
                elif current:
                    flush()
                    continue
                else:
                    raise ContractWindowError("unbreakable segment exceeds context limit")

            piece = body[position:end]
            current.append({
                "separator_before": separator,
                "source_locator": segment["source_locator"],
                "source_start": position,
                "source_end": end,
                "page": segment["pages"][0] if segment["pages"] else None,
                "pages": list(segment["pages"]),
                "kind": segment["kind"],
                "text": piece,
                "is_split_segment": position > 0 or end < len(body),
            })
            used += len(piece) + len(separator)
            covered_chars += len(piece)
            position = end
            if used == max_chars:
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
            "docling_layout_sequence_available": True,
            "reading_order_verified": False,
            "all_referenced_annexes_present": False,
            "semantic_risk_recall_verified": False,
        },
        "windows": windows,
    }
