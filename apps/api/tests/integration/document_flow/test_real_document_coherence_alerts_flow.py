"""Test Suite ID: TASK-OPS-DOCFLOW-008.

Real document coherence score and alerts contract for the operability gate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from src.analysis.adapters.graph.schema import ProjectState
from src.coherence.domain.v2_constants import SCORE_VERSION_V1
from src.coherence.graph.graph import evaluate_coherence_async
from src.coherence.graph.state import EvaluationConfig
from src.coherence.models import Clause as CoherenceClause
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


def _alert_category_to_manifest_category(category: str) -> str:
    mapping = {
        "schedule": "TIME",
        "financial": "BUDGET",
        "legal": "LEGAL",
        "scope": "SCOPE",
        "technical": "TECHNICAL",
        "quality": "QUALITY",
        "general": "GENERAL",
    }
    return mapping.get(category, category.upper())


@pytest.mark.asyncio
async def test_real_pdf_produces_v1_coherence_score_missing_dims_and_alerts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_langchain_tracing(monkeypatch)

    entry = _corpus_entry("construction_contract")
    fixture_path = CORPUS_DIR / entry["filename"]
    await _exercise_real_coherence_contract(entry, fixture_path)


def _disable_langchain_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_CALLBACKS_BACKGROUND", "false")
    try:
        from langsmith import run_helpers as langsmith_run_helpers
        from langsmith import utils as langsmith_utils

        monkeypatch.setattr(
            langsmith_run_helpers,
            "get_tracing_context",
            lambda: {"parent": None, "project_name": None, "enabled": False},
            raising=False,
        )
        monkeypatch.setattr(langsmith_utils, "tracing_is_enabled", lambda: False, raising=False)
    except Exception:
        pass

    try:
        from langchain_core.tracers import context as langchain_tracing_context

        monkeypatch.setattr(
            langchain_tracing_context,
            "_get_tracer_project",
            lambda: "disabled",
            raising=False,
        )
    except Exception:
        pass


async def _exercise_real_coherence_contract(entry: dict[str, Any], fixture_path: Path) -> None:
    document_id = uuid4()
    project_id = uuid4()
    document = Document(
        id=document_id,
        project_id=project_id,
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

    from src.analysis.adapters.graph import nodes_extended

    state = await nodes_extended.pii_anonymizer_node(_state_from_text(parsed_text))
    domain_clauses = _extract_contract_clauses(
        document_id=document_id,
        project_id=project_id,
        parsed_text=state["anonymized_text"],
    )
    coherence_clauses = [
        CoherenceClause(
            id=str(clause.id),
            text=clause.full_text or "",
            data={
                **clause.extracted_entities,
                "document_type": "contract",
                "clause_type": clause.clause_type.value if clause.clause_type else None,
            },
        )
        for clause in domain_clauses
    ]

    result = await evaluate_coherence_async(
        clauses=coherence_clauses,
        project_id=str(project_id),
        config=EvaluationConfig(
            low_budget_mode=True,
            include_rag_similarity=False,
            tenant_id=str(uuid4()),
            project_id=str(project_id),
        ),
    )

    expected_min, expected_max = entry["expected_score_range"]
    alert_categories = {
        _alert_category_to_manifest_category(str(alert.category))
        for alert in result.alerts
    }
    alert_severities = {str(alert.severity) for alert in result.alerts}

    assert result.score_version == SCORE_VERSION_V1
    assert result.overall_score is not None
    assert expected_min <= result.overall_score <= expected_max
    assert result.score_reason is None
    # Honest scoring (TASK-BCK-060): score_missing_dimensions is now derived
    # from the per-category coverage map (canonical categories that had no
    # evaluator actually run) instead of the old doc-type heuristic that
    # always returned ["schedule", "budget"]. A contract-only upload cannot
    # assess every dimension, so this must be a non-empty subset of the six
    # canonical categories.
    _CANON = {"SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"}
    assert result.score_missing_dimensions
    assert set(result.score_missing_dimensions).issubset(_CANON)
    assert result.category_breakdown
    assert result.alerts
    for expected_alert in entry["expected_alerts"]:
        assert expected_alert["category"] in alert_categories
        assert expected_alert["severity"] in alert_severities
