"""ACC-01 D2: source-bound technical requirements, not invented coverage."""

from uuid import uuid4

from src.documents.application.technical_requirement_clauses import (
    extract_technical_requirement_clauses,
)
from src.documents.domain.models import ClauseType


def _extract(text: str, *, revision_id=None):
    return extract_technical_requirement_clauses(
        document_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        parsed_text=text,
        revision_id=revision_id,
    )


def test_two_real_sections_preserve_literal_source_offsets_and_revision() -> None:
    revision = uuid4()
    text = (
        "Introductory text with no technical claim.\n\n"
        "Section 4.1.2 Concrete compressive strength shall exceed 35 MPa at 28 days.\n\n"
        "Section 4.2 Reinforcement steel shall be B500S.\n"
    )
    clauses = _extract(text, revision_id=revision)
    assert [clause.clause_code for clause in clauses] == ["4.1.2", "4.2"]
    for clause in clauses:
        assert clause.text_start_offset is not None
        assert clause.text_end_offset is not None
        assert text[clause.text_start_offset : clause.text_end_offset] == clause.full_text
        assert clause.revision_id == revision
        assert clause.clause_type == ClauseType.OTHER
        assert clause.extraction_confidence is None
        assert (
            clause.extracted_entities["technical_requirement"]["verification_status"]
            == "unverified"
        )
        assert clause.extracted_entities["evidence_location"] == {
            "revision_id": str(revision),
            "page_number": None,
            "page_numbers": [],
            "bbox": None,
            "normalized": False,
        }
        assert clause.extracted_entities.get("wbs_node_id") is None


def test_span_is_separated_at_next_header_not_reference_in_body() -> None:
    revision = uuid4()
    text = (
        "Sección 5.1 El hormigón deberá soportar 45 MPa, de acuerdo con la sección 5.2.\n"
        "Las muestras deben ensayarse a los 28 días.\n"
        "Apartado 5.2 El acero debe ser B500S.\n"
    )
    clauses = _extract(text, revision_id=revision)
    assert [clause.clause_code for clause in clauses] == ["5.1", "5.2"]
    assert "Las muestras" in clauses[0].full_text
    assert "Apartado 5.2" not in clauses[0].full_text
    assert clauses[1].full_text.startswith("Apartado 5.2")


def test_no_fabricated_evidence_from_heading_only_or_unstructured_prose() -> None:
    revision = uuid4()
    assert _extract("Section 5.2 General information only.", revision_id=revision) == []
    assert _extract(
        "The supplier shall comply with section 5.2 according to standards.",
        revision_id=revision,
    ) == []
    assert (
        _extract("Section 3.1 The applicable definition is provided.", revision_id=revision)
        == []
    )


def test_unpinned_source_produces_no_canonical_technical_clauses() -> None:
    source = "Section 4.2 Reinforcement steel shall be B500S."
    assert _extract(source, revision_id=None) == []
    assert len(_extract(source, revision_id=uuid4())) == 1


def test_document_source_is_not_claimed_to_be_human_approved() -> None:
    revision = uuid4()
    clauses = _extract(
        "Section 2.1 The installation shall withstand wind loads of 100 km/h.",
        revision_id=revision,
    )
    assert len(clauses) == 1
    clause = clauses[0]
    assert clause.manually_verified is False
    assert clause.verified_at is None
    assert (
        clause.extracted_entities["technical_requirement"]["verification_status"]
        == "unverified"
    )


def test_large_section_preserves_the_qualifying_obligation_and_exact_offsets() -> None:
    revision = uuid4()
    source = (
        "Section 10.1 " + ("Engineering background information. " * 160)
        + "\nThe reinforcement steel shall be B500S."
    )
    [clause] = _extract(source, revision_id=revision)
    assert len(source) > 4000
    assert "shall be B500S" in clause.full_text
    assert clause.text_start_offset is not None
    assert clause.text_end_offset is not None
    assert source[clause.text_start_offset : clause.text_end_offset] == clause.full_text
    assert clause.extracted_entities["technical_requirement"]["source_section"] == "10.1"


def test_crlf_preserves_full_numbered_source_section() -> None:
    revision = uuid4()
    source = "Section 4.1.2\r\nConcrete shall exceed 35 MPa."
    [clause] = _extract(source, revision_id=revision)
    assert clause.clause_code == "4.1.2"
    assert source[clause.text_start_offset:clause.text_end_offset] == clause.full_text


def test_truncated_parent_of_overdepth_heading_is_not_evidence() -> None:
    revision = uuid4()
    source = "Section 1.2.3.4.5.6.7.8\r\nConcrete shall exceed 35 MPa."
    assert _extract(source, revision_id=revision) == []


def test_heading_with_terminal_dot_has_full_source_code() -> None:
    revision = uuid4()
    source = "Section 4.1.2.\r\nSteel must comply with B500S."
    [clause] = _extract(source, revision_id=revision)
    assert clause.clause_code == "4.1.2"


def test_unsupported_heading_still_terminates_preceding_section() -> None:
    """An obligation below an unsupported heading never belongs to Section 9."""
    revision = uuid4()
    source = (
        "Section 9 General background only.\r\n"
        "Section 1.2.3.4.5.6.7.8\r\n"
        "Concrete shall exceed 35 MPa."
    )
    assert _extract(source, revision_id=revision) == []


def test_unsupported_heading_between_supported_sections_preserves_true_identity() -> None:
    revision = uuid4()
    source = (
        "Section 4.1.2 The steel shall comply with B500S.\n"
        "Section 1.2.3.4.5.6.7.8\n"
        "Concrete shall exceed 35 MPa.\n"
        "Apartado 4.2 El cemento deberá cumplir la normativa vigente."
    )
    clauses = _extract(source, revision_id=revision)
    assert [c.clause_code for c in clauses] == ["4.1.2", "4.2"]
    assert "Concrete shall exceed 35 MPa" not in clauses[0].full_text
    assert all(c.full_text in source for c in clauses)


def test_overlong_code_still_ends_preceding_source_section() -> None:
    revision = uuid4()
    source = (
        "Section 9 Background information for all disciplines.\n"
        "Sección 1234.2\n"
        "The concrete must comply with B500S."
    )
    assert _extract(source, revision_id=revision) == []


def test_closing_parenthesis_preserves_full_unsupported_section_as_boundary() -> None:
    revision = uuid4()
    source = (
        "Section 9 General background only.\n"
        "Section 1.2.3.4.5.6.7.8)\n"
        "Steel shall comply with B500S."
    )
    assert _extract(source, revision_id=revision) == []


def test_closing_parenthesis_after_overlong_code_is_also_boundary() -> None:
    revision = uuid4()
    source = (
        "Section 9 General background only.\n"
        "Section 1234)\n"
        "Steel shall comply with B500S."
    )
    assert _extract(source, revision_id=revision) == []


def test_supported_heading_with_closing_parenthesis_can_be_extracted() -> None:
    revision = uuid4()
    source = "Apartado 4.1.2) El acero deberá ser B500S."
    [clause] = _extract(source, revision_id=revision)
    assert clause.clause_code == "4.1.2"
    assert source[clause.text_start_offset:clause.text_end_offset] == clause.full_text
