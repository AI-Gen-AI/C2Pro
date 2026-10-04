"""TS-UT-P0C-TEMPORAL-007 - read-time qualification of stored change events (PR-C2).

Stored events are immutable. What a user is shown is qualified at read time:
an event compared by a known older version of a registered matcher family is
legacy; an engine nobody registered is unverified (never called "legacy");
only the current registered matcher with full match provenance passes through.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from src.temporal.application.change_qualification import qualify_event
from src.temporal.domain.engine_registry import MatcherStatus, classify_engine_version
from src.temporal.domain.project_event import ProjectEvent


def _change(**overrides: Any) -> dict[str, Any]:
    change: dict[str, Any] = {
        "object_type": "clause",
        "change_type": "modified",
        "anchor": "3",
        "before": {"id": str(uuid4()), "full_text": "3. Penalties are 0.5% per day."},
        "after": {"id": str(uuid4()), "full_text": "3. Penalties are 1.0% per day."},
        "semantic_summary": "clause 3 text modified",
        "match_confidence": 1.0,
        "needs_review": False,
        "evidence_refs": [],
        "severity": None,
        "confidence": None,
        "match_basis": "source_identifier",
        "match_rationale": "source identifier 3 appears once in each revision",
    }
    change.update(overrides)
    return change


def _event(
    engine: str | None, changes: list[dict[str, Any]], *, state: str = "ready"
) -> ProjectEvent:
    now = datetime.now(UTC).replace(tzinfo=None)
    provenance: dict[str, Any] = {
        "source_revision_id": str(uuid4()),
        "target_revision_id": str(uuid4()),
    }
    if engine is not None:
        provenance["diff_engine_version"] = engine
    return ProjectEvent(
        event_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        event_type="revision.changed",
        payload={
            "schema_version": 1,
            "state": state,
            "document_id": str(uuid4()),
            "change_cause": "BUSINESS_STATE_CHANGED",
            "changeset": {"changes": changes},
            "provenance": provenance,
            "l3_impact": None,
        },
        confidence=1.0,
        occurred_at=now,
        created_at=now,
    )


# --- engine family registry (tests 27-29) ------------------------------------


def test_current_registered_engine_version_is_current() -> None:
    result = classify_engine_version("p0c-structural-l1-v2")

    assert result.status is MatcherStatus.CURRENT
    assert result.family == "p0c-structural-l1"


def test_known_older_version_of_registered_family_is_legacy() -> None:
    assert classify_engine_version("p0c-structural-l1-v1").status is MatcherStatus.LEGACY


def test_unknown_engine_family_is_unsupported_not_legacy() -> None:
    for value in ("schedule-cpm-v1", "unknown", None, "", "p0c-structural-l1-v9"):
        assert classify_engine_version(value).status is MatcherStatus.UNSUPPORTED, value


# --- legacy read policy (tests 1-4) -------------------------------------------


def test_v1_matcher_event_is_presented_as_needs_review() -> None:
    event = _event("p0c-structural-l1-v1", [_change(match_basis=None, match_rationale=None)])

    qualification = qualify_event(event)

    assert qualification.matcher_status is MatcherStatus.LEGACY
    assert qualification.legacy_matcher is True
    assert qualification.effective_state == "needs_review"
    assert qualification.effective_change_cause is None
    assert qualification.identity_verified is False
    assert qualification.reason and "p0c-structural-l1-v1" in qualification.reason


def test_v1_confidence_is_unknown_not_one() -> None:
    event = _event("p0c-structural-l1-v1", [_change(match_basis=None)])

    assert event.confidence == 1.0
    assert qualify_event(event).effective_confidence is None


def test_qualification_never_mutates_the_stored_event() -> None:
    event = _event("p0c-structural-l1-v1", [_change(match_basis=None)])
    before = copy.deepcopy(event.model_dump(mode="json"))

    qualify_event(event)

    assert event.model_dump(mode="json") == before


def test_current_v2_event_passes_through_unchanged() -> None:
    event = _event("p0c-structural-l1-v2", [_change()])

    qualification = qualify_event(event)

    assert qualification.matcher_status is MatcherStatus.CURRENT
    assert qualification.legacy_matcher is False
    assert qualification.identity_verified is True
    assert qualification.effective_state == "ready"
    assert qualification.effective_confidence == 1.0
    assert qualification.effective_change_cause == "BUSINESS_STATE_CHANGED"
    assert qualification.reason is None


def test_unknown_family_is_unverified_without_the_legacy_label() -> None:
    event = _event("schedule-cpm-v1", [_change()])

    qualification = qualify_event(event)

    assert qualification.matcher_status is MatcherStatus.UNSUPPORTED
    assert qualification.legacy_matcher is False
    assert qualification.effective_state == "needs_review"
    assert qualification.effective_confidence is None
    assert qualification.reason and "legacy" not in qualification.reason.lower()


def test_current_engine_without_match_provenance_fails_closed() -> None:
    event = _event("p0c-structural-l1-v2", [_change(), _change(match_basis=None)])

    qualification = qualify_event(event)

    assert qualification.identity_verified is False
    assert qualification.legacy_matcher is False
    assert qualification.effective_state == "needs_review"
    assert qualification.effective_confidence is None


def test_non_change_events_are_not_matcher_qualified() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    analyzed = ProjectEvent(
        event_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        event_type="revision.analyzed",
        payload={"state": "needs_review", "document_id": str(uuid4())},
        occurred_at=now,
        created_at=now,
    )

    qualification = qualify_event(analyzed)

    assert qualification.matcher_status is None
    assert qualification.legacy_matcher is False
    assert qualification.effective_state == "needs_review"
