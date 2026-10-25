"""ACC-01 S7: a technical observation never silently becomes an approved WBS link."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.analysis.domain.budget_row_evidence import ApprovedWBSScope
from src.analysis.domain.technical_wbs_link_candidate import (
    TechnicalLinkState,
    TechnicalWBSLinkCandidateError,
    preview_technical_wbs_link,
)
from src.documents.domain.models import Clause, ClauseType
from src.temporal.domain.document_revision import DocumentRevision

TENANT = UUID("11111111-1111-1111-1111-111111111111")
PROJECT = UUID("22222222-2222-2222-2222-222222222222")
DOCUMENT = UUID("33333333-3333-3333-3333-333333333333")
REVISION = UUID("44444444-4444-4444-4444-444444444444")
BASELINE = UUID("55555555-5555-5555-5555-555555555555")
NODE = UUID("66666666-6666-6666-6666-666666666666")
STAMP = datetime(2026, 10, 25, tzinfo=UTC)
RAW_TEXT = (
    "General description.\n"
    "Section 4.1.2 Concrete compressive strength shall exceed 35 MPa at 28 days."
)
SECTION = "Section 4.1.2 Concrete compressive strength shall exceed 35 MPa at 28 days."
START = RAW_TEXT.index(SECTION)


def _revision() -> DocumentRevision:
    return DocumentRevision(
        revision_id=REVISION,
        document_id=DOCUMENT,
        project_id=PROJECT,
        tenant_id=TENANT,
        rev_no=1,
        blob_hash="a" * 64,
        blob_key="revisions/specification.docx",
        valid_from=STAMP,
        created_at=STAMP,
    )


def _clause() -> Clause:
    return Clause(
        id=uuid4(),
        tenant_id=TENANT,
        project_id=PROJECT,
        document_id=DOCUMENT,
        revision_id=REVISION,
        clause_code="4.1.2",
        clause_type=ClauseType.OTHER,
        title=SECTION,
        full_text=SECTION,
        text_start_offset=START,
        text_end_offset=START + len(SECTION),
        extracted_entities={
            "technical_requirement": {
                "source_section": "4.1.2",
                "verification_status": "unverified",
            },
            "evidence_location": {
                "revision_id": str(REVISION),
                "page_number": None,
                "bbox": None,
            },
        },
        extraction_confidence=None,
        extraction_model="deterministic-technical-section-v1",
    )


def _scope() -> ApprovedWBSScope:
    return ApprovedWBSScope(
        tenant_id=TENANT,
        project_id=PROJECT,
        baseline_id=BASELINE,
        node_ids=frozenset({NODE}),
    )


def _preview(**changes: object):
    kwargs = {
        "document_revision": _revision(),
        "clause": _clause(),
        "trusted_current_revision_id": REVISION,
        "parsed_revision_text": RAW_TEXT,
        "approved_wbs_scope": _scope(),
        "proposed_wbs_node_id": NODE,
        "actor_tenant_id": TENANT,
    }
    kwargs.update(changes)
    return preview_technical_wbs_link(**kwargs)  # type: ignore[arg-type]


def test_exact_source_and_approved_scope_yield_review_only_candidate() -> None:
    candidate = _preview()
    assert candidate.source_clause_id
    assert candidate.tenant_id == TENANT
    assert candidate.project_id == PROJECT
    assert candidate.technical_document_id == DOCUMENT
    assert candidate.technical_revision_id == REVISION
    assert candidate.source_section == "4.1.2"
    assert (candidate.source_start_offset, candidate.source_end_offset) == (
        START, START + len(SECTION)
    )
    assert candidate.source_blob_hash == "a" * 64
    assert candidate.proposed_wbs_baseline_id == BASELINE
    assert candidate.proposed_wbs_node_id == NODE
    assert candidate.state is TechnicalLinkState.HUMAN_REVIEW_REQUIRED
    assert candidate.assessment == "NOT_ASSESSED"
    assert candidate.is_approved_link is False


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"actor_tenant_id": uuid4()}, "authorized project"),
        ({"clause": replace(_clause(), project_id=uuid4())}, "authorized project"),
        ({"clause": replace(_clause(), tenant_id=uuid4())}, "authorized project"),
        ({"trusted_current_revision_id": None}, "trusted-current"),
        ({"trusted_current_revision_id": uuid4()}, "trusted-current"),
        ({"clause": replace(_clause(), revision_id=None)}, "trusted-current"),
        ({"clause": replace(_clause(), revision_id=uuid4())}, "trusted-current"),
        ({"clause": replace(_clause(), extraction_model=None)}, "provenance"),
        ({"approved_wbs_scope": None}, "approved scope"),
        ({"proposed_wbs_node_id": uuid4()}, "approved scope"),
        ({"approved_wbs_scope": replace(_scope(), tenant_id=uuid4())}, "approved scope"),
        ({"approved_wbs_scope": replace(_scope(), project_id=uuid4())}, "approved scope"),
        ({"parsed_revision_text": RAW_TEXT.replace("35 MPa", "45 MPa")}, "source span"),
        ({"clause": replace(_clause(), text_end_offset=START + 5)}, "source span"),
    ],
)
def test_invalid_authority_or_provenance_fail_closed(overrides: dict, reason: str) -> None:
    with pytest.raises(TechnicalWBSLinkCandidateError, match=reason):
        _preview(**overrides)


def test_claimed_section_does_not_authorize_a_link() -> None:
    source = _clause()
    source.extracted_entities["technical_requirement"]["source_section"] = "9.9"
    with pytest.raises(TechnicalWBSLinkCandidateError, match="provenance"):
        _preview(clause=source)


def test_unverified_source_stays_unapproved_even_when_clause_was_reviewed() -> None:
    clause = replace(_clause(), manually_verified=True, verified_at=STAMP)
    candidate = _preview(clause=clause)
    assert candidate.state is TechnicalLinkState.HUMAN_REVIEW_REQUIRED
    assert not candidate.is_approved_link
    assert candidate.assessment == "NOT_ASSESSED"


def test_matching_forged_section_codes_are_rejected_against_original_heading() -> None:
    """Both metadata fields may lie together; the immutable source overrides them."""
    clause = replace(_clause(), clause_code="9.9")
    clause.extracted_entities["technical_requirement"]["source_section"] = "9.9"
    with pytest.raises(TechnicalWBSLinkCandidateError, match="source heading"):
        _preview(clause=clause)


def test_requirement_window_after_a_long_heading_still_recovers_true_source_section() -> None:
    section = (
        "Section 6.2 " + "Background information only. " * 180
        + "The concrete shall withstand 50 MPa."
    )
    raw = "Preamble\n" + section
    obligation = raw.index("shall withstand")
    start = obligation - 12  # the extractor may window in after 4,000 chars
    excerpt = raw[start : start + 120]
    clause = replace(
        _clause(),
        clause_code="6.2",
        title=excerpt,
        full_text=excerpt,
        text_start_offset=start,
        text_end_offset=start + len(excerpt),
    )
    clause.extracted_entities["technical_requirement"]["source_section"] = "6.2"
    candidate = _preview(clause=clause, parsed_revision_text=raw)
    assert candidate.source_section == "6.2"
    assert candidate.source_start_offset == start
    assert candidate.is_approved_link is False


def test_requirement_span_must_not_cross_two_distinct_source_sections() -> None:
    source = RAW_TEXT + "\nSection 5.1 Additional concrete obligations must be checked."
    clause = replace(
        _clause(),
        text_end_offset=len(source),
        full_text=source[START:],
    )
    with pytest.raises(TechnicalWBSLinkCandidateError, match="crosses source sections"):
        _preview(clause=clause, parsed_revision_text=source)


def test_crlf_heading_keeps_full_hierarchical_code_not_parent() -> None:
    full = "Section 4.1.2\r\nConcrete shall exceed 35 MPa."
    clause = replace(
        _clause(),
        full_text=full,
        text_start_offset=0,
        text_end_offset=len(full),
    )
    candidate = _preview(clause=clause, parsed_revision_text=full)
    assert candidate.source_section == "4.1.2"


def test_crlf_heading_does_not_allow_forged_parent_section_code() -> None:
    full = "Section 4.1.2\r\nConcrete shall exceed 35 MPa."
    clause = replace(
        _clause(),
        clause_code="4.1",
        full_text=full,
        text_start_offset=0,
        text_end_offset=len(full),
    )
    clause.extracted_entities["technical_requirement"]["source_section"] = "4.1"
    with pytest.raises(TechnicalWBSLinkCandidateError, match="source heading"):
        _preview(clause=clause, parsed_revision_text=full)


def test_overdepth_heading_never_backtracks_to_false_parent() -> None:
    full = "Section 1.2.3.4.5.6.7.8\r\nThe steel shall comply."
    clause = replace(
        _clause(),
        clause_code="1.2.3.4.5.6.7",
        full_text=full,
        text_start_offset=0,
        text_end_offset=len(full),
    )
    clause.extracted_entities["technical_requirement"]["source_section"] = "1.2.3.4.5.6.7"
    with pytest.raises(TechnicalWBSLinkCandidateError, match="source heading"):
        _preview(clause=clause, parsed_revision_text=full)


def test_unsupported_heading_revokes_preceding_section_authority() -> None:
    """A 4.1.2 source cannot claim evidence actually below an unsupported heading."""
    source = (
        "Section 4.1.2 Valid section.\n"
        "Old background content.\n"
        "Section 1.2.3.4.5.6.7.8\r\n"
        "The steel shall comply with B500S."
    )
    fragment = "The steel shall comply with B500S."
    start = source.index(fragment)
    clause = replace(
        _clause(),
        full_text=fragment,
        text_start_offset=start,
        text_end_offset=start + len(fragment),
    )
    with pytest.raises(TechnicalWBSLinkCandidateError, match="source heading"):
        _preview(clause=clause, parsed_revision_text=source)


def test_span_crossing_an_unsupported_heading_is_rejected() -> None:
    source = (
        "Section 4.1.2 The steel shall comply with B500S.\n"
        "Section 1.2.3.4.5.6.7.8\r\n"
        "Concrete shall exceed 35 MPa."
    )
    clause = replace(
        _clause(),
        full_text=source,
        text_start_offset=0,
        text_end_offset=len(source),
    )
    with pytest.raises(TechnicalWBSLinkCandidateError, match="crosses source sections"):
        _preview(clause=clause, parsed_revision_text=source)


def test_overlong_heading_is_a_boundary_not_previous_section() -> None:
    source = (
        "Section 4.1.2 Valid section.\n"
        "Sección 1234.2\r\n"
        "El acero deberá ser B500S."
    )
    fragment = "El acero deberá ser B500S."
    start = source.index(fragment)
    clause = replace(
        _clause(),
        full_text=fragment,
        text_start_offset=start,
        text_end_offset=start + len(fragment),
    )
    with pytest.raises(TechnicalWBSLinkCandidateError, match="source heading"):
        _preview(clause=clause, parsed_revision_text=source)


def test_parenthesized_unsupported_code_is_never_truncated_into_parent() -> None:
    full = "Section 1.2.3.4.5.6.7.8)\nSteel shall comply."
    clause = replace(
        _clause(),
        clause_code="1.2.3.4.5.6.7",
        full_text=full,
        text_start_offset=0,
        text_end_offset=len(full),
    )
    clause.extracted_entities["technical_requirement"]["source_section"] = "1.2.3.4.5.6.7"
    with pytest.raises(TechnicalWBSLinkCandidateError, match="source heading"):
        _preview(clause=clause, parsed_revision_text=full)


def test_parenthesized_unsupported_code_blocks_previous_section_source() -> None:
    source = (
        "Section 4.1.2 Valid heading.\n"
        "Section 1234)\n"
        "Steel shall comply."
    )
    fragment = "Steel shall comply."
    start = source.index(fragment)
    clause = replace(
        _clause(),
        full_text=fragment,
        text_start_offset=start,
        text_end_offset=start + len(fragment),
    )
    with pytest.raises(TechnicalWBSLinkCandidateError, match="source heading"):
        _preview(clause=clause, parsed_revision_text=source)


def test_supported_parenthesized_heading_preserves_source_code() -> None:
    source = "Section 4.1.2)\nConcrete shall exceed 35 MPa."
    clause = replace(
        _clause(),
        full_text=source,
        text_start_offset=0,
        text_end_offset=len(source),
    )
    candidate = _preview(clause=clause, parsed_revision_text=source)
    assert candidate.source_section == "4.1.2"
