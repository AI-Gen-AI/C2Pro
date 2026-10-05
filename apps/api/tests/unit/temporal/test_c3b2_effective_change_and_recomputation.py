"""TS-UT-C3B2-TEMPORAL-001 - effective outcome selection + legacy recomputation (pure).

* Which stored outcome of a revision is EFFECTIVE is decided by lineage and
  matcher qualification, never by "latest timestamp" alone.
* A legacy (``p0c-structural-l1-v1``) comparison is recomputed by the CURRENT
  matcher over the exact immutable snapshots it used, append-only, with
  provenance, a deterministic id, and no fabricated evidence.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from src.documents.domain.models import Clause, ClauseType
from src.temporal.application.change_projection import CHANGE_PROJECTION_ENGINE_VERSION
from src.temporal.application.change_qualification import qualify_event
from src.temporal.application.effective_change import (
    Derivation,
    derivation_of,
    derived_from,
    effective_by_revision,
    select_effective_outcome,
)
from src.temporal.application.legacy_recomputation import (
    build_recomputed_event,
    eligibility,
    recomputation_event_id,
)
from src.temporal.application.revision_change_orchestrator import _snapshot_clause
from src.temporal.application.temporal_review import decide_temporal_review
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.engine_registry import MatcherStatus
from src.temporal.domain.project_event import ProjectEvent
from src.temporal.ports.revision_trust_reader import RevisionTrustEvidence

T0 = datetime(2026, 10, 5, 9, 0, 0)
TENANT, PROJECT, DOCUMENT = uuid4(), uuid4(), uuid4()
V1, V2 = uuid4(), uuid4()
V1_HASH, V2_HASH = "1" * 64, "2" * 64


def _event(
    event_type: str,
    payload: dict[str, Any],
    *,
    at: int,
    revision: UUID = V2,
    event_id: UUID | None = None,
) -> ProjectEvent:
    when = T0 + timedelta(seconds=at)
    return ProjectEvent(
        event_id=event_id or uuid4(),
        project_id=PROJECT,
        tenant_id=TENANT,
        event_type=event_type,
        payload={"document_id": str(DOCUMENT), **payload},
        source_revision_id=revision,
        occurred_at=when,
        created_at=when,
    )


def _comparison(
    event_type: str = "revision.changed",
    *,
    engine: str,
    at: int,
    state: str = "ready",
    extra: dict[str, str] | None = None,
    needs_review: bool = False,
) -> ProjectEvent:
    change = {
        "object_type": "clause",
        "change_type": "modified",
        "needs_review": needs_review,
        "match_basis": "source_number",
    }
    return _event(
        event_type,
        {
            "state": state,
            "changeset": {"changes": [change]},
            "provenance": {
                "diff_engine_version": engine,
                "source_revision_id": str(V1),
                "target_revision_id": str(V2),
                "source_blob_hash": V1_HASH,
                "target_blob_hash": V2_HASH,
                **(extra or {}),
            },
        },
        at=at,
    )


LEGACY = "p0c-structural-l1-v1"
CURRENT = CHANGE_PROJECTION_ENGINE_VERSION


# ── effective selection ─────────────────────────────────────────────────────


def test_current_recomputation_supersedes_its_legacy_original() -> None:
    original = _comparison(engine=LEGACY, at=1)
    recomputed = _comparison(
        "revision.recomputed",
        engine=CURRENT,
        at=5,
        extra={"recomputed_from_event_id": str(original.event_id)},
    )
    outcome = select_effective_outcome([original, recomputed])
    assert outcome.effective == recomputed
    assert outcome.superseded_by == {original.event_id: recomputed.event_id}
    assert derivation_of(recomputed) is Derivation.RECOMPUTED
    assert derived_from(recomputed) == original.event_id
    assert derivation_of(original) is Derivation.ORIGINAL


def test_a_later_legacy_reinterpretation_never_takes_over_from_the_recomputation() -> None:
    original = _comparison(engine=LEGACY, at=1)
    recomputed = _comparison(
        "revision.recomputed",
        engine=CURRENT,
        at=5,
        extra={"recomputed_from_event_id": str(original.event_id)},
    )
    # Appended LATER, but it re-reads the legacy pairings: newest is not effective.
    late_reading = _comparison(
        "revision.reinterpreted",
        engine=LEGACY,
        at=9,
        extra={"reinterpretation_of_event_id": str(original.event_id)},
    )
    outcome = select_effective_outcome([late_reading, original, recomputed])
    assert outcome.effective == recomputed
    assert outcome.superseded_by[late_reading.event_id] == recomputed.event_id


def test_a_reinterpretation_of_the_recomputation_refines_it() -> None:
    original = _comparison(engine=LEGACY, at=1)
    recomputed = _comparison(
        "revision.recomputed",
        engine=CURRENT,
        at=5,
        extra={"recomputed_from_event_id": str(original.event_id)},
    )
    reading = _comparison(
        "revision.reinterpreted",
        engine=CURRENT,
        at=7,
        extra={"reinterpretation_of_event_id": str(recomputed.event_id)},
    )
    assert select_effective_outcome([original, recomputed, reading]).effective == reading


def test_a_newer_analysis_supersedes_every_earlier_family() -> None:
    original = _comparison(engine=LEGACY, at=1)
    recomputed = _comparison(
        "revision.recomputed",
        engine=CURRENT,
        at=5,
        extra={"recomputed_from_event_id": str(original.event_id)},
    )
    reanalysis = _comparison(engine=CURRENT, at=10)
    assert select_effective_outcome([original, recomputed, reanalysis]).effective == reanalysis


def test_a_failed_newest_analysis_fails_closed() -> None:
    original = _comparison(engine=CURRENT, at=1)
    failed = _event("revision.analysis_failed", {"state": "error"}, at=4)
    assert select_effective_outcome([original, failed]).effective == failed


def test_selection_is_deterministic_and_grouped_per_revision() -> None:
    a = _comparison(engine=CURRENT, at=1)
    b = _comparison(engine=CURRENT, at=1)
    first = select_effective_outcome([a, b]).effective
    assert first == select_effective_outcome([b, a]).effective
    other = _event("revision.changed", {"state": "ready"}, at=2, revision=V1)
    grouped = effective_by_revision([a, b, other])
    assert set(grouped) == {V1, V2}
    assert grouped[V1].effective == other


def test_the_trust_seam_uses_the_effective_outcome_not_the_newest() -> None:
    parent = DocumentRevision(
        revision_id=V1, document_id=DOCUMENT, project_id=PROJECT, tenant_id=TENANT,
        rev_no=1, parent_revision_id=None, blob_hash=V1_HASH, blob_key="r/1",
        valid_from=T0, created_at=T0,
    )
    revision = DocumentRevision(
        revision_id=V2, document_id=DOCUMENT, project_id=PROJECT, tenant_id=TENANT,
        rev_no=2, parent_revision_id=V1, blob_hash=V2_HASH, blob_key="r/2",
        valid_from=T0, created_at=T0,
    )
    trust = RevisionTrustEvidence(states_by_revision={V1: frozenset({"trusted"})}, unbound_trusted=False)
    original = _comparison(engine=LEGACY, at=1)
    recomputed = _comparison(
        "revision.recomputed",
        engine=CURRENT,
        at=5,
        extra={"recomputed_from_event_id": str(original.event_id)},
    )
    late_legacy_reading = _comparison(
        "revision.reinterpreted",
        engine=LEGACY,
        at=9,
        extra={"reinterpretation_of_event_id": str(original.event_id)},
    )

    def decide(*events: ProjectEvent) -> str:
        return decide_temporal_review(
            revision=revision,
            document_id=DOCUMENT,
            events=list(events),
            artifact_type="contract",
            lineage=[parent, revision],
            trust=trust,
        ).reason

    assert decide(original) == "temporal_identity_unverified"
    assert decide(original, recomputed) == "temporal_identity_resolved"
    assert decide(original, recomputed, late_legacy_reading) == "temporal_identity_resolved"


# ── legacy recomputation ────────────────────────────────────────────────────


def _clause(revision: UUID, text: str, code: str = "14.2") -> dict[str, Any]:
    return _snapshot_clause(
        Clause(
            id=uuid4(), project_id=PROJECT, tenant_id=TENANT, document_id=DOCUMENT,
            clause_code=code, clause_type=ClauseType.PENALTY, title=text[:30], full_text=text,
            extracted_entities={},
        )
    )


def _snapshot(revision: UUID, blob_hash: str, text: str, *, at: int) -> ProjectEvent:
    return _event(
        "revision.analyzed",
        {
            "state": "ready",
            "revision_id": str(revision),
            "blob_hash": blob_hash,
            "clauses": [_clause(revision, text)],
        },
        at=at,
        revision=revision,
    )


V1_TEXT = "Clause 14.2 The contractor pays a delay penalty of 1% per week of delay."
V2_TEXT = "Clause 14.2 The contractor pays a delay penalty of 5% per week of delay."


def test_recomputation_is_append_only_provenanced_current_and_deterministic() -> None:
    s1 = _snapshot(V1, V1_HASH, V1_TEXT, at=0)
    s2 = _snapshot(V2, V2_HASH, V2_TEXT, at=1)
    original = _comparison(engine=LEGACY, at=2)
    frozen_original = original.model_dump(mode="json")

    first = build_recomputed_event(original, [s1, s2])
    second = build_recomputed_event(original, [s1, s2])
    assert isinstance(first, ProjectEvent) and isinstance(second, ProjectEvent)

    # Original immutable; the result is a NEW event.
    assert original.model_dump(mode="json") == frozen_original
    assert first.event_id != original.event_id
    assert first.event_type == "revision.recomputed"
    # Deterministic identity: (original, engine) -> one id.
    assert first.event_id == second.event_id == recomputation_event_id(original.event_id, CURRENT)
    # Provenance: what it was recomputed from, with which engine, over which evidence.
    provenance = first.payload["provenance"]
    assert provenance["recomputed_from_event_id"] == str(original.event_id)
    assert provenance["recomputed_from_engine"] == LEGACY
    assert provenance["diff_engine_version"] == CURRENT
    assert provenance["source_snapshot_event_id"] == str(s1.event_id)
    assert provenance["target_snapshot_event_id"] == str(s2.event_id)
    assert (provenance["source_revision_id"], provenance["target_revision_id"]) == (str(V1), str(V2))
    assert (provenance["source_blob_hash"], provenance["target_blob_hash"]) == (V1_HASH, V2_HASH)
    assert first.source_revision_id == V2
    # The current matcher's result qualifies CURRENT; the original stays LEGACY.
    assert qualify_event(first).matcher_status is MatcherStatus.CURRENT
    assert qualify_event(original).matcher_status is MatcherStatus.LEGACY
    assert qualify_event(original).legacy_matcher is True
    # The change is genuinely recomputed from the evidence (1% -> 5%).
    [change] = first.payload["changeset"]["changes"]
    assert change["change_type"] == "modified"


def test_recomputation_never_fabricates_missing_or_mismatched_evidence() -> None:
    original = _comparison(engine=LEGACY, at=2)
    s1 = _snapshot(V1, V1_HASH, V1_TEXT, at=0)
    s2 = _snapshot(V2, V2_HASH, V2_TEXT, at=1)
    assert build_recomputed_event(original, [s1]) == "evidence_snapshot_missing"
    wrong_blob = _snapshot(V2, "f" * 64, V2_TEXT, at=1)
    assert build_recomputed_event(original, [s1, wrong_blob]) == "evidence_snapshot_missing"
    # A snapshot written AFTER the original comparison is not the evidence it used.
    later = _snapshot(V2, V2_HASH, V2_TEXT, at=9)
    assert build_recomputed_event(original, [s1, later]) == "evidence_snapshot_missing"
    assert isinstance(build_recomputed_event(original, [s1, s2]), ProjectEvent)


def test_only_legacy_original_comparisons_are_eligible() -> None:
    assert eligibility(_comparison(engine=LEGACY, at=1)) is None
    assert eligibility(_comparison(engine=CURRENT, at=1)) == "matcher_current"
    assert eligibility(_comparison(engine="other-engine-v1", at=1)) == "matcher_unsupported"
    assert eligibility(_comparison(engine="", at=1)) == "matcher_unsupported"
    derived = _comparison("revision.reinterpreted", engine=LEGACY, at=1)
    assert eligibility(derived) == "not_an_original_comparison"


def test_selection_is_time_honest_for_a_future_project_state_at_t() -> None:
    """A derived event carries its own occurred_at: an as-of-T read before the
    recomputation still sees what was effective then (the legacy reading)."""
    original = _comparison(engine=LEGACY, at=1)
    recomputed = _comparison(
        "revision.recomputed",
        engine=CURRENT,
        at=50,
        extra={"recomputed_from_event_id": str(original.event_id)},
    )
    events = [original, recomputed]

    def as_of(seconds: int) -> ProjectEvent | None:
        moment = T0 + timedelta(seconds=seconds)
        return select_effective_outcome(e for e in events if e.occurred_at <= moment).effective

    assert as_of(10) == original
    assert as_of(60) == recomputed
