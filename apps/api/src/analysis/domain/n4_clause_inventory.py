"""Deterministic clause-heading inventory over a model-safe N2 projection.

This is an inventory of *detectable headings*, not a semantic assessment or
proof that all clauses in a document have been recognized. Never select only a
top-N set: every recognized heading is carried to the model in bounded parts.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

N4ClauseLanguage = Literal["EN", "ES", "PT"]

N4_CLAUSE_INVENTORY_MAX_CHARS_PER_MESSAGE = 3000
N4_CLAUSE_INVENTORY_LANGUAGES: tuple[N4ClauseLanguage, ...] = ("EN", "ES", "PT")


@dataclass(frozen=True, slots=True)
class N4InventoryClause:
    clause_ref: str
    heading: str
    start_offset: int
    end_offset: int
    language: N4ClauseLanguage | None


_LABEL = re.compile(
    r"^\s*(?P<word>section|article|clause|chapter|annex|exhibit|"
    r"secci[oó]n|art[ií]culo|cl[aá]usula|cap[ií]tulo|anexo|"
    r"se[cç][aã]o|artigo|anexo)\s+"
    r"(?P<ref>\d+(?:\.\d+){0,7}|[IVXLCDM]+|[A-Z])\b"
    r"(?:\s*[:.©\-–]\s*|\s+)?(?P<heading>.*)$",
    re.IGNORECASE,
)
_NUMBERED = re.compile(
    r"^\s*(?P<ref>\d{1,3}(?:\.\d{1,3}){0,7})(?:[.)])?"
    r"\s+(?P<heading>[\wÀ-ÿ][^\r\n]{2,180})$",
    re.UNICODE,
)
_LANG_MARKERS: dict[str, N4ClauseLanguage] = {
    "section": "EN", "article": "EN", "clause": "EN",
    "chapter": "EN", "annex": "EN", "exhibit": "EN",
    "sección": "ES", "seccion": "ES", "artículo": "ES",
    "articulo": "ES", "cláusula": "ES", "clausula": "ES",
    "capítulo": "ES", "capitulo": "ES",
    "seção": "PT", "secao": "PT", "artigo": "PT",
}


def _detected_heading(
    raw_line: str, cursor: int,
) -> tuple[int, str, str, N4ClauseLanguage | None] | None:
    """Parse one N2 heading without consuming or truncating the source text."""
    line = raw_line.rstrip("\r\n")
    labelled = _LABEL.fullmatch(line)
    match = labelled or _NUMBERED.fullmatch(line)
    if match is None:
        return None
    heading = (match.group("heading") or "").strip()
    if not heading or not any(char.isalpha() for char in heading):
        return None
    language = (
        _LANG_MARKERS.get(labelled.group("word").lower())
        if labelled is not None else None
    )
    start = cursor + len(line) - len(line.lstrip())
    return start, match.group("ref"), heading[:180], language


def build_n4_clause_inventory(projection_text: str) -> tuple[N4InventoryClause, ...]:
    """Detect EN/ES/PT headings, preserving exact N2 character offsets.

    This heading heuristic cannot attest to missing or unusual clauses.
    Source windows still pass ALL N2 text through to the model.
    """
    if not isinstance(projection_text, str):
        raise TypeError("N2 projection must be text")
    headings: list[tuple[int, str, str, N4ClauseLanguage | None]] = []
    cursor = 0
    for raw_line in projection_text.splitlines(keepends=True):
        detected = _detected_heading(raw_line, cursor)
        if detected is not None:
            headings.append(detected)
        cursor += len(raw_line)
    clauses: list[N4InventoryClause] = []
    for index, (start, ref, heading, language) in enumerate(headings):
        end = headings[index + 1][0] if index + 1 < len(headings) else len(projection_text)
        clauses.append(N4InventoryClause(
            clause_ref=ref, heading=heading, start_offset=start,
            end_offset=end, language=language,
        ))
    return tuple(clauses)


def render_n4_clause_inventory_messages(
    clauses: Sequence[N4InventoryClause],
    max_chars: int = N4_CLAUSE_INVENTORY_MAX_CHARS_PER_MESSAGE,
) -> tuple[str, ...]:
    """Render *every* recognized clause in messages bounded to max_chars."""
    if max_chars < 100:
        raise ValueError("clause inventory message limit must be >=100")
    header = (
        "N2 detected clause headings (not a completeness attestation).\n"
        "Declare each reference examined with or without risk:\n"
    )
    if not clauses:
        return ("N2 clause heading inventory: none detected; read the full "
                "source anyway.",)

    parts: list[str] = []
    current = header
    for item in clauses:
        label = item.language or "UNKNOWN"
        line = (
            f"- {item.clause_ref} | {item.heading} | "
            f"offsets [{item.start_offset},{item.end_offset}) | {label}\n"
        )
        # Fail loudly rather than silently trimming/skipping an identifier.
        if len(header) + len(line) > max_chars:
            raise ValueError("clause item exceeds inventory message limit")
        if len(current) + len(line) > max_chars:
            parts.append(current.rstrip("\n"))
            current = header
        current += line
    parts.append(current.rstrip("\n"))
    return tuple(parts)
