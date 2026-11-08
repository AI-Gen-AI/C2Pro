"""Health P1: stronger source evidence is bounded to persisted-clause granularity.

No paid model calls; the immutable EPC oracle is reused rather than tuning
to three tiny document placeholders.
"""

from __future__ import annotations

import pytest

from scripts.n4_n12_real_ai_eval import load_fixture
from src.coherence.domain.category_weights import CoherenceCategory
from src.coherence.models import Clause
from src.health.application.document_assessment import build_document_assessment_artifact
from src.health.application.single_document_coverage import assess_single_document_coverage
from src.health.domain.analysis_assessment import (
    HEALTH_METHOD_CLAUSE_V2,
    HEALTH_METHOD_ROUTER_V1,
    SINGLE_DOCUMENT_ASSESSMENT_KEY,
    decode_single_document_assessment,
    encode_single_document_assessment,
)
from src.health.domain.category_coverage import CategoryCoverageState
from src.health.domain.single_document_coverage import EvidenceGranularity


def _epc_price() -> str:
    return next(c["text"] for c in load_fixture()["contract"]["clauses"] if c["id"] == "EPC-02")


def _budget(coverage):
    return next(c for c in coverage.assessments if c.category is CoherenceCategory.BUDGET)


def test_unsegmented_document_does_not_inherit_source_clause_fallback() -> None:
    source = [Clause(id="synthetic-whole-document", text=_epc_price())]
    artifact = build_document_assessment_artifact(
        source, [], granularity=EvidenceGranularity.DOCUMENT
    )
    item = decode_single_document_assessment(artifact)
    assert item is not None
    assert item.classification_method_version == HEALTH_METHOD_ROUTER_V1
    assert _budget(item.coverage).state is CategoryCoverageState.INSUFFICIENT_EVIDENCE


def test_only_clause_level_assessment_uses_new_method_and_retains_id() -> None:
    artifact = build_document_assessment_artifact(
        [Clause(id="persisted-clause-uuid", text=_epc_price())],
        [],
        granularity=EvidenceGranularity.CLAUSE,
    )
    item = decode_single_document_assessment(artifact)
    assert item is not None
    assert item.classification_method_version == HEALTH_METHOD_CLAUSE_V2
    assert item.evidence_granularity is EvidenceGranularity.CLAUSE
    assert _budget(item.coverage).evidence_clause_ids == ("persisted-clause-uuid",)


def test_anchors_from_unrelated_paragraphs_cannot_be_combined() -> None:
    combined = "Contract Price.\n\nThe taxes and customs charges were quoted elsewhere."
    outcome = assess_single_document_coverage(
        [Clause(id="one", text=combined)],
        [],
        granularity=EvidenceGranularity.CLAUSE,
    )
    assert _budget(outcome).state is CategoryCoverageState.INSUFFICIENT_EVIDENCE


def test_legacy_method_not_reinterpreted_and_v2_rejected_for_document_blob() -> None:
    legacy = build_document_assessment_artifact(
        [Clause(id="old", text=_epc_price())], [], granularity=EvidenceGranularity.DOCUMENT
    )
    raw = dict(legacy[SINGLE_DOCUMENT_ASSESSMENT_KEY])
    old_coverage = raw["coverage"]
    raw.pop("classification_method_version")
    decoded = decode_single_document_assessment({SINGLE_DOCUMENT_ASSESSMENT_KEY: raw})
    assert decoded is not None
    assert decoded.classification_method_version == HEALTH_METHOD_ROUTER_V1
    assert decoded.coverage.model_dump(mode="json") == old_coverage

    with pytest.raises(ValueError, match="clause-anchor method requires"):
        encode_single_document_assessment(
            decoded.coverage,
            [],
            EvidenceGranularity.DOCUMENT,
            classification_method_version=HEALTH_METHOD_CLAUSE_V2,
        )
