"""Deterministic, source-bound section evidence from technical specifications.

This is an ingestion evidence slice, NOT a technical-compliance assessment:
a numbered section with an explicit obligation is indexed as source text.  No
LLM claim, inferred requirement, WBS link or assessment score is fabricated.
C3a trusted-current readers decide whether a revision can be used downstream.
"""

from __future__ import annotations

import re
from uuid import UUID, uuid4

from src.core.tenants.types import TenantId
from src.documents.domain.models import Clause, ClauseType

# Recognize only a genuine source section at the start of a line, never a
# cross-reference inside prose ("according to section 4.2").  The code is a
# source locator, not a derived identity or proof of technical compliance.
# Any recognizable numbered heading ends the preceding section, even when
# its code is unsupported. Otherwise an obligation from an over-depth section
# can leak into the prior eligible section and acquire a false source identity.
_SECTION_BOUNDARY = re.compile(
    r"^[ \t]*(?:section|secci[oó]n|apartado)[ \t]+"
    r"(?P<code>\d+(?:\.\d+)*)(?=[ \t\r\n.:\-–]|$)",
    re.IGNORECASE | re.MULTILINE,
)
_ELIGIBLE_SECTION_CODE = re.compile(r"\d{1,3}(?:\.\d{1,3}){0,6}\Z")
_OBLIGATION = re.compile(
    r"\b(?:shall|must|should|deber[aá]n?|debe(?:n)?|"
    r"se\s+exige|ser[aá]\s+obligatori[oa]s?|"
    r"minimum|m[ií]nim[oa]s?|not\s+less\s+than|no\s+inferior)\b",
    re.IGNORECASE,
)
_MAX_SOURCE_CHARS = 4000


def extract_technical_requirement_clauses(
    *,
    document_id: UUID,
    project_id: UUID,
    tenant_id: TenantId,
    parsed_text: str,
    revision_id: UUID | None,
) -> list[Clause]:
    """Index independently cited obligations, without claiming assessment.

    Each span is a literal substring of the parsed DOCX/PDF text.  Page and
    bbox remain unknown here: the generic parser does not establish exact
    DOCX page geometry.  Revision and deterministic row identity are assigned
    by persist_revision_clauses inside the ingestion authority fence.
    """
    if revision_id is None:
        # Unpinned source has no authority to create canonical technical
        # evidence. Legacy free-text remains available for noncanonical uses.
        return []

    boundaries = list(_SECTION_BOUNDARY.finditer(parsed_text))
    clauses: list[Clause] = []
    for index, match in enumerate(boundaries):
        section_code = match.group("code")
        if _ELIGIBLE_SECTION_CODE.fullmatch(section_code) is None:
            # Still terminates the preceding section; no evidence of its own.
            continue
        end = boundaries[index + 1].start() if index + 1 < len(boundaries) else len(parsed_text)
        raw = parsed_text[match.start():end]
        left_trim = len(raw) - len(raw.lstrip())
        stripped = raw.strip()
        if len(stripped) < 30:
            continue
        obligation = _OBLIGATION.search(stripped)
        if obligation is None:
            continue
        # Preserve the qualifying requirement inside the literal source span.
        # A long source section can have extensive background text before the
        # first operative sentence; silently keeping only its first 4000 chars
        # would fabricate "evidence" with no obligation in the saved snippet.
        window_start = (
            0 if obligation.end() <= _MAX_SOURCE_CHARS
            else max(0, obligation.start() - 200)
        )
        start_offset = match.start() + left_trim + window_start
        literal = stripped[window_start : window_start + _MAX_SOURCE_CHARS]
        end_offset = start_offset + len(literal)
        clauses.append(
            Clause(
                id=uuid4(),  # replaced by revision-derived UUID before DB insert
                project_id=project_id,
                tenant_id=tenant_id,
                document_id=document_id,
                clause_code=section_code,
                clause_type=ClauseType.OTHER,  # technical is the DOCUMENT type
                title=literal.split("\n", 1)[0][:80],
                full_text=literal,
                text_start_offset=start_offset,
                text_end_offset=end_offset,
                extracted_entities={
                    "technical_requirement": {
                        "source_section": section_code,
                        "verification_status": "unverified",
                    },
                    "evidence_location": {
                        "revision_id": str(revision_id),
                        "page_number": None,
                        "page_numbers": [],
                        "bbox": None,
                        "normalized": False,
                    },
                },
                extraction_confidence=None,  # do not invent AI confidence
                extraction_model="deterministic-technical-section-v1",
                revision_id=revision_id,
            )
        )
    return clauses
