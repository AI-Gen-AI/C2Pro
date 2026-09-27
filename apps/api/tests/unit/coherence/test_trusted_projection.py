"""#714 projected Coherence: canonical evaluator over trusted + ALL actionable pending.

projected = canonical ProjectGraph evaluation of the trusted artifact set with
every actionable pending proposal substituted; baseline = the same evaluation
of the trusted set. No stored per-run scores, no "latest wins".
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from src.analysis.adapters.graph.project_graph import evaluate_artifact_set
from src.analysis.adapters.persistence.document_artifact_repository import PendingCandidate
from src.analysis.domain.contracts import DocumentArtifact, RiskItem
from src.analysis.domain.trust import CandidateBinding
from src.coherence.application.trusted_projection import (
    ProjectionStatus,
    project_pending_coherence,
)

pytestmark = pytest.mark.asyncio

T0 = datetime(2026, 9, 27, 12, 0, 0)
DOC_A = str(uuid4())
DOC_B = str(uuid4())
A_CATEGORIES = ("LEGAL", "TECHNICAL", "SCOPE")
B_CATEGORIES = ("BUDGET", "TIME", "QUALITY")


def _artifact(document_id: str, categories: tuple[str, ...], level: str = "LOW", n: int = 1):
    return DocumentArtifact(
        document_id=document_id,
        doc_type="contract",
        extracted_risks=[
            RiskItem(title=f"{c}-{i}", description="d", category=c, impact=level, likelihood=level)
            for c in categories
            for i in range(n)
        ],
    )


def _pending(artifact: DocumentArtifact, *, at: int = 0) -> PendingCandidate:
    return PendingCandidate(
        binding=CandidateBinding(uuid4(), UUID(artifact.document_id), 2, "a" * 64),
        project_id=uuid4(),
        scoring=None,
        created_at=T0 + timedelta(minutes=at),
        artifact=artifact,
        review_row_id=uuid4(),
    )


def _real_evaluator():
    project_id, tenant_id = uuid4(), uuid4()

    async def evaluate(artifacts: list[DocumentArtifact]):
        return await evaluate_artifact_set(
            artifacts, project_id=project_id, tenant_id=tenant_id, llm_on=False
        )

    return evaluate


TRUSTED = [_artifact(DOC_A, A_CATEGORIES), _artifact(DOC_B, B_CATEGORIES)]
A_PRIME = _artifact(DOC_A, A_CATEGORIES, "CRITICAL", 3)
B_PRIME = _artifact(DOC_B, B_CATEGORIES, "CRITICAL", 3)


async def test_projection_is_canonical_evaluation_of_all_pending_substituted() -> None:
    evaluate = _real_evaluator()
    both = (await evaluate([A_PRIME, B_PRIME])).summary.overall_score
    only_a = (await evaluate([A_PRIME, TRUSTED[1]])).summary.overall_score
    only_b = (await evaluate([TRUSTED[0], B_PRIME])).summary.overall_score
    baseline = (await evaluate(TRUSTED)).summary.overall_score
    # Both proposals materially change the canonical result, and neither
    # single substitution equals the combined scenario.
    assert len({both, only_a, only_b, baseline}) >= 3
    assert both not in (only_a, only_b)

    for order in ([_pending(A_PRIME, at=0), _pending(B_PRIME, at=5)],
                  [_pending(B_PRIME, at=5), _pending(A_PRIME, at=0)]):
        p = await project_pending_coherence(
            trusted_artifacts=TRUSTED, pending=order, evaluate=evaluate,
            trusted_score_version="coherence-v1",
        )
        assert p.status is ProjectionStatus.PROVISIONAL
        assert p.projected_score == both, "ALL pending proposals, order independent"
        assert p.baseline_score == baseline
        assert p.projected_delta == round(both - baseline, 4)
        assert p.pending_review_count == 2
        assert p.projection_score_version == "coherence-v1"


async def test_single_pending_is_evaluated_not_copied_from_stored_score() -> None:
    evaluate = _real_evaluator()
    candidate = _pending(A_PRIME)
    candidate = PendingCandidate(**{**candidate.__dict__, "scoring": SimpleNamespace(
        coherence_score=99.0, score_version="coherence-v1")})
    p = await project_pending_coherence(
        trusted_artifacts=TRUSTED, pending=[candidate], evaluate=evaluate
    )
    assert p.projected_score == (await evaluate([A_PRIME, TRUSTED[1]])).summary.overall_score
    assert p.projected_score != 99.0


async def test_correction_replaces_the_pending_version_in_the_scenario() -> None:
    evaluate = _real_evaluator()
    corrected = _artifact(DOC_A, A_CATEGORIES, "MEDIUM", 1)
    p = await project_pending_coherence(
        trusted_artifacts=TRUSTED, pending=[_pending(corrected)], evaluate=evaluate
    )
    assert p.projected_score == (await evaluate([corrected, TRUSTED[1]])).summary.overall_score


async def test_no_projection_when_nothing_is_pending_and_no_evaluation_runs() -> None:
    calls: list[object] = []

    async def evaluate(artifacts):
        calls.append(artifacts)
        raise AssertionError("must not evaluate")

    p = await project_pending_coherence(trusted_artifacts=TRUSTED, pending=[], evaluate=evaluate)
    assert p.status is ProjectionStatus.NONE
    assert (p.projected_score, p.projected_delta, p.pending_review_count) == (None, None, 0)
    assert calls == []


def _fake(score_by_len: dict[int, float | None], version: str | None = "coherence-v1"):
    async def evaluate(artifacts):
        return SimpleNamespace(
            summary=SimpleNamespace(
                overall_score=score_by_len.get(len(artifacts)), score_reason="insufficient_evidence"
            ),
            score_version=version,
        )

    return evaluate


async def test_first_analysis_has_projection_but_no_baseline_or_delta() -> None:
    p = await project_pending_coherence(
        trusted_artifacts=[], pending=[_pending(A_PRIME)], evaluate=_fake({1: 72.0})
    )
    assert p.status is ProjectionStatus.PROVISIONAL
    assert (p.baseline_score, p.projected_score, p.projected_delta) == (None, 72.0, None)


async def test_insufficient_projected_evidence_stays_null_not_zero() -> None:
    p = await project_pending_coherence(
        trusted_artifacts=TRUSTED, pending=[_pending(A_PRIME)], evaluate=_fake({2: None})
    )
    assert p.status is ProjectionStatus.UNAVAILABLE
    assert p.projected_score is None
    assert p.reason == "insufficient_evidence"
    assert p.pending_review_count == 1


async def test_projection_never_mixes_score_versions() -> None:
    p = await project_pending_coherence(
        trusted_artifacts=TRUSTED,
        pending=[_pending(A_PRIME)],
        evaluate=_fake({2: 60.0}, version="coherence-v2"),
        trusted_score_version="coherence-v1",
    )
    assert p.status is ProjectionStatus.UNAVAILABLE
    assert p.reason == "score_version_mismatch"


async def test_evaluation_failure_is_unavailable_not_an_error() -> None:
    async def boom(_artifacts):
        raise RuntimeError("engine down")

    p = await project_pending_coherence(
        trusted_artifacts=TRUSTED, pending=[_pending(A_PRIME)], evaluate=boom
    )
    assert p.status is ProjectionStatus.UNAVAILABLE
    assert p.reason == "projection_evaluation_failed"
    assert p.pending_review_count == 1
