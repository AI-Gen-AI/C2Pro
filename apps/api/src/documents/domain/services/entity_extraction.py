"""
TS-UD-DOC-ENT-003: Duration entity extraction helpers.
Also supports TS-UD-DOC-ENT-001/002/004 compatibility extractors.
Refers to Suite ID: TS-UD-DOC-CNF-001.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal


def _normalize_number(value: str) -> Decimal:
    compact = value.strip().replace(" ", "")
    compact = re.sub(r"[^\d,.\-]+$", "", compact)
    compact = re.sub(r"(?<=\d)\.$", "", compact)
    if "," in compact and "." in compact:
        if compact.rfind(",") > compact.rfind("."):
            normalized = compact.replace(".", "").replace(",", ".")
        else:
            normalized = compact.replace(",", "")
    elif "," in compact:
        left, _, right = compact.rpartition(",")
        if right.isdigit() and len(right) == 3 and left.replace("-", "").isdigit():
            normalized = compact.replace(",", "")
        else:
            normalized = compact.replace(",", ".")
    else:
        parts = compact.split(".")
        if len(parts) > 2:
            normalized = "".join(parts)
        elif len(parts) == 2 and len(parts[1]) == 3 and parts[0].replace("-", "").isdigit():
            normalized = compact.replace(".", "")
        else:
            normalized = compact
    return Decimal(normalized)


def extract_durations(text: str) -> list[dict[str, int | str]]:
    """Refers to Suite ID: TS-UD-DOC-ENT-003."""
    pattern = re.compile(r"\b(?P<value>\d+)\s*(?P<unit>day|days|week|weeks|month|months|year|years)\b", re.IGNORECASE)
    unit_map = {
        "day": "days",
        "days": "days",
        "week": "weeks",
        "weeks": "weeks",
        "month": "months",
        "months": "months",
        "year": "years",
        "years": "years",
    }
    results: list[dict[str, int | str]] = []
    for match in pattern.finditer(text):
        results.append(
            {
                "value": int(match.group("value")),
                "unit": unit_map[match.group("unit").lower()],
            }
        )
    return results


def extract_dates(text: str) -> list[date]:
    """Compatibility helper for TS-UD-DOC-ENT-001 legacy tests."""
    results: list[date] = []
    for match in re.finditer(r"\b(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})\b", text):
        try:
            results.append(date(int(match.group("y")), int(match.group("m")), int(match.group("d"))))
        except ValueError:
            continue
    for match in re.finditer(r"\b(?P<d>\d{2})/(?P<m>\d{2})/(?P<y>\d{4})\b", text):
        try:
            results.append(date(int(match.group("y")), int(match.group("m")), int(match.group("d"))))
        except ValueError:
            continue
    return results


def extract_money(text: str) -> list[dict[str, Decimal | str]]:
    """Compatibility helper for TS-UD-DOC-ENT-002 legacy tests."""
    results: list[dict[str, Decimal | str]] = []
    patterns = [
        (r"€\s*(?P<amount>-?[\d.,]+)", "EUR"),
        (r"(?P<amount>-?[\d.,]+)\s*(?:EUR|euros?)\b", "EUR"),
        (r"\bUSD\s*(?P<amount>-?[\d.,]+)", "USD"),
        (r"\$\s*(?P<amount>-?[\d.,]+)", "USD"),
        (r"(?P<amount>-?[\d.,]+)\s*(?:dollars?)\b", "USD"),
    ]
    seen: set[tuple[str, str]] = set()
    for pattern, currency in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            amount = _normalize_number(match.group("amount"))
            key = (str(amount), currency)
            if key in seen:
                continue
            seen.add(key)
            results.append({"amount": amount, "currency": currency})
    return results


def extract_stakeholders(text: str) -> list[dict[str, str]]:
    """Compatibility helper for TS-UD-DOC-ENT-004 legacy tests."""
    org_match = re.search(
        r"\bcontratista\s+(?P<org>[A-Z][A-Z0-9 .&]+?)\s+representado",
        text,
        flags=re.IGNORECASE,
    )
    organization = org_match.group("org").strip() if org_match else ""

    pattern = re.compile(
        r"(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*\((?P<email>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\)"
    )
    results: list[dict[str, str]] = []
    seen_emails: set[str] = set()
    for match in pattern.finditer(text):
        email = match.group("email").lower()
        if email in seen_emails:
            continue
        seen_emails.add(email)
        item = {"name": match.group("name"), "email": email}
        if organization:
            item["organization"] = organization
        results.append(item)
    return results


def calculate_confidence_score(
    text: str,
    extracted_entities_count: int,
    parsing_errors_count: int,
    ambiguous_markers_count: int,
) -> float:
    """Refers to Suite ID: TS-UD-DOC-CNF-001."""
    base = 0.5

    entities = max(0, extracted_entities_count)
    errors = max(0, parsing_errors_count)
    ambiguities = max(0, ambiguous_markers_count)

    # Reward richer extraction evidence with a bounded contribution.
    entity_boost = min(0.35, 0.05 * entities)
    error_penalty = min(0.4, 0.1 * errors)
    ambiguity_penalty = min(0.3, 0.08 * ambiguities)

    has_enumeration = bool(re.search(r"\b\d+\s*[.)]", text))
    structure_boost = 0.15 if has_enumeration else 0.0

    score = base + entity_boost + structure_boost - error_penalty - ambiguity_penalty
    return max(0.0, min(1.0, round(score, 4)))
