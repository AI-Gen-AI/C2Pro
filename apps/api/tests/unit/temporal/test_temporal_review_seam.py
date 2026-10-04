"""TS-UT-P0C-TEMPORAL-011 - revision-level temporal-review trust seam (PR-C2).

A revision whose temporal interpretation needs review must not auto-promote
to TRUSTED. The decision is derived from the revision's own temporal events
(artifact/revision scoped, no clause fields) and is consumed by the canonical
gate at N12 by OR-ing it into ``human_approval_required``.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.temporal.application.temporal_review import (
    TemporalReviewDecision,
    decide_temporal_review,
)
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.project_event import ProjectEvent

DOCUMENT = uuid4()


def _revision(parent: UUID | None = None, *, document_id: UUID = DOCUMENT) -> DocumentRevision:
    now = datetime.now(UTC).replace(tzinfo=None)
    return DocumentRevision(
        revision_id=uuid4(),
        document_id=document_id,
        project_id=uuid4(),
        tenant_id=uuid4(),
        rev_no=2 if parent else 1,
        parent_revision_id=parent,
        blob_hash="b" * 64,
        blob_key="revisions/b",
        valid_from=now,
        created_at=now,
    )


def _event(
    revision: DocumentRevision, event_type: str, payload: dict[str, Any], *, seconds: int = 0
) -> ProjectEvent:
    now = datetime(2026, 10, 4, 10, 0, seconds)
    return ProjectEvent(
        event_id=uuid4(),
        project_id=revision.project_id,
        tenant_id=revision.tenant_id,
        event_type=event_type,
        payload={"document_id": str(revision.document_id), **payload},
        source_revision_id=revision.revision_id,
        occurred_at=now,
        created_at=now,
    )


def _changed(
    revision: DocumentRevision,
    *,
    state: str,
    engine: str = "p0c-structural-l1-v2",
    basis: str | None = "exact_content",
    seconds: int = 1,
) -> ProjectEvent:
    change = {
        "object_type": "clause",
        "change_type": "renumbered",
        "needs_review": state == "needs_review",
        "match_basis": basis,
    }
    return _event(
        revision,
        "revision.changed",
        {
            "state": state,
            "changeset": {"changes": [change]},
            "provenance": {"diff_engine_version": engine},
        },
        seconds=seconds,
    )


def _analyzed(revision: DocumentRevision, state: str = "ready") -> ProjectEvent:
    return _event(
        revision, "revision.analyzed", {"state": state, "revision_id": str(revision.revision_id)}
    )


# --- 21-22 -----------------------------------------------------------------------


def test_needs_review_revision_requires_temporal_review() -> None:
    revision = _revision(parent=uuid4())

    decision = decide_temporal_review(
        revision=revision,
        document_id=DOCUMENT,
        events=[_analyzed(revision), _changed(revision, state="needs_review")],
    )

    assert decision.required is True
    assert decision.reason == "temporal_changes_need_review"


def test_clean_deterministic_revision_does_not_require_review() -> None:
    revision = _revision(parent=uuid4())

    decision = decide_temporal_review(
        revision=revision,
        document_id=DOCUMENT,
        events=[_analyzed(revision), _changed(revision, state="ready")],
    )

    assert decision == TemporalReviewDecision(required=False, reason="temporal_identity_resolved")


def test_baseline_revision_needs_no_temporal_review() -> None:
    revision = _revision(parent=None)

    decision = decide_temporal_review(
        revision=revision, document_id=DOCUMENT, events=[_analyzed(revision)]
    )

    assert decision.required is False
    assert decision.reason == "baseline_revision"


# --- 23: legacy / unverified / incomplete fail closed --------------------------------


@pytest.mark.parametrize(
    ("events_for", "reason"),
    [
        (
            lambda r: [_changed(r, state="ready", engine="p0c-structural-l1-v1", basis=None)],
            "temporal_identity_unverified",
        ),
        (
            lambda r: [_changed(r, state="ready", engine="schedule-cpm-v1")],
            "temporal_identity_unverified",
        ),
        (lambda r: [_changed(r, state="ready", basis=None)], "temporal_identity_unverified"),
        (lambda r: [_analyzed(r, "needs_review")], "temporal_comparison_incomplete"),
        (
            lambda r: [_event(r, "revision.analysis_failed", {"state": "error"})],
            "temporal_comparison_failed",
        ),
        (lambda r: [_analyzed(r, "ready")], "temporal_comparison_missing"),
    ],
)
def test_unresolved_temporal_identity_fails_closed(events_for: Any, reason: str) -> None:
    revision = _revision(parent=uuid4())

    decision = decide_temporal_review(
        revision=revision, document_id=DOCUMENT, events=events_for(revision)
    )

    assert decision.required is True
    assert decision.reason == reason


def test_latest_comparison_wins_for_the_revision() -> None:
    revision = _revision(parent=uuid4())
    events = [
        _changed(revision, state="ready", seconds=1),
        _changed(revision, state="needs_review", seconds=5),
    ]

    assert (
        decide_temporal_review(revision=revision, document_id=DOCUMENT, events=events).required
        is True
    )


def test_unknown_or_foreign_revision_fails_closed() -> None:
    assert decide_temporal_review(revision=None, document_id=DOCUMENT, events=[]).required is True
    foreign = _revision(parent=uuid4(), document_id=uuid4())
    assert (
        decide_temporal_review(revision=foreign, document_id=DOCUMENT, events=[]).required is True
    )


def test_revision_without_temporal_assessment_is_not_claimed() -> None:
    revision = _revision(parent=uuid4())

    decision = decide_temporal_review(revision=revision, document_id=DOCUMENT, events=[])

    assert decision.required is False
    assert decision.reason == "no_temporal_assessment"


# --- 31: revision/artifact scoped, no clause fields -----------------------------


def test_seam_signature_is_revision_scoped() -> None:
    from src.temporal.adapters.temporal_review_gate import revision_requires_temporal_review

    params = set(inspect.signature(revision_requires_temporal_review).parameters)

    assert params == {"tenant_id", "document_id", "revision_id"}
    assert not any("clause" in name for name in params)


# --- canonical gate consumption at N12 ----------------------------------------------


def _graph_state(**overrides: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "project_id": str(uuid4()),
        "document_id": str(DOCUMENT),
        "tenant_id": str(uuid4()),
        "doc_type": "contract",
        "messages": [],
        "extracted_risks": [],
        "extracted_wbs": [],
        "retry_count": 0,
        "confidence_score": 0.0,
        "critique_notes": "",
        "human_approval_required": False,
    }
    state.update(overrides)
    return state


@pytest.mark.asyncio
async def test_temporal_review_forces_the_canonical_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.temporal.adapters.temporal_review_gate as gate
    from src.analysis.adapters.graph.nodes import critique_node

    seen: list[tuple[str, str, str]] = []

    async def _requires(
        *, tenant_id: str, document_id: str, revision_id: str
    ) -> TemporalReviewDecision:
        seen.append((tenant_id, document_id, revision_id))
        return TemporalReviewDecision(required=True, reason="temporal_changes_need_review")

    monkeypatch.setenv("C2PRO_AI_MOCK", "1")
    monkeypatch.setattr(gate, "revision_requires_temporal_review", _requires)
    revision_id = str(uuid4())

    state = await critique_node(_graph_state(document_revision_id=revision_id))

    assert state["human_approval_required"] is True
    assert state["temporal_review_reason"] == "temporal_changes_need_review"
    assert seen and seen[0][2] == revision_id


@pytest.mark.asyncio
async def test_clean_revision_leaves_the_gate_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.temporal.adapters.temporal_review_gate as gate
    from src.analysis.adapters.graph.nodes import critique_node

    async def _clean(**_: str) -> TemporalReviewDecision:
        return TemporalReviewDecision(required=False, reason="temporal_identity_resolved")

    monkeypatch.setenv("C2PRO_AI_MOCK", "1")
    monkeypatch.setattr(gate, "revision_requires_temporal_review", _clean)

    state = await critique_node(_graph_state(document_revision_id=str(uuid4())))

    assert state["human_approval_required"] is False


@pytest.mark.asyncio
async def test_seam_lookup_failure_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.temporal.adapters.temporal_review_gate as gate
    from src.analysis.adapters.graph.nodes import critique_node

    async def _boom(**_: str) -> TemporalReviewDecision:
        raise RuntimeError("event store unavailable")

    monkeypatch.setenv("C2PRO_AI_MOCK", "1")
    monkeypatch.setattr(gate, "revision_requires_temporal_review", _boom)

    state = await critique_node(_graph_state(document_revision_id=str(uuid4())))

    assert state["human_approval_required"] is True
    assert state["temporal_review_reason"] == "temporal_review_lookup_failed"


@pytest.mark.asyncio
async def test_run_without_a_pinned_revision_does_not_query_the_seam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.temporal.adapters.temporal_review_gate as gate
    from src.analysis.adapters.graph.nodes import critique_node

    async def _never(**_: str) -> TemporalReviewDecision:
        raise AssertionError("seam must not be queried without a pinned revision")

    monkeypatch.setenv("C2PRO_AI_MOCK", "1")
    monkeypatch.setattr(gate, "revision_requires_temporal_review", _never)

    state = await critique_node(_graph_state())

    assert state["human_approval_required"] is False


def test_gated_completion_persists_a_proposed_candidate_even_under_skip_hitl() -> None:
    """The completion hook decides PROPOSED vs TRUSTED from the same flag (#714)."""
    from src.analysis.application.document_artifact_completion import _requires_human_approval

    assert _requires_human_approval({"human_approval_required": True}) is True


def test_analysis_initial_state_carries_the_pinned_revision() -> None:
    """The graph must know which revision it analyses for the seam and artifact binding."""
    from src.analysis.adapters.graph.schema import ProjectState

    assert "document_revision_id" in ProjectState.__annotations__
