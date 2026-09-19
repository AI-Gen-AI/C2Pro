"""TS-UA-HEALTH-024-R3 — the Health assessment names the document it was computed from.

Health → Evidence must open the EXACT document the single-document assessment came from.
The only authority for that identity is the analysis graph's own document id, carried as
``SingleDocumentCoverage.document_id`` through the analysis artifact into the HealthVector.
A consumer must never infer it (e.g. "the first contract of the project").
"""

from __future__ import annotations

from uuid import UUID, uuid4

from src.analysis.adapters.graph.nodes_extended import coverage_source_document_id
from src.coherence.models import Clause
from src.health.application.document_assessment import build_document_assessment_artifact
from src.health.application.single_document_coverage import assess_single_document_coverage
from src.health.domain.analysis_assessment import (
    SINGLE_DOCUMENT_ASSESSMENT_KEY,
    decode_single_document_assessment,
)
from src.health.domain.single_document_coverage import EvidenceGranularity


def _qualifier(_text: str) -> set:
    return set()


def test_coverage_carries_the_source_document_id() -> None:
    document_id = uuid4()

    coverage = assess_single_document_coverage(
        [], [], qualifier=_qualifier, document_id=document_id
    )

    assert coverage.document_id == document_id


def test_coverage_without_a_known_document_is_honestly_unattributed() -> None:
    coverage = assess_single_document_coverage([], [], qualifier=_qualifier)

    assert coverage.document_id is None


def test_the_source_document_survives_the_analysis_artifact_round_trip() -> None:
    document_id = uuid4()

    fragment = build_document_assessment_artifact(
        [Clause(id=str(uuid4()), text="The total contract price is 2,400,000.00 EUR")],
        [],
        granularity=EvidenceGranularity.CLAUSE,
        document_id=document_id,
    )
    assert fragment[SINGLE_DOCUMENT_ASSESSMENT_KEY]["coverage"]["document_id"] == str(document_id)

    decoded = decode_single_document_assessment(fragment)
    assert decoded is not None
    assert decoded.coverage.document_id == document_id


def test_graph_state_document_id_is_the_only_source() -> None:
    document_id = uuid4()

    assert coverage_source_document_id({"document_id": str(document_id)}) == document_id
    assert coverage_source_document_id({"document_id": document_id}) == document_id


def test_graph_state_without_a_real_document_id_never_invents_one() -> None:
    assert coverage_source_document_id({}) is None
    assert coverage_source_document_id({"document_id": None}) is None
    assert coverage_source_document_id({"document_id": "document"}) is None
    assert coverage_source_document_id({"document_id": "not-a-uuid"}) is None


def test_decoding_a_pre_propagation_artifact_keeps_the_document_unattributed() -> None:
    fragment = build_document_assessment_artifact([], [], granularity=EvidenceGranularity.DOCUMENT)
    fragment[SINGLE_DOCUMENT_ASSESSMENT_KEY]["coverage"].pop("document_id", None)

    decoded = decode_single_document_assessment(fragment)

    assert decoded is not None
    assert decoded.coverage.document_id is None
    assert isinstance(uuid4(), UUID)
