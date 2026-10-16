"""
C2Pro - Source Locator Service

This service is responsible for linking AI-generated text evidence back to its
exact source within a document, using a combination of direct lookups and
fuzzy text matching.
"""

import re
from typing import Literal
from uuid import UUID

import structlog
from pydantic import BaseModel, Field
from rapidfuzz import fuzz, process

from src.core.tenants.types import require_tenant_id
from src.documents.ports.document_repository import IDocumentRepository

logger = structlog.get_logger()


QuoteStatus = Literal["VERBATIM", "NOT_VERBATIM", "NO_QUOTE"]
ClaimSupport = Literal["UNVERIFIED", "CONFLICT_DETECTED"]


# Pydantic model for the enriched evidence location
class SourceLocation(BaseModel):
    """
    Represents the precise location of a piece of evidence within a document.

    Finding the cited clause is not proof the claim is true: ``similarity_score``,
    ``quote_status`` and ``term_conflicts`` are reported separately, and
    ``claim_support`` is never "supported" (PQ-HITL-06/#942, #713).
    """
    document_id: UUID = Field(..., description="The ID of the document containing the evidence.")
    revision_id: UUID | None = Field(..., description="The revision the matched clause belongs to.")
    clause_id: UUID = Field(..., description="The matched clause.")
    clause_code: str = Field(..., description="The matched clause's code, e.g. '5.2'.")
    match_method: Literal["clause_code", "text_similarity"] = Field(
        ..., description="How the clause was found."
    )
    page_number: int | None = Field(None, description="The page number where the evidence is found.")
    chunk_text: str = Field(..., description="The actual text of the matched chunk from the document.")
    similarity_score: int = Field(
        ...,
        description=(
            "Locator match score (0-100); 100 for a clause-code hit. It locates the "
            "clause and is never evidence that the claim is supported."
        ),
    )
    quote_status: QuoteStatus = Field(
        ..., description="Whether the claim's quoted text appears verbatim in the clause."
    )
    term_conflicts: list[str] = Field(
        default_factory=list,
        description="Durations or named parties in the claim that the clause does not contain.",
    )
    claim_support: ClaimSupport = Field(
        ..., description="UNVERIFIED unless a deterministic term conflict was detected."
    )
    bbox: list[float] | None = Field(None, description="Bounding box for highlighting in a PDF viewer.")


_EDGE_PUNCTUATION = " \t\n:;,.-\u2013\u2014"
# Match explicit source quotation separately from citation framing. ASCII
# single quotes use a greedy outer delimiter to preserve possessive apostrophes.
_EXPLICIT_QUOTE = re.compile(
    r'''"([^"\n]+)"|“([^”\n]+)”|«([^»\n]+)»'''
)


def _explicit_quotes(text: str) -> tuple[list[str], bool]:
    """Extract separately delimited excerpts, never accepting malformed quotes.

    Paired typographic marks and ASCII single quotes may contain possessives.
    A missing true closing delimiter is explicitly non-verbatim (fail closed).
    """
    found = [
        (match.start(), next(part for part in match.groups() if part is not None))
        for match in _EXPLICIT_QUOTE.finditer(text)
    ]
    malformed = False

    start = text.find("‘")
    while start != -1:
        next_start = text.find("‘", start + 1)
        limit = next_start if next_start != -1 else len(text)
        endings = [
            i for i in range(start + 1, limit)
            if text[i] == "’"
            and not (
                i + 1 < len(text)
                and text[i - 1].isalnum()
                and text[i + 1].isalnum()
            )
        ]
        boundaries = [
            i for i in endings
            if i + 1 == len(text) or text[i + 1] in ";,.:!?)]}"
        ]
        end = (boundaries[-1] if boundaries else endings[-1]) if endings else -1
        if end == -1:
            malformed = True
        else:
            found.append((start, text[start + 1 : end]))
        start = next_start

    cursor = 0
    while cursor < len(text):
        opening = text.find("'", cursor)
        if opening == -1:
            break
        if opening > 0 and text[opening - 1].isalnum():
            cursor = opening + 1
            continue
        endings = [
            i for i in range(opening + 1, len(text))
            if text[i] == "'" and (
                i + 1 == len(text) or not text[i + 1].isalnum()
            )
        ]
        if not endings:
            malformed = True
            cursor = opening + 1
            continue
        # A delimiter immediately followed by a new explicitly quoted
        # excerpt is a true closer, not an internal plural possessive.
        separated = [
            i for i in endings
            if re.match(
                r"\s+(?:and|or|but)\s+'", text[i + 1 :], re.IGNORECASE
            )
        ]
        closing = separated[0] if separated else endings[-1]
        # If the only possible closer is followed by free prose, its
        # apostrophe may instead be a plural possessive in an unclosed quote.
        # This syntax is ambiguous; it must NOT certify a partial quote.
        if (
            not separated
            and len(endings) == 1
            and closing + 1 < len(text)
            and text[closing + 1].isspace()
            and re.match(r"\s+\w", text[closing + 1 :])
        ):
            malformed = True
        found.append((opening, text[opening + 1 : closing]))
        cursor = closing + 1

    return [candidate for _, candidate in sorted(found)], malformed


