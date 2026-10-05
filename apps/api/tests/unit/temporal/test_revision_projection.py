"""TS-UT-P0C-TEMPORAL-010 - revision projection through the #714 machinery (PR-C2).

The projected Coherence for a revision is the existing trusted projection
(``project_pending_coherence``) fed with exactly the PROPOSED candidate bound
to that revision. No second evaluator; nothing is written; no candidate means
no projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.analysis.adapters.persistence.document_artifact_repository import PendingCandidate
from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.domain.trust import CandidateBinding
from src.temporal.application.change_qualification import ChangeQualification
from src.temporal.application.revision_projection import project_revision_coherence
from src.temporal.domain.engine_registry import MatcherStatus
from src.temporal.domain.impact import EpistemicBasis

pytestmark = pytest.mark.asyncio

PROJECT, DOCUMENT, OTHER_DOCUMENT = uuid4(), uuid4(), uuid4()
REVISION = uuid4()


@dataclass
class _Summary:
    overall_score: float | None
    score_reason: str | None = None


@dataclass
class _Evaluation:
    summary: _Summary
    score_version: str = "coherence-v1"


def _artifact(document_id: UUID, revision_id: UUID | None) -> DocumentArtifact:
    return DocumentArtifact(
        document_id=str(document_id),
        document_revision_id=str(revision_id) if revision_id else None,
        doc_type="contract",
    )


def _candidate(document_id: UUID, revision_id: UUID | None) -> PendingCandidate:
    return PendingCandidate(
        binding=CandidateBinding(
            artifact_id=uuid4(), document_id=document_id, artifact_version=3, artifact_hash="h" * 64
        ),
        project_id=PROJECT,
        scoring=None,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        artifact=_artifact(document_id, revision_id),
    )


def _qualification(
    *, verified: bool = True, state: str = "ready", confidence: float | None = 1.0
) -> ChangeQualification:
    return ChangeQualification(
        matcher_status=MatcherStatus.CURRENT,
        legacy_matcher=False,
        identity_verified=verified,
        effective_state=state,
        effective_confidence=confidence,
        effective_change_cause="BUSINESS_STATE_CHANGED",
        reason=None,
    )


class _Recorder:
    def __init__(self, trusted: float, projected: float) -> None:
        self.calls: list[list[DocumentArtifact]] = []
        self.trusted = trusted
        self.projected = projected

    async def evaluate(self, artifacts: list[DocumentArtifact]) -> Any:
        self.calls.append(list(artifacts))
        has_candidate = any(a.document_revision_id == str(REVISION) for a in artifacts)
        return _Evaluation(_Summary(self.projected if has_candidate else self.trusted))


async def _project(
    pending: list[PendingCandidate],
    trusted: list[DocumentArtifact],
    recorder: _Recorder,
    qualification: ChangeQualification,
) -> Any:
    async def _pending() -> list[PendingCandidate]:
        return pending

    async def _trusted() -> list[DocumentArtifact]:
        return trusted

    return await project_revision_coherence(
        document_id=DOCUMENT,
        revision_id=REVISION,
        list_pending=_pending,
        list_trusted=_trusted,
        evaluate=recorder.evaluate,
        qualification=qualification,
    )


async def test_candidate_for_revision_is_projected_with_the_canonical_evaluator() -> None:
    recorder = _Recorder(trusted=0.70, projected=0.62)
    trusted = [_artifact(DOCUMENT, None), _artifact(OTHER_DOCUMENT, None)]
    candidate = _candidate(DOCUMENT, REVISION)

    projection = await _project([candidate], trusted, recorder, _qualification())

    assert projection.status == "provisional"
    assert projection.basis is EpistemicBasis.PROJECTED
    assert projection.trusted_score == 0.70
    assert projection.projected_score == 0.62
    assert projection.projected_delta == pytest.approx(-0.08)
    assert projection.score_version == "coherence-v1"
    # Baseline over trusted only, then trusted with the candidate substituted.
    assert len(recorder.calls) == 2
    assert {a.document_revision_id for a in recorder.calls[1]} == {str(REVISION), None}


async def test_projection_never_mutates_the_trusted_inputs() -> None:
    recorder = _Recorder(trusted=0.70, projected=0.40)
    trusted = [_artifact(DOCUMENT, None)]
    snapshot = [a.model_dump() for a in trusted]

    await _project([_candidate(DOCUMENT, REVISION)], trusted, recorder, _qualification())

    assert [a.model_dump() for a in trusted] == snapshot


async def test_projection_carries_source_revision_and_candidate_binding() -> None:
    recorder = _Recorder(trusted=0.70, projected=0.62)
    candidate = _candidate(DOCUMENT, REVISION)

    projection = await _project([candidate], [], recorder, _qualification())

    assert projection.source_revision_id == REVISION
    assert projection.candidate is not None
    assert projection.candidate.artifact_id == candidate.binding.artifact_id
    assert projection.candidate.artifact_version == 3
    assert projection.candidate.artifact_hash == "h" * 64


async def test_review_required_temporal_input_keeps_projection_unverified() -> None:
    recorder = _Recorder(trusted=0.70, projected=0.62)

    projection = await _project(
        [_candidate(DOCUMENT, REVISION)],
        [],
        recorder,
        _qualification(verified=True, state="needs_review", confidence=0.84),
    )

    assert projection.status == "provisional"
    assert projection.qualification == "provisional_unverified_temporal_identity"
    assert projection.confidence == 0.84


async def test_legacy_input_projection_has_unknown_confidence() -> None:
    recorder = _Recorder(trusted=0.70, projected=0.62)

    projection = await _project(
        [_candidate(DOCUMENT, REVISION)],
        [],
        recorder,
        _qualification(verified=False, state="needs_review", confidence=None),
    )

    assert projection.qualification == "provisional_unverified_temporal_identity"
    assert projection.confidence is None


async def test_no_candidate_for_the_revision_is_no_projection() -> None:
    recorder = _Recorder(trusted=0.70, projected=0.62)
    unrelated = [_candidate(OTHER_DOCUMENT, uuid4()), _candidate(DOCUMENT, None)]

    projection = await _project(unrelated, [_artifact(DOCUMENT, None)], recorder, _qualification())

    assert projection.status == "none"
    assert projection.projected_score is None
    assert projection.trusted_score is None
    assert projection.candidate is None
    assert recorder.calls == []


async def test_evaluator_failure_is_unavailable_not_fabricated() -> None:
    async def _boom(_artifacts: list[DocumentArtifact]) -> Any:
        raise RuntimeError("engine down")

    async def _pending() -> list[PendingCandidate]:
        return [_candidate(DOCUMENT, REVISION)]

    async def _trusted() -> list[DocumentArtifact]:
        return [_artifact(DOCUMENT, None)]

    projection = await project_revision_coherence(
        document_id=DOCUMENT,
        revision_id=REVISION,
        list_pending=_pending,
        list_trusted=_trusted,
        evaluate=_boom,
        qualification=_qualification(),
    )

    assert projection.status == "unavailable"
    assert projection.projected_score is None
