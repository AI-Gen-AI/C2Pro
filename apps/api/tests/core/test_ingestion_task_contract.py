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
