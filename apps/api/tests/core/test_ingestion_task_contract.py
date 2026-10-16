"""
TS-INT-DOC-PROC-002: Ingestion task contract tests.
"""

from __future__ import annotations

from uuid import uuid4

from src.core.tasks.ingestion_tasks import _build_processing_details, _extract_contract_clauses


def test_build_processing_details_marks_parsed_as_pre_analysis() -> None:
    details = _build_processing_details({"stakeholders": 2})

    assert details["processing_stage"] == "parsed_pending_analysis"
    assert details["analysis_status"] == "queued"
    assert "analysis orchestration queued" in details["status_detail"].lower()
    assert details["extraction_summary"] == {"stakeholders": 2}


def test_extract_contract_clauses_groups_numbered_clauses_not_sentences() -> None:
    """Contract is split at clause boundaries (numbered/ordinal/keyword), not per sentence."""
    text = (
        "CONTRATO ADMINISTRATIVO DE OBRAS entre la Administracion y la Empresa "
        "contratista. En Alicante, a 8 de enero de 2015.\n\n"
        "ESTIPULACIONES\n\n"
        "1.- El contrato se ejecutara con estricta sujecion al pliego de clausulas. "
        "El director facultativo dara instrucciones al contratista.\n\n"
        "2.- El contratista esta obligado a cumplir el plazo de ejecucion del contrato. "
        "El incumplimiento del plazo conllevara penalizaciones economicas.\n\n"
        "3.- La ejecucion se realizara a riesgo y ventura del contratista del proyecto.\n\n"
    )
    clauses = _extract_contract_clauses(
        document_id=uuid4(), project_id=uuid4(), tenant_id=uuid4(), parsed_text=text
    )

    assert clauses
    assert all(c.full_text for c in clauses)
    # Each numbered clause is ONE clause carrying its whole body (both sentences),
    # not one clause per sentence.
    clause1 = next(c for c in clauses if c.full_text.startswith("1.-"))
    assert "director facultativo" in clause1.full_text
    assert any(c.full_text.startswith("2.-") for c in clauses)
    assert any(c.full_text.startswith("3.-") for c in clauses)
    # Far fewer than the ~7 sentence-fragments the old splitter produced.
    assert len(clauses) <= 5


def test_explicit_clause_heading_codes_survive_deterministic_ingestion() -> None:
    text = (
        "5.2.- The Contractor shall rectify all defects within fourteen days of notice, "
        "without undue delay and at its own cost.\n\n"
        "6.3.- Payment terms require certification and settlement within thirty days, "
        "with withholding only where expressly permitted.\n\n"
        "The Contractor remains responsible under clause 6.4 for site handover "
        "and all costs including storage and delivery of materials.\n\n"
        "1.- Notices must be made in writing to the address specified in the contract, "
        "and are deemed received upon acknowledgement."
    )
    clauses = _extract_contract_clauses(
        document_id=uuid4(), project_id=uuid4(), tenant_id=uuid4(), parsed_text=text
    )
    assert [c.clause_code for c in clauses] == ["5.2", "6.3", "1"]
    for clause in clauses:
        assert text[clause.text_start_offset:clause.text_end_offset] == clause.full_text


def test_unlabeled_or_nonheading_numeric_text_does_not_promote_a_source_code() -> None:
    text = (
        "The rate is 5.2 percent per month and payments are due within fourteen days "
        "of receiving the full and final engineer certification."
    )
    clauses = _extract_contract_clauses(
        document_id=uuid4(), project_id=uuid4(), tenant_id=uuid4(), parsed_text=text
    )
    assert len(clauses) == 1
    assert clauses[0].clause_code == "AUTO-001"


def test_nested_heading_without_hyphen_is_retained_when_a_separate_paragraph() -> None:
    text = (
        "6.3 Payment terms require certification and settlement within thirty days, "
        "unless the parties have agreed to a longer period expressly in writing."
    )
    clauses = _extract_contract_clauses(
        document_id=uuid4(), project_id=uuid4(), tenant_id=uuid4(), parsed_text=text
    )
    assert len(clauses) == 1
    assert clauses[0].clause_code == "6.3"


def test_mixed_article_and_single_line_numeric_headings_each_get_their_own_clause() -> None:
    text = (
        "ARTICLE 6 – General conditions for the execution of the Works.\n"
        "6.1 Definitions establish the obligations of each party and define the "
        "scope of services, responsibilities and timing of acceptance.\n"
        "6.3 Payment shall follow certification within thirty calendar days "
        "of the Engineer's receipt of supporting information.\n"
        "6.4 Notice must be sent in writing as described in the Contract "
        "within the timeframes applicable to each claim."
    )
    clauses = _extract_contract_clauses(
        document_id=uuid4(), project_id=uuid4(), tenant_id=uuid4(), parsed_text=text
    )
    assert [clause.clause_code for clause in clauses] == ["6", "6.1", "6.3", "6.4"]
    for clause in clauses:
        assert text[clause.text_start_offset:clause.text_end_offset] == clause.full_text


def test_decimal_prose_is_not_promoted_to_clause_even_near_real_heading() -> None:
    text = (
        "5.2 percent interest applies when payment is delayed by more than "
        "thirty days after a valid invoice is received.\n"
        "6.3 Payment conditions must be reviewed by the Engineer before any "
        "payment certificate can be issued."
    )
    clauses = _extract_contract_clauses(
        document_id=uuid4(), project_id=uuid4(), tenant_id=uuid4(), parsed_text=text
    )
    assert [c.clause_code for c in clauses] == ["AUTO-001", "6.3"]


def test_explicit_keyword_labelled_clause_number_is_preserved() -> None:
    text = (
        "SECTION 5.2 Defect rectification is the obligation of the Contractor "
        "and all rectification work is at the Contractor's cost."
    )
    clauses = _extract_contract_clauses(
        document_id=uuid4(), project_id=uuid4(), tenant_id=uuid4(), parsed_text=text
    )
    assert len(clauses) == 1
    assert clauses[0].clause_code == "5.2"


def test_single_level_numbered_headings_are_preserved_without_guessing_prose() -> None:
    text = (
        "6. Payment Terms require certification of all invoices within thirty "
        "calendar days of receipt of the supporting documents.\n"
        "7 General Conditions govern the responsibilities of the Engineer "
        "and the Contractor and describe written notice requirements.\n"
        "8.1 Termination Rights define the grounds and conditions under which "
        "either party may lawfully terminate the Contract."
    )
    clauses = _extract_contract_clauses(
        document_id=uuid4(), project_id=uuid4(), tenant_id=uuid4(), parsed_text=text
    )
    assert [clause.clause_code for clause in clauses] == ["6", "7", "8.1"]
    for clause in clauses:
        assert text[clause.text_start_offset:clause.text_end_offset] == clause.full_text


def test_quantity_prefix_is_not_single_level_clause_heading() -> None:
    text = (
        "5 Percent interest applies to outstanding sums under this "
        "agreement, calculated on each calendar month until final payment."
    )
    clauses = _extract_contract_clauses(
        document_id=uuid4(), project_id=uuid4(), tenant_id=uuid4(), parsed_text=text
    )
    assert len(clauses) == 1
    assert clauses[0].clause_code == "AUTO-001"
