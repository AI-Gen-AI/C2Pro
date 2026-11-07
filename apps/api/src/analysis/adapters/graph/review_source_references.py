"""Prepare read-only revision-bound source links from persisted clause IDs.

N13 must not invent clause identities by parsing model narrative. Only a
structured exact risk.clause_ref matched to a physically persisted clause in
this tenant/document/revision can create a link. This is location, not proof
that the critique or risk statement is correct.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any
from uuid import UUID

# Accept explicit numbered contractual clause codes; never mine free text.
_EXPLICIT_CLAUSE_CODE = re.compile(r"^(?:§\s*)?\d+(?:\.\d+)*$")
# This deliberately only recognizes a heading at the beginning of original
# persisted clause text. Do not relax this to search body text: references in
# a paragraph are not persisted clause identities. Punctuation terminators
# require whitespace or end-of-text so the numeric pattern cannot backtrack
# from a malformed token (for example, ``8.2(a)``) to its parent ``8``.
_LEADING_NUMBERED_HEADING = re.compile(
    r"^\s*(?:§\s*)?(\d+(?:\.\d+)*)(?=$|\s|[.:-](?=\s|$))"
)


def _normalized_numbered_clause_code(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.removeprefix("§").strip()
    return normalized if _EXPLICIT_CLAUSE_CODE.fullmatch(value.strip()) else None


def _leading_numbered_clause_code(full_text: object) -> str | None:
    if not isinstance(full_text, str):
        return None
    match = _LEADING_NUMBERED_HEADING.match(full_text)
    return match.group(1) if match else None


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
    """Return only unique, exact-scope locators for structured clause references.

    A genuine explicit numeric ``clause_code`` and an exact numbered heading
    at the *start* of parser-persisted ``full_text`` are both candidate
    locators. Their combined physical ClauseORM UUIDs must be unique; this
    fails closed when the two routes identify different persisted clauses.
    An explicit code with present source text that lacks a matching leading
    numeric heading is likewise unverified: source preservation is required
    before returning a VERIFIED locator.
    """
    requested_codes = {
        normalized
        for code in clause_codes
        if (normalized := _normalized_numbered_clause_code(code)) is not None
    }
    if not requested_codes:
        return []

    clauses = [
        clause for clause in persisted_clauses
        if (
            getattr(clause, "tenant_id", None) == tenant_id
            and getattr(clause, "project_id", None) == project_id
            and getattr(clause, "document_id", None) == document_id
            and getattr(clause, "revision_id", None) == revision_id
            and isinstance(getattr(clause, "id", None), UUID)
        )
    ]
    direct_matches: dict[str, list[Any]] = {code: [] for code in requested_codes}
    heading_matches: dict[str, list[Any]] = {code: [] for code in requested_codes}
    conflicted_codes: set[str] = set()
    for clause in clauses:
        code = _normalized_numbered_clause_code(getattr(clause, "clause_code", None))
        full_text = getattr(clause, "full_text", None)
        heading = _leading_numbered_clause_code(full_text)
        source_mismatch = code is not None and full_text is not None and heading != code
        # A missing legacy full_text does not weaken its own code identity.
        # Present source text without a matching numbered heading does: it is
        # neither a trustworthy explicit-code locator nor a fallback heading
        # locator. A disagreement makes either claimed identity ambiguous.
        if source_mismatch:
            conflicted_codes.update(
                candidate
                for candidate in (code, heading)
                if candidate in requested_codes
            )
            continue
        if code in direct_matches:
            direct_matches[code].append(clause)
        if heading in heading_matches:
            heading_matches[heading].append(clause)

    resolved: dict[str, Any] = {}
    for code in requested_codes:
        if code in conflicted_codes:
            continue
        direct_by_id = {clause.id: clause for clause in direct_matches[code]}
        heading_by_id = {clause.id: clause for clause in heading_matches[code]}
        # One physical clause may appear by both routes. Any distinct UUID in
        # their union is source-identity ambiguity and must not be selected.
        candidates_by_id = direct_by_id | heading_by_id
        if len(candidates_by_id) == 1:
            resolved[code] = next(iter(candidates_by_id.values()))

    refs: list[dict[str, str]] = []
    for clause in clauses:
        for code, resolved_clause in resolved.items():
            if clause is resolved_clause:
                refs.append({
                    "document_id": str(document_id),
                    "revision_id": str(revision_id),
                    "clause_id": str(clause.id),
                    "clause_code": code,
                })
                break
    return refs[:25]


def bind_risk_alert_source_references(
    risks: Iterable[Any], source_references: Iterable[dict[str, str]]
) -> list[dict[str, Any]]:
    """Attach one already-grounded source ref to each extracted risk, or an honest null.

    ``source_references`` must have been produced by
    :func:`grounded_review_source_references`; this function never derives a
    locator from generated risk text.  A duplicate/malformed reference is
    deliberately treated as unverified rather than selecting one arbitrarily.
    """
    by_code: dict[str, list[dict[str, str]]] = {}
    for reference in source_references:
        if not isinstance(reference, dict):
            continue
        code = reference.get("clause_code")
        if not isinstance(code, str) or not _EXPLICIT_CLAUSE_CODE.fullmatch(code):
            continue
        try:
            UUID(str(reference.get("document_id")))
            UUID(str(reference.get("revision_id")))
            UUID(str(reference.get("clause_id")))
        except (TypeError, ValueError):
            continue
        normalized = {
            "document_id": str(reference["document_id"]),
            "revision_id": str(reference["revision_id"]),
            "clause_id": str(reference["clause_id"]),
            "clause_code": code.removeprefix("§").strip(),
        }
        by_code.setdefault(normalized["clause_code"], []).append(normalized)

    bound: list[dict[str, Any]] = []
    for raw_risk in risks:
        risk = dict(raw_risk) if isinstance(raw_risk, dict) else {}
        raw_code = risk.get("clause_ref")
        code = raw_code.removeprefix("§").strip() if isinstance(raw_code, str) else ""
        candidates = by_code.get(code, []) if _EXPLICIT_CLAUSE_CODE.fullmatch(code) else []
        if len(candidates) == 1:
            risk["source_references"] = candidates
            risk["source_locator_status"] = "VERIFIED"
        else:
            risk["source_references"] = []
            risk["source_locator_status"] = "NOT_VERIFIED"
        bound.append(risk)
    return bound


__all__ = [
    "bind_risk_alert_source_references",
    "review_risk_clause_codes",
    "grounded_review_source_references",
]
