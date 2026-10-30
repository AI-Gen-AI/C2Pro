"""S3: a cited technical requirement is NOT automatically assessed compliance.

A trusted technical source is eligible for a Health/Evidence deep link. Its
unverified obligations must be withheld from TECHNICAL scoring, even when the
CategoryRouter identifies the topic. A later compliance decision needs its own
authority, never source-upload or source-HITL as a substitute.
"""

from uuid import uuid4

import pytest

from src.coherence.graph.nodes import _effective_coverage, _withheld_coverage
from src.coherence.router import _build_clause
from src.coherence.scoring import ScoringService

REASON = "TECHNICAL_SOURCE_ONLY_COMPLIANCE_UNVERIFIED"


@pytest.mark.parametrize("family", ["technical_spec", "specification"])
@pytest.mark.parametrize("claimed_status", ["unverified", "verified"])
def test_source_requirement_is_citable_but_cannot_be_scored(
    family: str, claimed_status: str
) -> None:
    document_id = uuid4()
    revision_id = uuid4()
    section = "Section 4.1.2 Concrete compressive strength shall exceed 35 MPa at 28 days."
    clause = _build_clause(
        (
            uuid4(),
            section,
            {
                "technical_requirement": {
                    "source_section": "4.1.2",
                    "verification_status": claimed_status,
                },
                "evidence_location": {"revision_id": str(revision_id)},
            },
            document_id,
            family,
        )
    )
    assert clause is not None
    assert clause.text == section
    assert clause.data["document_id"] == str(document_id)
    assert clause.data["source_document_type"] == family
    assert clause.data["document_type"] == family
    assert clause.data["category"] == "TECHNICAL"
    assert clause.data["affected_categories"] == ["TECHNICAL"]
    assert clause.data["evidence_location"]["revision_id"] == str(revision_id)
    assert clause.data["assessment_unavailable"] == {"TECHNICAL": REASON}

    # Simulate an aggressive router inferring TECHNICAL from source words. The
    # technical dimension stays NULL despite that prior; no clean baseline.
    coverage = _effective_coverage({"TECHNICAL": True}, [clause])
    assert coverage["TECHNICAL"] is False
    assert _withheld_coverage([clause])["TECHNICAL"] == REASON
    score = ScoringService().calculate_detailed(
        signals=[], num_clauses=1, coverage_map=coverage
    )
    assert score.score is None
    assert "TECHNICAL" in (score.missing_dimensions or [])
    assert score.category_scores is not None
    assert score.category_scores["TECHNICAL"] is None


def test_contract_source_has_no_technical_source_only_veto() -> None:
    clause = _build_clause((uuid4(), "Payment of 1,000 EUR.", {}, uuid4(), "contract"))
    assert clause is not None
    assert clause.data["category"] == "CONTRACT"
    assert "assessment_unavailable" not in clause.data


def test_technical_document_without_a_requirement_does_not_invent_one() -> None:
    clause = _build_clause(
        (uuid4(), "Section 1 Table of contents.", {}, uuid4(), "technical_spec")
    )
    assert clause is not None
    assert clause.data["category"] == "TECHNICAL"
    assert "technical_requirement" not in clause.data
    assert "assessment_unavailable" not in clause.data