_REFERENCE_ONLY_FRAMING = re.compile(
    r"(?:see|refer\s+to|according\s+to|under|per|cf\.?|as\s+per|"
    r"seg[uú]n(?:\s+(?:la|el))?|v[eé]ase|consulte|conforme\s+a|de\s+acuerdo\s+con)",
    re.IGNORECASE,
)
_NUMBER_WORDS = {
    word: value
    for value, words in {
        1: "one uno una", 2: "two dos", 3: "three tres", 4: "four cuatro",
        5: "five cinco", 6: "six seis", 7: "seven siete", 8: "eight ocho",
        9: "nine nueve", 10: "ten diez", 11: "eleven once", 12: "twelve doce",
        13: "thirteen trece", 14: "fourteen catorce",
        15: "fifteen quince", 16: "sixteen dieciséis dieciseis",
        17: "seventeen diecisiete", 18: "eighteen dieciocho",
        19: "nineteen diecinueve", 20: "twenty veinte",
        21: "twenty-one veintiuno veintiún veintiun",
        22: "twenty-two veintidós veintidos",
        23: "twenty-three veintitrés veintitres",
        24: "twenty-four veinticuatro",
        25: "twenty-five veinticinco",
        26: "twenty-six veintiséis veintiseis",
        27: "twenty-seven veintisiete",
        28: "twenty-eight veintiocho", 29: "twenty-nine veintinueve",
        30: "thirty treinta", 45: "forty-five", 60: "sixty sesenta",
        90: "ninety noventa",
    }.items()
    for word in words.split()
}
# Treat space-separated composite numerals as one deadline value. The regex
# sorts the longest alternatives first so it cannot match only the tail "one".
_EN_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_EN_ONES = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9,
}
_NUMBER_WORDS.update({
    f"{tens}{separator}{one}": base + increment
    for tens, base in _EN_TENS.items()
    for one, increment in _EN_ONES.items()
    for separator in (" ", "-")
})
_ES_TENS = {
    "treinta": 30, "cuarenta": 40, "cincuenta": 50,
    "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90,
}
_ES_ONES = {
    "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
}
_NUMBER_WORDS.update({
    f"{tens} y {one}": base + increment
    for tens, base in _ES_TENS.items()
    for one, increment in _ES_ONES.items()
})
# Include standalone decades as well as composed values (forty, forty-one).
_NUMBER_WORDS.update(_EN_TENS)
_NUMBER_WORDS.update(_ES_TENS)
_DURATION = re.compile(
    r"\b(\d+|" + "|".join(sorted(map(re.escape, _NUMBER_WORDS), key=len, reverse=True))
    + r")[\s-]*(?:\((\d+)\)[\s-]*)?(?:(calendar|working|business)[\s-]+)?"
    r"(days?|weeks?|months?|d[ií]as?|semanas?|meses|mes)\b"
    r"(?:[\s-]+(h[aá]biles?|naturales?|laborables?|calendario))?",
    re.IGNORECASE,
)
_UNITS = {"d": "day", "w": "week", "s": "week", "m": "month"}
_PARTIES = {
    "employer": r"employer|empleador",
    "owner": r"owner|propietario",
    "client": r"client|cliente",
    "contractor": r"contractor|contratista",
    "subcontractor": r"subcontractor|subcontratista",
    "engineer": r"engineer|ingeniero",
}


def _normalise(text: str) -> str:
    # Compare source text verbatim modulo case/whitespace; punctuation such as
    # Contractor's / Contractors changes the source and must NOT be deleted.
    return " ".join(text.lower().split())


