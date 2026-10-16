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
    r"""["“«]([^"”»]+)["”»]|(?<!\w)'([^\n]+)'(?!\w)|‘([^’]+)’"""
)
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
        14: "fourteen catorce", 15: "fifteen quince", 20: "twenty veinte",
        21: "twenty-one veintiuno veintiún", 28: "twenty-eight veintiocho",
        30: "thirty treinta", 45: "forty-five", 60: "sixty sesenta",
        90: "ninety noventa",
    }.items()
    for word in words.split()
}
_DURATION = re.compile(
    r"\b(\d+|" + "|".join(sorted(map(re.escape, _NUMBER_WORDS), key=len, reverse=True))
    + r")\s*(?:\((\d+)\)\s*)?(?:(calendar|working|business)\s+)?-?"
    r"(days?|weeks?|months?|d[ií]as?|semanas?|meses|mes)\b",
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


def _durations(text: str) -> set[tuple[int, str, str]]:
    found: set[tuple[int, str, str]] = set()
    for number, digits, qualifier, unit in _DURATION.findall(text):
        value = int(digits) if digits else (
            int(number) if number.isdigit() else _NUMBER_WORDS[number.lower()]
        )
        found.add((value, _UNITS[unit[0].lower()], qualifier.lower()))
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
        explicit = _EXPLICIT_QUOTE.search(query_text)
        if explicit:
            # Citation prefixes are not part of the source's literal quotation.
            candidate = next(part for part in explicit.groups() if part is not None)
        elif not claim or _REFERENCE_ONLY_FRAMING.fullmatch(claim):
            candidate = ""
        else:
            candidate = claim
        quote = _normalise(candidate).strip(_EDGE_PUNCTUATION)
        if not re.search(r"\w", quote):
            quote_status: QuoteStatus = "NO_QUOTE"
        elif quote in _normalise(clause_text):
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
