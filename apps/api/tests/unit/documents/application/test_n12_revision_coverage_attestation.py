"""N12 revision-anchored source coverage: parser claims are not an attestation."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.analysis.domain.n12_source_attestation import is_n12_source_attestation_valid
from src.documents.application.document_coverage import (
    build_n12_source_attestation,
    record_revision_document_coverage,
    record_revision_parsed_text_digest,
)

TEXT = "EPC-05: Contractor shall pay delay damages of 1% per week."


def _fixture(*, status="COMPLETE", assurance="verified_full_source_text"):
    tenant, project, doc, rev = (uuid4() for _ in range(4))
    metadata: dict = {}
    coverage = {
        "status": status,
        "origin": "docx_file_parser",
        "limitations": [],
        "known_omissions": [],
        "text_coverage_assurance": assurance,
    }
    record_revision_document_coverage(
        metadata,
        parsed_payload={"document_coverage": coverage, "text_blocks": [
            {"text": TEXT, "page": 1},
        ]},
        revision_id=rev,
        blob_hash="a" * 64,
    )
    record_revision_parsed_text_digest(metadata, parsed_text=TEXT, revision_id=rev)
    metadata["parsed_text"] = TEXT
    metadata["parsed_text_revision_id"] = str(rev)
    revision = SimpleNamespace(
        revision_id=rev, tenant_id=tenant, project_id=project,
        document_id=doc, blob_hash="a" * 64,
    )
    kwargs = dict(
        metadata=metadata, parsed_text=TEXT, revision=revision,
        tenant_id=tenant, project_id=project, document_id=doc,
    )
    return metadata, revision, kwargs


def test_verified_synthetic_revision_produces_bound_attestation() -> None:
    _, revision, kwargs = _fixture()
    attested = build_n12_source_attestation(**kwargs)
    assert attested is not None
    assert attested["revision_id"] == str(revision.revision_id)
    state = {
        "document_revision_id": str(revision.revision_id),
        "document_id": str(revision.document_id),
        "project_id": str(revision.project_id),
        "tenant_id": str(revision.tenant_id),
        "document_text": TEXT,
        "n12_source_attestation": attested,
    }
    assert is_n12_source_attestation_valid(state, source_text=TEXT)
    assert not is_n12_source_attestation_valid(state, source_text="EPC-05: trimmed")
    assert not is_n12_source_attestation_valid({**state, "document_revision_id": str(uuid4())}, source_text=TEXT)
    assert not is_n12_source_attestation_valid({**state, "tenant_id": str(uuid4())}, source_text=TEXT)


@pytest.mark.parametrize("status,assurance", [
    ("UNVERIFIED", "verified_full_source_text"),
    ("PARTIAL", "verified_full_source_text"),
    ("COMPLETE", None),  # a COMPLETE flag alone does not prove text coverage
    ("COMPLETE", "parser_only"),
])
def test_parser_coverage_claims_without_assurance_fail_closed(status, assurance):
    _, _, kwargs = _fixture(status=status, assurance=assurance)
    assert build_n12_source_attestation(**kwargs) is None


@pytest.mark.parametrize("tamper", [
    "revision", "tenant", "document", "project", "blob", "text", "text_digest",
    "missing_digest", "stale_text_revision", "known_omission", "limitations",
    "missing_observation", "unknown_parser",
])
def test_source_revision_and_text_tampering_cannot_attest(tamper):
    metadata, revision, kwargs = _fixture()
    coverage = metadata["document_coverage_by_revision"][str(revision.revision_id)]
    if tamper == "revision":
        kwargs["revision"] = SimpleNamespace(**{**vars(revision), "revision_id": uuid4()})
    elif tamper in {"tenant", "document", "project"}:
        kwargs[{"tenant": "tenant_id", "document": "document_id", "project": "project_id"}[tamper]] = uuid4()
    elif tamper == "blob":
        coverage["blob_hash"] = "b" * 64
    elif tamper == "text":
        kwargs["parsed_text"] = TEXT + " missing a clause"
    elif tamper == "text_digest":
        metadata["n12_parsed_text_sha256_by_revision"][str(revision.revision_id)] = "0" * 64
    elif tamper == "missing_digest":
        metadata.pop("n12_parsed_text_sha256_by_revision")
    elif tamper == "stale_text_revision":
        metadata["parsed_text_revision_id"] = str(uuid4())
    elif tamper == "known_omission":
        coverage["known_omissions"] = [{"kind": "missing_clause"}]
    elif tamper == "limitations":
        coverage["limitations"] = ["ocr_failed"]
    elif tamper == "missing_observation":
        coverage.pop("parser_observations")
    elif tamper == "unknown_parser":
        coverage["origin"] = "untrusted_importer"
    assert build_n12_source_attestation(**kwargs) is None


def test_graph_cannot_accept_a_coverage_attestation_for_a_redacted_projection():
    _, revision, kwargs = _fixture()
    attested = build_n12_source_attestation(**kwargs)
    state = {
        "document_revision_id": str(revision.revision_id),
        "document_id": str(revision.document_id),
        "project_id": str(revision.project_id),
        "tenant_id": str(revision.tenant_id),
        "document_text": TEXT,
        "anonymized_text": "EPC-05: [REDACTED] pays delay damages.",
        "pii_anonymization_complete": True,
        "n12_source_attestation": attested,
    }
    assert not is_n12_source_attestation_valid(
        state, source_text="EPC-05: [REDACTED] pays delay damages."
    )


def test_real_pdf_docx_parser_metadata_stays_unverified() -> None:
    from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser
    # Both actual parser branches publish UNVERIFIED, not assurance.
    from inspect import getsource
    source = getsource(CompositeFileParser.parse_document_file)
    assert source.count('"status": "UNVERIFIED"') >= 2
    assert "verified_full_source_text" not in source


def test_parser_cannot_override_server_minted_revision_and_blob_identity() -> None:
    _, revision, kwargs = _fixture()
    metadata = {}
    record_revision_document_coverage(
        metadata,
        parsed_payload={
            "document_coverage": {
                "status": "UNVERIFIED", "origin": "docx_file_parser",
                "revision_id": str(uuid4()), "blob_hash": "0" * 64,
            },
            "text_blocks": [{"text": TEXT, "page": 1}],
        },
        revision_id=revision.revision_id,
        blob_hash=revision.blob_hash,
    )
    coverage = metadata["document_coverage_by_revision"][str(revision.revision_id)]
    assert coverage["revision_id"] == str(revision.revision_id)
    assert coverage["blob_hash"] == revision.blob_hash


@pytest.mark.asyncio
async def test_canonical_n12_node_accepts_only_trusted_synthetic_attestation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import AsyncMock
    from src.analysis.adapters.graph import nodes
    from tests.unit.analysis.graph.test_thin_nodes import _make_state

    _, revision, kwargs = _fixture()
    attested = build_n12_source_attestation(**kwargs)

    class AI:
        async def run_extraction(self, _system, _content):
            return {"status": "OK", "notes": "", "findings": []}

    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    monkeypatch.setattr(nodes, "get_ai_service", lambda tenant_id: AI())
    monkeypatch.setattr(nodes, "_apply_temporal_review_gate", AsyncMock())
    state = _make_state(
        document_text=TEXT,
        document_revision_id=str(revision.revision_id),
        document_id=str(revision.document_id),
        project_id=str(revision.project_id),
        tenant_id=str(revision.tenant_id),
        extracted_risks=[{"title": "contract risk", "confidence": 0.99}],
        n12_source_attestation=attested,
    )
    verified = await nodes.critique_node(state)
    assert verified["confidence_score"] == pytest.approx(0.99)
    assert verified["human_approval_required"] is False

    missing = _make_state(**{
        **state,
        "messages": [],
        "node_results": [],
        "n12_source_attestation": None,
        "human_approval_required": False,
        "critique_notes": "",
    })
    not_verified = await nodes.critique_node(missing)
    assert not_verified["confidence_score"] is None
    assert not_verified["human_approval_required"] is True
    assert "upstream document completeness not verified" in not_verified["critique_notes"]