# Reduce written hundreds to numeric values before the regular duration
# extractor. Otherwise an unsupported prefix can cause "eighty days" to
# be misread from "one hundred eighty days" and invent a conflict.
_HUNDRED_WORDS = {
    "one hundred": 100, "two hundred": 200, "three hundred": 300,
    "four hundred": 400, "five hundred": 500, "six hundred": 600,
    "seven hundred": 700, "eight hundred": 800,
    "nine hundred": 900, "cien": 100, "ciento": 100,
    "doscientos": 200, "trescientos": 300, "cuatrocientos": 400,
    "quinientos": 500, "seiscientos": 600, "setecientos": 700,
    "ochocientos": 800, "novecientos": 900,
}
_HUNDRED_PARTS = "|".join(
    sorted(map(re.escape, _HUNDRED_WORDS), key=len, reverse=True)
)
_SUBHUNDRED_PARTS = "|".join(
    sorted(map(re.escape, _NUMBER_WORDS), key=len, reverse=True)
)
_HUNDREDS_RE = re.compile(
    rf"\b({_HUNDRED_PARTS})"
    rf"(?:\s+(?:and\s+)?({_SUBHUNDRED_PARTS}))?"
    r"(?=\s*(?:\(\d+\)\s*)?"
    r"(?:(?:calendar|working|business)[\s-]+)?"
    r"(?:days?|weeks?|months?|d[ií]as?|semanas?|meses|mes)\b)",
    re.IGNORECASE,
)


def _normalize_hundreds(match: re.Match[str]) -> str:
    base = _HUNDRED_WORDS[match.group(1).lower()]
    rest = _NUMBER_WORDS[match.group(2).lower()] if match.group(2) else 0
    return str(base + rest)


def _durations(text: str) -> set[tuple[int, str, str]]:
    found: set[tuple[int, str, str]] = set()
    normalized = _HUNDREDS_RE.sub(_normalize_hundreds, text)
    for number, digits, qualifier, unit, post_qualifier in _DURATION.findall(normalized):
        value = int(digits) if digits else (
            int(number) if number.isdigit() else _NUMBER_WORDS[number.lower()]
        )
        explicit_qualifier = (post_qualifier or qualifier).lower()
        if explicit_qualifier in {
            "hábil", "hábiles", "habil", "habiles",
            "laborable", "laborables", "working",
        }:
            explicit_qualifier = "business"
        elif explicit_qualifier in {"natural", "naturales", "calendario"}:
            explicit_qualifier = "calendar"
        found.add((value, _UNITS[unit[0].lower()], explicit_qualifier))
    return found


def _duration_conflicts(claim: str, clause_text: str) -> list[str]:
    source = _durations(clause_text)
    conflicts = []
    for value, unit, qualifier in _durations(claim):
        # Missing day qualifier is less specific, not proof of contradiction.
        # Explicit calendar vs business/working qualifiers DO conflict.
        if any(
            value == sv and unit == su and (
                not qualifier or not sq or qualifier == sq
            )
            for sv, su, sq in source
        ):
            continue
        label = f"{value} {qualifier + ' ' if qualifier else ''}{unit}"
        conflicts.append(f"duration_not_in_source:{label}")
    return sorted(conflicts)


def _parties(text: str) -> set[str]:
    return {
        name
        for name, pattern in _PARTIES.items()
        if re.search(rf"\b(?:{pattern})s?\b", text, re.IGNORECASE)
    }


