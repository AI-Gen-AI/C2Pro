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


@pytest.mark.parametrize(
    "heading",
    [
        "Completion Date.",
        "Completion Date: TBD.",
        "Contract Price.",
        "Scope of Work.",
        "Technical Specification.",
        "Quality Inspection.",
        "Fecha de finalización.",
    ],
)
def test_bare_headings_do_not_count_as_evidence(heading: str) -> None:
    outcome = assess_single_document_coverage(
        [Clause(id="persisted-heading", text=heading)],
        [],
        granularity=EvidenceGranularity.CLAUSE,
    )
    assert all(item.evidence_count == 0 for item in outcome.assessments)


@pytest.mark.parametrize(
    "unrelated",
    [
        "The price of admission was a small amount compared with the cost of travel.",
        "The inspection article discussed test quality in a school laboratory.",
        "The television program announced the completion date and milestone celebration.",
        "The standards magazine compared equipment design in consumer advertising.",
        "The school project scope included supply of deliverables.",
        "A magazine article summarized contract liability and warranty.",
    ],
)
def test_non_contract_prose_is_not_health_evidence(unrelated: str) -> None:
    outcome = assess_single_document_coverage(
        [Clause(id="single", text=unrelated)],
        [],
        granularity=EvidenceGranularity.CLAUSE,
    )
    assert all(item.evidence_count == 0 for item in outcome.assessments)


@pytest.mark.parametrize(
    "non_contract_statement",
    [
        "The museum will display its quality inspection certification.",
        "The newspaper will publish a completion date and milestone timeline.",
        "The museum shall report the price, payment amount and cost of tickets.",
        "An inspection museum will perform quality tests on exhibits.",
        "5.2 Completion Date: 30 days, delay, milestone.",
    ],
)
def test_operative_but_non_contractual_prose_is_not_evidence(
    non_contract_statement: str,
) -> None:
    result = assess_single_document_coverage(
        [Clause(id="persisted-looking-id", text=non_contract_statement)],
        [],
        granularity=EvidenceGranularity.CLAUSE,
    )
    assert all(item.evidence_count == 0 for item in result.assessments)


def test_single_newline_does_not_pool_header_and_unrelated_payment_terms() -> None:
    # This used to generate BUDGET merely by pooling separate lines.
    combined = "Price.\nThe payment amount shall be recorded elsewhere."
    outcome = assess_single_document_coverage(
        [Clause(id="single", text=combined)],
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
