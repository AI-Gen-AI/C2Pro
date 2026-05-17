"""Shared category inference utilities for coherence rules and graph nodes."""

from __future__ import annotations

from ..models import Clause, CoherenceCategory

CATEGORY_KEYWORDS: dict[CoherenceCategory, list[str]] = {
    "BUDGET": [
        "budget", "cost", "price", "amount", "payment", "invoice", "expense",
        "contingency", "retention", "advance", "total", "unit_price", "line_total",
        "planned", "current", "variance", "overrun", "financial",
    ],
    "TIME": [
        "schedule", "deadline", "milestone", "date", "duration", "start_date",
        "end_date", "timeline", "delay", "overdue", "predecessor", "task",
        "calendar", "days", "weeks", "months",
    ],
    "LEGAL": [
        "contract", "agreement", "clause", "term", "condition", "warranty",
        "liability", "penalty", "notice", "insurance", "indemnity", "review",
        "expiry", "termination", "dispute", "arbitration",
    ],
    "SCOPE": [
        "scope", "deliverable", "requirement", "specification", "work",
        "objective", "inclusion", "exclusion", "change", "amendment",
    ],
    "TECHNICAL": [
        "bom", "material", "specification", "standard", "iso", "astm",
        "lead_time", "technical", "engineering", "design", "component",
    ],
    "QUALITY": [
        "quality", "inspection", "test", "compliance", "standard",
        "acceptance", "defect", "tolerance", "frequency",
    ],
}


def infer_category(clause: Clause) -> CoherenceCategory:
    """
    Infer the coherence category from clause text and data keys.

    Uses keyword matching to determine the most likely category.
    Returns "SCOPE" as default if no strong match.
    """
    text_lower = clause.text.lower() if clause.text else ""
    data_keys = " ".join(clause.data.keys()).lower() if clause.data else ""
    combined = f"{text_lower} {data_keys}"

    scores: dict[CoherenceCategory, int] = {cat: 0 for cat in CATEGORY_KEYWORDS}

    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                scores[category] += 1

    max_score = max(scores.values())
    if max_score == 0:
        return "SCOPE"

    for cat, score in scores.items():
        if score == max_score:
            return cat

    return "SCOPE"