class SourceLocator:
    """
    Finds the source of AI-generated text within project documents.
    """
    def __init__(self, document_repository: IDocumentRepository):
        self.document_repository = document_repository
        # Regex to find clause references like "Clause 14.2", "Sub-Clause 3.1.a" or "§5.2"
        self.clause_regex = re.compile(
            r'(?:§\s*|\b(?:cláusula|clausula|clause|sub-clause|sub-cláusula)\s+)'
            r'([0-9]+\.[0-9]+(?:\.[a-zA-Z0-9]+)*)',
            re.IGNORECASE,
        )

    def _assess(
        self, query_text: str, clause_text: str
    ) -> tuple[QuoteStatus, list[str], ClaimSupport]:
        """Compare the claim with the clause without ever confirming the claim."""
        claim = self.clause_regex.sub(" ", query_text).strip(_EDGE_PUNCTUATION)
        explicit, malformed_quote = _explicit_quotes(query_text)
        # Every explicitly delimited quotation must be present in the source.
        # Checking only the first permits a fabricated second quote to pass.
        if explicit:
            candidates = explicit
        elif not claim or _REFERENCE_ONLY_FRAMING.fullmatch(claim):
            candidates = []
        else:
            candidates = [claim]
        quotes = [
            _normalise(candidate).strip(_EDGE_PUNCTUATION)
            for candidate in candidates
        ]
        if malformed_quote:
            quote_status: QuoteStatus = "NOT_VERBATIM"
        elif not any(re.search(r"\w", quote) for quote in quotes):
            quote_status = "NO_QUOTE"
        elif all(quote and quote in _normalise(clause_text) for quote in quotes):
            quote_status = "VERBATIM"
        else:
            quote_status = "NOT_VERBATIM"
        conflicts = sorted(
            _duration_conflicts(claim, clause_text)
            + [f"party_not_in_source:{p}" for p in _parties(claim) - _parties(clause_text)]
        )
        return quote_status, conflicts, "CONFLICT_DETECTED" if conflicts else "UNVERIFIED"

    async def locate_evidence(
        self,
        query_text: str,
        document_id: UUID,
        tenant_id: UUID,
        min_similarity_score: int = 85,
        revision_id: UUID | None = None,
    ) -> SourceLocation | None:
        """
        Locates the best source for a given query text within a document.

        It uses a hybrid approach:
        1.  **Fast Path**: Attempts to extract a clause code from the query and find an exact match.
        2.  **Slow Path**: If the fast path fails, it performs a fuzzy search over all clauses
            in the document to find the best partial match.

        Args:
            query_text: The text generated by the LLM (the "evidence quote").
            document_id: The ID of the document to search within.
            min_similarity_score: The minimum score (0-100) for a fuzzy match to be considered valid.
            revision_id: Lane C / C3a. ``None`` searches the document's trusted-current
                revision; an explicit revision searches only that historical revision.
                The same clause code exists in several revisions, so both paths read
                exactly one clause set and never mix revisions.

        Returns:
            A SourceLocation object if a satisfactory match is found, otherwise None.
        """
        scoped_tenant_id = require_tenant_id(tenant_id)
        # --- Fast Path: Direct Code Match ---
        match = self.clause_regex.search(query_text)
        if match:
            clause_code = match.group(1)
            clause = await self.document_repository.get_clause_by_document_and_code(
                tenant_id=scoped_tenant_id,
                document_id=document_id,
                clause_code=clause_code,
                revision_id=revision_id,
            )
            if clause:
                logger.info("source_locator_fast_path_success", clause_code=clause_code)
                quote_status, term_conflicts, claim_support = self._assess(
                    query_text, clause.full_text or ""
                )
                return SourceLocation(
                    document_id=document_id,
                    revision_id=clause.revision_id,
                    clause_id=clause.id,
                    clause_code=clause.clause_code,
                    match_method="clause_code",
                    page_number=None, # Page number is not stored on Clause model
                    chunk_text=clause.full_text or "",
                    similarity_score=100,
                    bbox=None, # Bbox is not stored on Clause model
                    quote_status=quote_status,
                    term_conflicts=term_conflicts,
                    claim_support=claim_support,
                )

        # --- Slow Path: Fuzzy Search ---
        logger.info("source_locator_slow_path_started", document_id=document_id)
        all_clauses = (
            await self.document_repository.list_current_clauses(scoped_tenant_id, document_id)
            if revision_id is None
            else await self.document_repository.list_revision_clauses(
                scoped_tenant_id, document_id, revision_id
            )
        )

        if not all_clauses:
            logger.warning("source_locator_no_clauses", document_id=document_id)
            return None

        # Create a dictionary of clause texts to search against
        choices = {c.id: c.full_text for c in all_clauses if c.full_text}

        # Use rapidfuzz to find the best match
        best_match = process.extractOne(query_text, choices, scorer=fuzz.partial_ratio)

        if best_match and best_match[1] >= min_similarity_score:
            match_score, match_key = best_match[1], best_match[2]
            matched_clause = next((c for c in all_clauses if c.id == match_key), None)

            if matched_clause:
                logger.info("source_locator_slow_path_success", best_score=match_score)
                quote_status, term_conflicts, claim_support = self._assess(
                    query_text, matched_clause.full_text or ""
                )
                return SourceLocation(
                    document_id=document_id,
                    revision_id=matched_clause.revision_id,
                    clause_id=matched_clause.id,
                    clause_code=matched_clause.clause_code,
                    match_method="text_similarity",
                    page_number=None, # Page number is not on Clause model
                    chunk_text=matched_clause.full_text or "",
                    similarity_score=int(match_score),
                    bbox=None, # Bbox is not on Clause model
                    quote_status=quote_status,
                    term_conflicts=term_conflicts,
                    claim_support=claim_support,
                )

        logger.warning("source_locator_no_match_found", min_score=min_similarity_score)
        return None
