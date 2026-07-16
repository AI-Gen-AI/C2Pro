"""Test Suite ID: TASK-OPS-DOCFLOW-007.

Real document extraction contract for clauses, risks, and categories.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from src.analysis.adapters.graph.schema import ProjectState
from src.core.tasks.ingestion_tasks import _extract_contract_clauses
from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser
from src.documents.domain.models import Document, DocumentStatus, DocumentType

CORPUS_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "documents" / "real"
MANIFEST_PATH = CORPUS_DIR / "manifest.yaml"


def _corpus_entry(document_type: str) -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return next(entry for entry in manifest if entry["document_type"] == document_type)


def _state_from_text(parsed_text: str) -> ProjectState:
    return {
        "project_id": str(uuid4()),
        "document_id": str(uuid4()),
        "document_text": parsed_text,
        "doc_type": "contract",
        "messages": [],
        "extracted_risks": [],
        "extracted_wbs": [],
        "confidence_score": 0.0,
        "critique_notes": "",
        "human_feedback": "",
        "retry_count": 0,
        "tenant_id": str(uuid4()),
        "analysis_id": None,
        "human_approval_required": False,
        "document_parsed": False,
        "document_category": "",
        "anonymized_text": "",
        "pii_redactions": [],
        "extracted_stakeholders": [],
        "raci_matrix": [],
        "coherence_score": 0,
        "coherence_reason": None,
        "coherence_missing_dimensions": [],
        "coherence_breakdown": {},
        "bom_items": [],
        "knowledge_graph_nodes": [],
        "knowledge_graph_edges": [],
        "decision_package": {},
        "citations": [],
        "citation_validation_passed": False,
        "final_report": {},
    }


@pytest.mark.asyncio
async def test_real_pdf_extracts_structured_clauses_risks_and_wbs_categories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = _corpus_entry("construction_contract")
    fixture_path = CORPUS_DIR / entry["filename"]
    document_id = uuid4()
    project_id = uuid4()
    tenant_id = uuid4()
    document = Document(
        id=document_id,
        project_id=project_id,
        tenant_id=tenant_id,
        document_type=DocumentType.CONTRACT,
        filename=entry["filename"],
        upload_status=DocumentStatus.UPLOADED,
        file_format=".pdf",
        file_size_bytes=fixture_path.stat().st_size,
    )

    parsed_payload = await CompositeFileParser.create().parse_document_file(
        document,
        fixture_path,
    )
    parsed_text = "\n".join(block["text"] for block in parsed_payload["text_blocks"])
    assert len(parsed_text) >= entry["expected_min_text_chars"]

    from src.analysis.adapters.graph import nodes, nodes_extended

    state = _state_from_text(parsed_text)
    state = await nodes_extended.pii_anonymizer_node(state)

    clauses = _extract_contract_clauses(
        document_id=document_id,
        project_id=project_id,
        tenant_id=tenant_id,
        parsed_text=state["anonymized_text"],
    )
    clause_categories = {
        category
        for clause in clauses
        for category in clause.extracted_entities.get("affected_categories", [])
    }

    monkeypatch.setenv("C2PRO_AI_MOCK", "1")
    extraction_state = await nodes.risk_extractor_node(state)
    extraction_state = await nodes.wbs_extractor_node(extraction_state)
    risk_categories = {
        str(risk.get("category", "")).upper()
        for risk in extraction_state["extracted_risks"]
        if risk.get("category")
    }

    assert clauses
    assert all(clause.full_text for clause in clauses)
    assert set(entry["expected_clause_categories"]) <= clause_categories
    assert set(entry["expected_risk_categories"]) <= risk_categories
    assert extraction_state["extracted_wbs"]
    assert all(item.get("code") and item.get("name") for item in extraction_state["extracted_wbs"])
