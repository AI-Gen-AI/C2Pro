"""S3: approved N8 assessment survives the immutable-artifact N17 resume path.

No models, live AI, network, or real PostgreSQL; these are the trust-preserving
materialization contracts, NOT a fabricated Health result.
"""

from copy import deepcopy

from src.analysis.adapters.graph.document_artifact_builder import build_document_artifact
from src.analysis.application.trusted_materialization import MaterializationContent
from src.analysis.domain.trust import artifact_digest
from src.health.application.document_assessment import build_document_assessment_artifact
from src.health.domain.analysis_assessment import decode_single_document_assessment


def _state(score=72):
    return {
        "document_id": "doc-A",
        "document_revision_id": "revision-2",
        "doc_type": "contract",
        "extracted_risks": [],
        "extracted_wbs": [],
        "coherence_score": score,
        "coherence_breakdown": {"LEGAL": 80} if score is not None else {},
        "coherence_reason": "evaluated" if score is not None else "insufficient_evidence",
        "single_document_assessment": build_document_assessment_artifact([], []),
    }


def _bound(state):
    payload = build_document_artifact(state).model_dump(mode="json")
    return payload, artifact_digest(payload)


def test_s3_verified_resume_persists_the_six_assessments_without_recomputing():
    state = _state()
    payload, digest = _bound(state)
    content = MaterializationContent.from_artifact(
        payload, resumed_state=state, expected_artifact_hash=digest
    )
    decoded = decode_single_document_assessment(content.assessment)
    assert decoded is not None
    assert len(decoded.coverage.assessments) == 6
    assert content.coherence_score == 72


def test_s3_null_coherence_score_does_not_erase_valid_six_category_evaluation():
    state = _state(score=None)
    payload, digest = _bound(state)
    content = MaterializationContent.from_artifact(
        payload, resumed_state=state, expected_artifact_hash=digest
    )
    decoded = decode_single_document_assessment(content.assessment)
    assert decoded is not None
    assert len(decoded.coverage.assessments) == 6
    assert content.coherence_score is None


def test_s3_missing_or_wrong_hash_and_changed_source_never_trust_resumed_assessment():
    state = _state()
    payload, digest = _bound(state)
    bad_states = [
        (state, None),
        (state, "0" * 64),
    ]
    changed_state = deepcopy(state)
    changed_state["extracted_wbs"] = [{"code": "FABRICATED-WBS"}]
    bad_states.append((changed_state, digest))
    for other_state, other_hash in bad_states:
        content = MaterializationContent.from_artifact(
            payload, resumed_state=other_state, expected_artifact_hash=other_hash
        )
        assert decode_single_document_assessment(content.assessment) is None
        assert content.coherence_score is None


def test_s3_invalid_assessment_is_unavailable_not_six_fabricated_categories():
    state = _state()
    state["single_document_assessment"] = {
        "single_document_assessment": {"version": 999, "coverage": {"assessments": []}}
    }
    payload, digest = _bound(state)
    content = MaterializationContent.from_artifact(
        payload, resumed_state=state, expected_artifact_hash=digest
    )
    assert decode_single_document_assessment(content.assessment) is None
