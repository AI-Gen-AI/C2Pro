"""DocumentArtifact builder tests (ADR-017 / TASK-V3-017-01).

TS-UT-ADR017-DA-001
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.analysis.domain.contracts import DocumentArtifact


def test_representative_tier1_state_builds_valid_document_artifact() -> None:
    from src.analysis.adapters.graph.document_artifact_builder import (
        build_document_artifact,
    )

    artifact = build_document_artifact(
        {
            "document_id": "doc-1",
            "document_revision_id": "rev-1",
            "doc_type": "contract",
            "document_category": "LEGAL",
            "extracted_risks": [
                {
                    "title": "Delay penalty",
                    "description": "Liquidated damages exposure",
                    "impact": "HIGH",
                    "confidence": 0.8,
                }
            ],
            "extracted_wbs": [{"code": "1.1", "name": "Mobilization"}],
            "bom_items": [{"name": "Concrete", "amount": 1250.0, "currency": "EUR"}],
            "citations": [
                {
                    "type": "risk",
                    "item": "Delay penalty",
                    "quote": "LD applies",
                    "found_in_source": True,
                }
            ],
            "coherence_findings": [
                {
                    "category": "LEGAL",
                    "message": "Penalty terms cited",
                    "severity": "LOW",
                    "score": 80.0,
                    "confidence": 0.7,
                }
            ],
            "confidence_score": 0.76,
            "pii_redactions": [{"kind": "email"}, {"kind": "phone"}],
        }
    )

    assert artifact.document_id == "doc-1"
    assert artifact.document_revision_id == "rev-1"
    assert artifact.doc_type == "contract"
    assert artifact.document_category == "LEGAL"
    assert artifact.extracted_risks[0].severity.value == "HIGH"
    assert artifact.extracted_wbs[0].code == "1.1"
    assert artifact.bom_items[0].amount == 1250.0
    assert artifact.citations[0].found_in_source is True
    assert artifact.coherence_findings[0].score == 80.0
    assert artifact.confidence_score == 0.76
    assert artifact.pii_redaction_count == 2


def test_builder_ignores_source_drift_but_artifact_rejects_extra_fields() -> None:
    from src.analysis.adapters.graph.document_artifact_builder import (
        build_document_artifact,
    )

    artifact = build_document_artifact(
        {
            "document_id": "doc-2",
            "doc_type": "contract",
            "unexpected_pipeline_field": "ignored at adapter boundary",
        }
    )

    assert artifact.document_id == "doc-2"
    assert artifact.extracted_risks == []
    with pytest.raises(ValidationError):
        DocumentArtifact(document_id="doc-2", doc_type="contract", unexpected="blocked")


def test_partial_state_builds_honest_null_artifact() -> None:
    from src.analysis.adapters.graph.document_artifact_builder import (
        build_document_artifact,
    )

    artifact = build_document_artifact({})

    assert artifact.document_id == ""
    assert artifact.document_revision_id is None
    assert artifact.doc_type == "unknown"
    assert artifact.document_category is None
    assert artifact.extracted_risks == []
    assert artifact.extracted_wbs == []
    assert artifact.bom_items == []
    assert artifact.citations == []
    assert artifact.coherence_findings == []
    assert artifact.confidence_score is None
    assert artifact.pii_redaction_count == 0
