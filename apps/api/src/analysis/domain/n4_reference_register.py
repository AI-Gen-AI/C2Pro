"""N4 reference register (JV1-A7): where do cited cross-references resolve?

Status vocabulary:
- IN_DOCUMENT: the referenced label is defined (heading line) in the source text.
- MISSING_EXTERNAL: a literal reference to a separate attachment/standard is
  present in a quote found verbatim in the source, but its target is absent.
  Proposes "Referenced document not provided" with that literal quote.
- UNRESOLVED: anything else (internal clause refs not found, quote not literal).
Nothing here certifies legal meaning; entries are proposals for human review.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Any

MISSING_DOCUMENT_PROPOSAL = "Referenced document not provided"

_ATTACHMENT = re.compile(
    r"\b(Appendix|Annex|Schedule|Exhibit|Attachment)\s+([A-Z0-9][A-Za-z0-9.\-]*)",
)
_STANDARD = re.compile(r"\b(ISO|EN|IEC|ASTM|DIN|BS)\s?(\d[\w.\-]*)")
_INTERNAL = re.compile(r"\b(Clause|Section|Article)\s+(\d[\d.]*\d|\d)", re.IGNORECASE)


def _defined(label: str, source_text: str) -> bool:
    """True when ``label`` starts a line (heading/definition) in the source."""
    pattern = r"^\s*(?:\d+[.)]?\s*)?" + re.escape(label) + r"\b(?![\w.-]*\w)"
    return re.search(pattern, source_text, re.IGNORECASE | re.MULTILINE) is not None


def build_reference_register(
    source_text: str, items: Sequence[Mapping[str, Any]],
    *, unresolved_refs: Sequence[str] = (),
) -> list[dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    # Remissions can be contractually material even when N4 found no risks.
    # Inspect every source line instead of limiting this register to model
    # findings. Only literal projection text is eligible for a proposal.
    source_items: list[Mapping[str, Any]] = list(items)
    for line in source_text.splitlines():
        source_line = line.strip()
        if source_line and (
            _ATTACHMENT.search(source_line) or _STANDARD.search(source_line)
            or _INTERNAL.search(source_line)
        ):
            source_items.append({
                "finding_key": "source-ref:" + sha256(source_line.encode("utf-8")).hexdigest(),
                "source_quote": source_line,
            })
    for item in source_items:
        quote = item.get("source_quote")
        literal = isinstance(quote, str) and bool(quote) and quote in source_text
        if not isinstance(quote, str):
            continue
        found: list[tuple[str, bool]] = []  # (label, external)
        for m in _ATTACHMENT.finditer(quote):
            found.append((f"{m.group(1).title()} {m.group(2).rstrip('.-')}", True))
        for m in _STANDARD.finditer(quote):
            found.append((f"{m.group(1)} {m.group(2).rstrip('.-')}", False))
        for m in _INTERNAL.finditer(quote):
            found.append((f"{m.group(1).title()} {m.group(2).rstrip('.-')}", False))
        for label, external in found:
            entry = entries.get(label)
            if entry is None:
                if _defined(label, source_text):
                    status = "IN_DOCUMENT"
                elif external and literal:
                    status = "MISSING_EXTERNAL"
                else:
                    status = "UNRESOLVED"
                entry = entries[label] = {
                    "label": label,
                    "status": status,
                    "source_quote": quote if literal else None,
                    "proposal": (
                        MISSING_DOCUMENT_PROPOSAL if status == "MISSING_EXTERNAL" else None
                    ),
                    "finding_keys": [],
                }
            key = item.get("finding_key")
            if key is not None and key not in entry["finding_keys"]:
                entry["finding_keys"].append(key)
    # Preserve model-declared remissions from the ledger, even when they are
    # not literal quotations or do not match our known reference patterns.
    # Only the source scan above may classify MISSING_EXTERNAL: a model alone
    # cannot prove an attachment was absent from the reviewed document set.
    for raw in unresolved_refs:
        if not isinstance(raw, str):
            continue
        label = " ".join(raw.split())[:160]
        if not label:
            continue
        if label in entries:
            continue
        entries[label] = {
            "label": label,
            "status": "UNRESOLVED",
            "source_quote": None,
            "proposal": None,
            "finding_keys": [],
        }
    return list(entries.values())
