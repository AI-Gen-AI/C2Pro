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

        # The reference and quote must be co-located in an identifiable clause.
        # Support line-initial EPC-04: and numbered clauses such as "5.2 <text>"
        # or "Section 5.2: <text>". Same-line mentions are not headings.
        # A reference merely *mentioned* elsewhere is not clause provenance.
        # Recognise only line-initial headings. Narrative same-line
        # cross-references such as "... Section 6.3 applies separately" are
        # NOT a new source span, even if followed by an authentic quotation.
        # Qualified headings need an explicit punctuation delimiter; without
        # one a phrase beginning "Section 6.3 applies" is still ambiguous.
        labels = list(
            re.finditer(
                r"(?im)^[ \t]*(?:"
                r"(?:(?:Clause|Section|Cláusula|Artículo|Articulo|§)[ \t]*)"
                r"(?P<qualified_ref>EPC-\d+|\d+(?:\.\d+){1,3})[ \t]*[:.)-]"
                r"|(?P<bare_ref>EPC-\d+|\d+(?:\.\d+){1,3})(?:[ \t]*[:.)-]|[ \t]+)"
                r")",
                source_text,
            )
        )
        # An uncertain qualified line still interrupts the *previous* known
        # clause, but is not itself sufficient to certify the new clause.
        # Otherwise a valid 5.2 heading can absorb an ambiguous Section 6.3.
        ambiguous_boundaries = [
            m.start()
            for m in re.finditer(
                r"(?im)^[ \t]*(?:Clause|Section|Cláusula|Artículo|Articulo|§)"
                r"[ \t]*(?:EPC-\d+|\d+(?:\.\d+){1,3})\b",
                source_text,
            )
        ]
        boundaries = sorted(
            {label.start() for label in labels} | set(ambiguous_boundaries)
        )
        matched = False
        for label in labels:
            ref = label.group("qualified_ref") or label.group("bare_ref")
            if ref.casefold() != clause_ref.strip().casefold():
                continue
            end = min(
                (point for point in boundaries if point > label.start()),
                default=len(source_text),
            )
            if quote in _normal(source_text[label.start() : end]):
                matched = True
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
    return "Source-cited critique findings (provenance only; interpretation unverified):\n" + "\n".join(
        f"- {item['clause_ref']} [{item['issue_type']}]: "
        f"{item['explanation']} Source: “{item['source_quote']}”"
        for item in findings
    )


__all__ = ["source_bound_findings", "format_source_bound_notes"]
