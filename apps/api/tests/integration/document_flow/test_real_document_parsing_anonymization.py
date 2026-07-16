"""Test Suite ID: TASK-OPS-DOCFLOW-006.

Real document parsing and anonymization contract for the operability gate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.graph.schema import ProjectState
from src.documents.adapters.http.router import get_storage_service
from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.adapters.storage.local_file_storage_service import (
    LocalFileStorageService,
)
from src.documents.domain.models import Document, DocumentStatus

CORPUS_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "documents" / "real"
MANIFEST_PATH = CORPUS_DIR / "manifest.yaml"
EXPECTED_PII_EMAIL = "privacy.officer@example.com"


class _CapturingAI:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def run_extraction(self, system_prompt: str, user_content: str) -> Any:
        self.calls.append((system_prompt, user_content))
        return {"items": [{"name": "Redaction-safe budget item", "amount": 1.0}]}


def _corpus_entry(document_type: str) -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return next(entry for entry in manifest if entry["document_type"] == document_type)


def _state_from_parsed_text(
    *,
    document_id: UUID,
    project_id: UUID,
    tenant_id: UUID,
    parsed_text: str,
) -> ProjectState:
    return {
        "project_id": str(project_id),
        "document_id": str(document_id),
        "document_text": parsed_text,
        "doc_type": "budget",
        "messages": [],
        "extracted_risks": [],
        "extracted_wbs": [],
        "confidence_score": 0.0,
        "critique_notes": "",
        "human_feedback": "",
        "retry_count": 0,
        "tenant_id": str(tenant_id),
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


def _to_domain_document(row: DocumentORM) -> Document:
    return Document(
        id=row.id,
        project_id=row.project_id,
        tenant_id=row.tenant_id,
        document_type=row.document_type,
        filename=row.filename,
        upload_status=row.upload_status,
        file_format=row.file_format,
        storage_url=row.storage_url,
        storage_encrypted=row.storage_encrypted,
        file_size_bytes=row.file_size_bytes,
        parsed_at=row.parsed_at,
        parsing_error=row.parsing_error,
        retention_until=row.retention_until,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        document_metadata=row.document_metadata or {},
    )


@pytest.mark.asyncio
async def test_uploaded_real_pdf_is_parsed_and_redacted_before_ai_analysis(
    app,
    client: AsyncClient,
    db: AsyncSession,
    get_auth_headers,
    test_user,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = _corpus_entry("construction_contract")
    fixture_path = CORPUS_DIR / entry["filename"]
    upload_dir = tmp_path / "real-document-parse-anonymize"
    app.dependency_overrides[get_storage_service] = lambda: LocalFileStorageService(
        base_dir=upload_dir
    )
    headers = get_auth_headers(user=test_user)

    project_response = await client.post(
        "/api/v1/projects",
        json={
            "name": "Real Document Parse Anonymization Project",
            "project_type": "construction",
        },
        headers=headers,
    )
    assert project_response.status_code == 201, project_response.text
    project_id = UUID(project_response.json()["id"])

    try:
        with fixture_path.open("rb") as fixture_file:
            upload_response = await client.post(
                f"/api/v1/projects/{project_id}/documents",
                files={
                    "file": (
                        entry["filename"],
                        fixture_file,
                        entry["expected_upload"]["content_type"],
                    )
                },
                data={"document_type": "contract"},
                headers=headers,
            )
    finally:
        app.dependency_overrides.pop(get_storage_service, None)

    assert upload_response.status_code == 202, upload_response.text
    document_id = UUID(upload_response.json()["id"])
    document_row = (
        await db.execute(select(DocumentORM).where(DocumentORM.id == document_id))
    ).scalar_one()
    assert document_row.upload_status == DocumentStatus.UPLOADED
    assert document_row.storage_url is not None

    parsed_payload = await CompositeFileParser.create().parse_document_file(
        _to_domain_document(document_row),
        Path(document_row.storage_url),
    )
    text_blocks = parsed_payload["text_blocks"]
    parsed_text = "\n".join(block["text"] for block in text_blocks)

    assert len(parsed_text) >= entry["expected_min_text_chars"]
    assert text_blocks
    assert all({"text", "bbox", "page"} <= set(block) for block in text_blocks)
    assert EXPECTED_PII_EMAIL in parsed_text

    from src.analysis.adapters.graph import nodes_extended

    state = _state_from_parsed_text(
        document_id=document_id,
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        parsed_text=parsed_text,
    )
    anonymized_state = await nodes_extended.pii_anonymizer_node(state)

    assert EXPECTED_PII_EMAIL not in anonymized_state["anonymized_text"]
    assert "[REDACTED]" in anonymized_state["anonymized_text"]
    assert any(
        redaction["text"] == EXPECTED_PII_EMAIL and redaction["type"] == "EMAIL"
        for redaction in anonymized_state["pii_redactions"]
    )

    ai = _CapturingAI()
    monkeypatch.setattr(
        nodes_extended,
        "get_ai_service",
        lambda tenant_id: ai,
        raising=False,
    )

    await nodes_extended.budget_parser_extended_node(anonymized_state)

    assert ai.calls
    assert ai.calls[0][1] == anonymized_state["anonymized_text"]
    assert EXPECTED_PII_EMAIL not in ai.calls[0][1]
