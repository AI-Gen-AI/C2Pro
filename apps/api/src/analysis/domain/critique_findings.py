"""Source-bound N12 critique findings: provenance, not model authority.

The model may propose omissions and contradictions. A finding is usable only
if its purported clause and verbatim source quotation can be independently
located in the supplied document text. This validator does NOT claim the
explanation is logically correct or that document coverage is exhaustive.
"""

from __future__ import annotations

import re
from typing import Any

MAX_FINDINGS = 40
MAX_SOURCE_QUOTE_CHARS = 2000


def _normal(text: str) -> str:
    return " ".join(text.split()).casefold()


def source_bound_findings(
    findings: Any,
    *,
    source_text: str | None,
) -> list[dict[str, str]]:
    """Reject invented, noncontiguous or unlocated citations, fail-closed."""
    if not isinstance(findings, list) or not source_text:
        return []
    source = _normal(source_text)
    verified: list[dict[str, str]] = []
    for item in findings[:MAX_FINDINGS]:
        if not isinstance(item, dict):
            continue
        clause_ref = item.get("clause_ref")
        issue_type = item.get("issue_type")
        source_quote = item.get("source_quote")
        explanation = item.get("explanation")
        if (
            not isinstance(clause_ref, str)
            or not clause_ref.strip()
            or not isinstance(issue_type, str)
            or issue_type not in ("omission", "contradiction")
            or not isinstance(source_quote, str)
            or not 12 <= len(source_quote) <= MAX_SOURCE_QUOTE_CHARS
            or not isinstance(explanation, str)
            or not explanation.strip()
        ):
            continue
        quote = _normal(source_quote)
        if not quote or quote not in source:
            continue
        if not re.search(r"(?<!\w)" + re.escape(clause_ref.strip()) + r"(?!\w)", source_text, re.IGNORECASE):
            # The source must actually contain this reference, not merely the
            # extracted risks. Do not create evidence based on title metadata.
            continue

        # If the provided source has explicit lines like "EPC-04: <text>",
        # ensure the quoted fragment lies within THAT clause, not a different
        # clause in the same contract. For other document layouts, provenance
        # guarantees remain quote-global and must be reported accordingly.
        labels = list(
            re.finditer(r"(?m)^\s*(EPC-\d+)\s*:", source_text, re.IGNORECASE)
        )
        if labels and re.fullmatch(r"EPC-\d+", clause_ref.strip(), re.IGNORECASE):
            matched = False
            for pos, label in enumerate(labels):
                if label.group(1).casefold() != clause_ref.strip().casefold():
                    continue
                end = labels[pos + 1].start() if pos + 1 < len(labels) else len(source_text)
                matched = quote in _normal(source_text[label.end() : end])
                break
            if not matched:
                continue
        verified.append(
            {
                "clause_ref": clause_ref.strip(),
                "issue_type": issue_type,
                "source_quote": source_quote.strip(),
                "explanation": explanation.strip(),
            }
        )
    return verified


def format_source_bound_notes(findings: list[dict[str, str]]) -> str:
    """Keep exact citations visible to existing N12/UI consumers."""
    return "Source-cited critique findings:\n" + "\n".join(
        f"- {item['clause_ref']} [{item['issue_type']}]: "
        f"{item['explanation']} Source: “{item['source_quote']}”"
        for item in findings
    )


__all__ = ["source_bound_findings", "format_source_bound_notes"]
