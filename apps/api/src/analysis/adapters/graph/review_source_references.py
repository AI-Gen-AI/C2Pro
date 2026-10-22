"""Prepare read-only revision-bound source links from persisted clause IDs.

N13 must not invent clause identities by parsing model narrative. Only a
structured exact risk.clause_ref matched to a physically persisted clause in
this tenant/document/revision can create a link. This is location, not proof
that the critique or risk statement is correct.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from typing import Any
from uuid import UUID

# Accept explicit numbered contractual clause codes; never mine free text.
_EXPLICIT_CLAUSE_CODE = re.compile(r"^(?:§\s*)?\d+(?:\.\d+)*$")


def review_risk_clause_codes(risks: object) -> set[str]:
    if not isinstance(risks, list):
        return set()
    codes: set[str] = set()
    for item in risks:
        if not isinstance(item, dict):
            continue
        raw = item.get("clause_ref")
        if not isinstance(raw, str):
            continue
        value = raw.strip()
        if _EXPLICIT_CLAUSE_CODE.fullmatch(value):
            codes.add(value.removeprefix("§").strip())
    return codes


def grounded_review_source_references(
    *,
    tenant_id: UUID,
    project_id: UUID,
    document_id: UUID,
    revision_id: UUID,
    clause_codes: set[str],
    persisted_clauses: Iterable[Any],
) -> list[dict[str, str]]:
    """Only exact unique revision-bound persisted clause IDs are navigable."""
    clauses = list(persisted_clauses)
    seen_counts = Counter(
        str(getattr(clause, "clause_code", "")) for clause in clauses
        if (
            getattr(clause, "tenant_id", None) == tenant_id
            and getattr(clause, "project_id", None) == project_id
            and getattr(clause, "document_id", None) == document_id
            and getattr(clause, "revision_id", None) == revision_id
        )
    )
    refs: list[dict[str, str]] = []
    for clause in clauses:
        code = getattr(clause, "clause_code", None)
        if (
            not isinstance(code, str)
            or code not in clause_codes
            or seen_counts[code] != 1
            or getattr(clause, "tenant_id", None) != tenant_id
            or getattr(clause, "project_id", None) != project_id
            or getattr(clause, "document_id", None) != document_id
            or getattr(clause, "revision_id", None) != revision_id
            or not isinstance(getattr(clause, "id", None), UUID)
        ):
            continue
        refs.append({
            "document_id": str(document_id),
            "revision_id": str(revision_id),
            "clause_id": str(clause.id),
            "clause_code": code,
        })
    return refs[:25]


__all__ = ["review_risk_clause_codes", "grounded_review_source_references"]
